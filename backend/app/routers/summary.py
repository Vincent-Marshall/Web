"""页面总结接口：链接 → 结构化摘要，历史可查。"""

import json

from fastapi import APIRouter
from pydantic import BaseModel

from app.db import query_all
from app.services.summarizer import summarize_url

router = APIRouter(prefix="/api/summary", tags=["summary"])


class SummaryRequest(BaseModel):
    url: str


@router.post("")
def summarize(req: SummaryRequest) -> dict:
    """对链接生成结构化摘要。"""
    return summarize_url(req.url.strip())


@router.get("/history")
def history() -> list[dict]:
    """最近 10 条摘要历史。"""
    rows = query_all(
        "SELECT url, title, gist, points_json, quote, created_at "
        "FROM summaries ORDER BY id DESC LIMIT 10"
    )
    return [
        {
            **r,
            "points": json.loads(r.pop("points_json") or "[]"),
        }
        for r in rows
    ]
