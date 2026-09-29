"""首页三区内容服务：每日诗词 / 每日英文句子 / 每日画作鉴赏 + AI 短赏析。

设计要点（与全站容错哲学一致）：
1. 三个内容源都是免费第三方 API，每个都配内置兜底数据集（按日期哈希轮换）——
   第三方挂了，首页也永远有内容；
2. 按日期缓存：一天只调一次第三方与模型，省 token、响应快；
3. 赏析走 fast 档（本地模型优先、云端降级），赏析失败时该项为 None，卡片照常渲染。
"""

import hashlib
import json
import logging
import random
from datetime import datetime
from zoneinfo import ZoneInfo

import httpx

from app.db import db_cursor, query_one
from app.llm.router import router

logger = logging.getLogger(__name__)

TZ = ZoneInfo("Asia/Shanghai")
API_TIMEOUT = 12.0
UA = "Mozilla/5.0 (compatible; ai-toolbox/1.0; +https://horseforever.cn)"

# ---------- 内置兜底数据集（第三方 API 全部失败时启用） ----------

FALLBACK_POEMS = [
    {"content": "床前明月光，疑是地上霜。举头望明月，低头思故乡。", "title": "静夜思", "author": "李白"},
    {"content": "白日依山尽，黄河入海流。欲穷千里目，更上一层楼。", "title": "登鹳雀楼", "author": "王之涣"},
    {"content": "春眠不觉晓，处处闻啼鸟。夜来风雨声，花落知多少。", "title": "春晓", "author": "孟浩然"},
    {"content": "千山鸟飞绝，万径人踪灭。孤舟蓑笠翁，独钓寒江雪。", "title": "江雪", "author": "柳宗元"},
    {"content": "锄禾日当午，汗滴禾下土。谁知盘中餐，粒粒皆辛苦。", "title": "悯农", "author": "李绅"},
    {"content": "离离原上草，一岁一枯荣。野火烧不尽，春风吹又生。", "title": "赋得古原草送别", "author": "白居易"},
    {"content": "明月几时有？把酒问青天。不知天上宫阙，今夕是何年。", "title": "水调歌头", "author": "苏轼"},
    {"content": "采菊东篱下，悠然见南山。", "title": "饮酒·其五", "author": "陶渊明"},
    {"content": "会当凌绝顶，一览众山小。", "title": "望岳", "author": "杜甫"},
    {"content": "落霞与孤鹜齐飞，秋水共长天一色。", "title": "滕王阁序", "author": "王勃"},
]

FALLBACK_QUOTES = [
    {"content": "Stay hungry, stay foolish.", "author": "Steve Jobs"},
    {"content": "The best way to predict the future is to invent it.", "author": "Alan Kay"},
    {"content": "Simplicity is the ultimate sophistication.", "author": "Leonardo da Vinci"},
    {"content": "Whatever you are, be a good one.", "author": "Abraham Lincoln"},
    {"content": "It always seems impossible until it's done.", "author": "Nelson Mandela"},
    {"content": "In the middle of difficulty lies opportunity.", "author": "Albert Einstein"},
    {"content": "Well begun is half done.", "author": "Aristotle"},
    {"content": "The journey of a thousand miles begins with a single step.", "author": "Lao Tzu"},
    {"content": "Do what you can, with what you have, where you are.", "author": "Theodore Roosevelt"},
    {"content": "Imagination is more important than knowledge.", "author": "Albert Einstein"},
]

FALLBACK_PAINTINGS = [
    {"title": "星月夜", "artist": "文森特·梵高", "year": "1889", "desc": "后印象派代表作，旋转的星空与宁静的村庄。"},
    {"title": "蒙娜丽莎", "artist": "列奥纳多·达·芬奇", "year": "1503", "desc": "文艺复兴肖像画的巅峰，神秘微笑名满天下。"},
    {"title": "向日葵", "artist": "文森特·梵高", "year": "1888", "desc": "以炽烈黄色描绘的静物系列，生命力喷薄而出。"},
    {"title": "呐喊", "artist": "爱德华·蒙克", "year": "1893", "desc": "表现主义名作，以扭曲的形象传达现代人的焦虑。"},
    {"title": "神奈川冲浪里", "artist": "葛饰北斋", "year": "1831", "desc": "浮世绘巨作，巨浪与富士山的经典构图。"},
    {"title": "戴珍珠耳环的少女", "artist": "约翰内斯·维米尔", "year": "1665", "desc": "「北方的蒙娜丽莎」，光影与回眸的永恒瞬间。"},
    {"title": "清明上河图", "artist": "张择端", "year": "1085", "desc": "北宋风俗画长卷，汴京市井生活的百科全书。"},
    {"title": "格尔尼卡", "artist": "巴勃罗·毕加索", "year": "1937", "desc": "立体主义反战名作，黑白灰中的无声呐喊。"},
    {"title": "睡莲", "artist": "克劳德·莫奈", "year": "1906", "desc": "印象派系列名作，光影在水面上的温柔变奏。"},
    {"title": "千里江山图", "artist": "王希孟", "year": "1113", "desc": "北宋青绿山水巅峰，十八岁的天才绝唱。"},
]

