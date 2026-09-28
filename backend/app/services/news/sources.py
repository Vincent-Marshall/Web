"""新闻源定义与抓取。

加一个新源 = 在 SOURCES 列表里加一条配置，其他地方一行不用改。
所有源均经过连通性实测（2026-09-28 记录）：
- 被淘汰的：36氪（反爬返回 HTML）、虎嗅/澎湃/参考消息/观察者网/环球网（无 RSS 或已废弃）；
- 选源原则：国内服务器可直达（境外源网络不可控，默认不启用）。
"""

import hashlib
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone

import feedparser
import httpx

logger = logging.getLogger(__name__)

UA = "Mozilla/5.0 (compatible; ai-toolbox/1.0; +https://horseforever.cn)"
FETCH_TIMEOUT = 15.0  # 单源超时：宁可少抓一个源，不让早报卡死

SOURCES: list[dict] = [
    # ---- 科技 50% ----
    {"name": "sspai", "category": "tech", "type": "rss", "url": "https://sspai.com/feed"},
    {"name": "ifanr", "category": "tech", "type": "rss", "url": "https://www.ifanr.com/feed"},
    {"name": "ithome", "category": "tech", "type": "rss", "url": "https://www.ithome.com/rss/"},
    {"name": "hackernews", "category": "tech", "type": "hn_api", "url": "https://hacker-news.firebaseio.com"},
    # ---- 国内时政 15% ----
    {"name": "xinhua_politics", "category": "cn_politics", "type": "rss", "url": "http://www.news.cn/politics/news_politics.xml"},
    # ---- 国外类 35%（入库前由 fast 层模型二分类为时政/日常，见 classifier.py）----
    {"name": "xinhua_world", "category": "world", "type": "rss", "url": "http://www.news.cn/world/news_world.xml"},
    {"name": "chinanews_world", "category": "world", "type": "rss", "url": "https://www.chinanews.com.cn/rss/world.xml"},
]


@dataclass
class NewsItem:
    source: str
    category: str
    title: str
    url: str
    summary: str | None = None
    published_at: str | None = None
    url_hash: str = ""

    def __post_init__(self) -> None:
        self.url_hash = hashlib.md5(self.url.encode("utf-8")).hexdigest()


def _iso(value) -> str | None:
    """把 feedparser 的 struct_time 或时间戳转成 ISO 字符串。"""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=timezone.utc).isoformat(timespec="seconds")
    return datetime(*value[:6], tzinfo=timezone.utc).isoformat(timespec="seconds")


def _fetch_rss(name: str, url: str, category: str) -> list[NewsItem]:
    resp = httpx.get(url, timeout=FETCH_TIMEOUT, headers={"User-Agent": UA})
    resp.raise_for_status()  # 非 200 直接抛，由 fetch_all 的逐源捕获接住
    feed = feedparser.parse(resp.content)
    items = []
    for entry in feed.entries:
        link = entry.get("link")
        title = (entry.get("title") or "").strip()
        if not link or not title:
            continue
        summary = None
        if entry.get("summary"):
            # RSS 摘要常带 HTML 标签，剥掉并截断（全文交给 LLM 摘要环节，不存原文）
            summary = re.sub(r"<[^>]+>", "", entry["summary"]).strip()[:300]
        items.append(
            NewsItem(
                source=name,
                category=category,
                title=title,
                url=link,
                summary=summary,
                published_at=_iso(entry.get("published_parsed")),
            )
        )
    return items


def _fetch_hn(base_url: str) -> list[NewsItem]:
    """Hacker News 官方 API：topstories 取前 30 个 id，并发拉条目详情。"""
    with httpx.Client(timeout=FETCH_TIMEOUT, headers={"User-Agent": UA}) as client:
        ids = client.get(f"{base_url}/v0/topstories.json").json()[:30]

        def get_item(item_id: int):
            try:
                return client.get(f"{base_url}/v0/item/{item_id}.json").json()
            except httpx.HTTPError:
                return None

        # 官方 API 无批量接口，用线程池并发拉取（stdlib 方案，不引 aiohttp）
        with ThreadPoolExecutor(max_workers=8) as pool:
            raw = [r for r in pool.map(get_item, ids) if r]

    items = []
    for r in raw:
        url = r.get("url")
        if not url:
            continue  # Ask/Show 等文本帖没有外链，摘要无从谈起
        items.append(
            NewsItem(
                source="hackernews",
                category="tech",
                title=r.get("title") or "",
                url=url,
                published_at=_iso(r.get("time")),
            )
        )
    return items


def fetch_all() -> list[NewsItem]:
    """抓取全部源。单源失败重试一次后只记日志跳过——早报不能因为一个源挂了而中断。"""
    items: list[NewsItem] = []
    for src in SOURCES:
        batch: list[NewsItem] = []
        for attempt in (1, 2):
            try:
                if src["type"] == "rss":
                    batch = _fetch_rss(src["name"], src["url"], src["category"])
                else:
                    batch = _fetch_hn(src["url"])
                break
            except Exception as e:
                logger.warning("源 %s 第 %d 次抓取失败: %s: %s", src["name"], attempt, type(e).__name__, e)
        logger.info("源 %s 抓取 %d 条", src["name"], len(batch))
        items.extend(batch)
    return items
