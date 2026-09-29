"""首页三区内容接口。"""

from fastapi import APIRouter

from app.services.daily import get_daily

router = APIRouter(prefix="/api/daily", tags=["daily"])


@router.get("")
def daily() -> dict:
    """今日诗词 / 英文句子 / 画作鉴赏（含 AI 赏析，已按日期缓存）。"""
    return get_daily()
