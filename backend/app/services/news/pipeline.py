"""采集流水线组装：抓取 → 分类 → 时效过滤 → 去重入库。

这是 run_digest 脚本的第一步，也供手动触发接口调用。
"""

import logging
from datetime import datetime, timedelta, timezone

from app.config import settings
from app.services.news.classifier import classify_world
from app.services.news.repo import save_items
from app.services.news.sources import NewsItem, fetch_all

logger = logging.getLogger(__name__)


def _is_fresh(item: NewsItem) -> bool:
    """只收录最近 digest_news_hours 小时内的新闻；没有时间信息的条目宁多勿漏。"""
    if not item.published_at:
        return True
    try:
        ts = datetime.fromisoformat(item.published_at)
    except ValueError:
        return True
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) - ts <= timedelta(hours=settings.digest_news_hours)


def fetch_and_store() -> dict:
    """执行一轮采集，返回各环节统计（供日志与接口展示）。"""
    items = fetch_all()
    fetched = len(items)

    # 先时效过滤再分类：RSS 源会返回大量旧条目，先砍掉能让模型分类的调用量降一个数量级
    fresh = [it for it in items if _is_fresh(it)]

    # 国外类条目二分类（world → world_politics / world_life）
    world_idx = [i for i, it in enumerate(fresh) if it.category == "world"]
    if world_idx:
        labels = classify_world([fresh[i] for i in world_idx])
        for i, label in zip(world_idx, labels):
            fresh[i].category = label

    inserted = save_items(fresh)
    logger.info("采集 %d 条 → 时效过滤后 %d 条 → 新入库 %d 条", fetched, len(fresh), inserted)
    return {"fetched": fetched, "fresh": len(fresh), "inserted": inserted}
