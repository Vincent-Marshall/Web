"""news_items 与 digests 两张表的存取（早报业务专用，与通用 db.py 分层）。"""

from datetime import datetime, timezone

from app.db import db_cursor, query_all


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def save_items(items: list) -> int:
    """批量入库。url_hash 唯一约束保证重复抓取不会重复收录（INSERT OR IGNORE）。

    返回本次真正新入库的条数。
    """
    inserted = 0
    with db_cursor() as cur:
        for it in items:
            cur.execute(
                """INSERT OR IGNORE INTO news_items
                   (url_hash, source, category, title, url, summary, published_at, fetched_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (it.url_hash, it.source, it.category, it.title, it.url, it.summary, it.published_at, _now()),
            )
            inserted += cur.rowcount
    return inserted


def count_by_category() -> dict[str, int]:
    """各类别的未用候选量（digest_date 为 NULL = 还没进过任何一期早报）。"""
    rows = query_all(
        "SELECT category, COUNT(*) AS n FROM news_items WHERE digest_date IS NULL GROUP BY category"
    )
    return {r["category"]: r["n"] for r in rows}


def take_items(category: str, limit: int) -> list[dict]:
    """按类别取最新的 limit 条候选（新入库优先）。"""
    return query_all(
        """SELECT * FROM news_items
           WHERE digest_date IS NULL AND category = ?
           ORDER BY COALESCE(published_at, fetched_at) DESC LIMIT ?""",
        (category, limit),
    )