# ---------- 内容抓取（每个源独立 try/except，失败返回 None 由兜底接管） ----------


def _fetch_poem() -> dict | None:
    """今日诗词 API（免费、无需 key）。"""
    try:
        resp = httpx.get("https://v2.jinrishici.com/one.json", timeout=API_TIMEOUT, headers={"User-Agent": UA})
        data = resp.json()["data"]
        origin = data.get("origin") or {}
        return {
            "content": data["content"].strip(),
            "title": origin.get("title") or "佚名",
            "author": origin.get("author") or "佚名",
        }
    except Exception as e:
        logger.warning("今日诗词 API 失败，走兜底: %s", e)
        return None


def _fetch_quote() -> dict | None:
    """quotable 随机名言 API（免费、无需 key）。"""
    try:
        resp = httpx.get("https://api.quotable.io/random", timeout=API_TIMEOUT, headers={"User-Agent": UA})
        data = resp.json()
        return {"content": data["content"], "author": data.get("author") or "佚名"}
    except Exception as e:
        logger.warning("quotable API 失败，走兜底: %s", e)
        return None


_MET_KEYWORDS = ["monet", "van gogh", "renoir", "klimt", "degas", "cezanne", "hopper", "morisot"]


def _fetch_painting() -> dict | None:
    """大都会博物馆 Open Access API（免费、公版画作、无需 key）。"""
    try:
        base = "https://collectionapi.metmuseum.org/public/collection/v1"
        keyword = random.choice(_MET_KEYWORDS)
        resp = httpx.get(
            f"{base}/search?hasImages=true&q={keyword}", timeout=API_TIMEOUT, headers={"User-Agent": UA}
        )
        ids = resp.json().get("objectIDs") or []
        if not ids:
            return None
        obj = httpx.get(
            f"{base}/objects/{random.choice(ids[:50])}", timeout=API_TIMEOUT, headers={"User-Agent": UA}
        ).json()
        image = obj.get("primaryImage") or ""
        if not image:
            return None
        return {
            "title": obj.get("title") or "无题",
            "artist": obj.get("artistDisplayName") or "佚名",
            "year": obj.get("objectDate") or "年代不详",
            "image": image,
        }
    except Exception as e:
        logger.warning("大都会博物馆 API 失败，走兜底: %s", e)
        return None


# ---------- AI 赏析（fast 档，失败返回 None 不阻塞） ----------


def _appreciate(kind: str, content: str, extra: str = "") -> str | None:
    prompts = {
        "poem": f"用一两句话（50字内）赏析这首诗词的意境：{content}",
        "quote": f"用一句中文（40字内）翻译并点评这句英文名言：{content}",
        "painting": f"用一两句话（60字内）鉴赏这幅画作：{extra}",
    }
    try:
        text, _ = router.chat(
            "short_appreciation", [{"role": "user", "content": prompts[kind]}], temperature=0.8
        )
        return text.strip()
    except Exception as e:
        logger.warning("赏析生成失败（%s），该项置空: %s", kind, e)
        return None


# ---------- 组装与缓存 ----------


def _pick_fallback(pool: list[dict], today: str) -> dict:
    """按日期哈希轮换兜底内容：同一天结果稳定，隔天自然轮换。"""
    idx = int(hashlib.md5(today.encode("utf-8")).hexdigest(), 16) % len(pool)
    return pool[idx]


def _build(today: str) -> dict:
    poem = _fetch_poem() or _pick_fallback(FALLBACK_POEMS, today)
    quote = _fetch_quote() or _pick_fallback(FALLBACK_QUOTES, today)
    painting = _fetch_painting() or _pick_fallback(FALLBACK_PAINTINGS, today)

    painting_extra = (
        f"{painting['title']}，{painting['artist']}，{painting['year']}。{painting.get('desc', '')}"
    )
    return {
        "date": today,
        "poem": {**poem, "appreciation": _appreciate("poem", poem["content"])},
        "quote": {**quote, "appreciation": _appreciate("quote", quote["content"])},
        "painting": {**painting, "appreciation": _appreciate("painting", painting["title"], painting_extra)},
    }


def get_daily() -> dict:
    """返回今日三区内容；一天只构建一次（日期缓存），当天重复请求零外部调用。"""
    today = datetime.now(TZ).strftime("%Y-%m-%d")
    cached = query_one("SELECT items_json FROM daily_items WHERE date=?", (today,))
    if cached:
        return json.loads(cached["items_json"])

    data = _build(today)
    with db_cursor() as cur:
        cur.execute(
            "INSERT INTO daily_items (date, items_json) VALUES (?, ?)",
            (today, json.dumps(data, ensure_ascii=False)),
        )
    logger.info("首页三区内容已构建并缓存: %s", today)
    return data
