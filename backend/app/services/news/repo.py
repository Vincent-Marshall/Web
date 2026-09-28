"""news_items 与 digests 两张表的存取（早报业务专用，与通用 db.py 分层）。"""

import json
from datetime import datetime, timezone

from app.db import db_cursor, dumps_json, query_all


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


def save_digest(digest: dict, html_body: str) -> None:
    """存一期早报。同一天重复生成时覆盖内容（幂等，不产生重复期数）。"""
    with db_cursor() as cur:
        cur.execute(
            """INSERT INTO digests (date, title, items_json, html, created_at)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(date) DO UPDATE SET
                 title=excluded.title, items_json=excluded.items_json, html=excluded.html""",
            (digest["date"], digest["title"], dumps_json(digest["sections"]), html_body, _now()),
        )


def mark_sent(digest_date: str, ok: bool) -> None:
    """记录发送状态：ok=False 时 sent_at 保持 NULL，下轮任务据此补发。"""
    with db_cursor() as cur:
        cur.execute(
            "UPDATE digests SET sent_at=? WHERE date=?",
            (_now() if ok else None, digest_date),
        )


def mark_items_used(ids: list[int], digest_date: str) -> None:
    """把入选早报的条目标记为已使用，之后不再出现在候选池。"""
    if not ids:
        return
    placeholders = ",".join("?" * len(ids))
    with db_cursor() as cur:
        cur.execute(
            f"UPDATE news_items SET digest_date=? WHERE id IN ({placeholders})",
            [digest_date, *ids],
        )


def get_digest(digest_date: str) -> dict | None:
    """取一期早报（含发送状态）；供网页展示接口使用。"""
    row = query_all("SELECT * FROM digests WHERE date=?", (digest_date,))
    if not row:
        return None
    d = row[0]
    return {
        "date": d["date"],
        "title": d["title"],
        "sections": json.loads(d["items_json"]),
        "html": d["html"],
        "created_at": d["created_at"],
        "sent_at": d["sent_at"],
    }


def list_digest_dates(limit: int = 7) -> list[str]:
    """最近的早报日期列表（供网页历史选择）。"""
    rows = query_all("SELECT date FROM digests ORDER BY date DESC LIMIT ?", (limit,))
    return [r["date"] for r in rows]
