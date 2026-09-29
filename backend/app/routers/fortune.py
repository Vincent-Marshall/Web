"""命理小站接口：八字命盘 + 命理解读 + 今日黄历。"""

import logging

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.errors import AppError
from app.services.fortune.bazi import compute_bazi, get_almanac
from app.services.fortune.reading import generate_reading

router = APIRouter(prefix="/api/fortune", tags=["fortune"])
logger = logging.getLogger(__name__)


class BaziRequest(BaseModel):
    birth_date: str            # YYYY-MM-DD
    birth_hour: int = Field(default=12, ge=0, le=23)  # 时辰 0-23
    gender: int | None = Field(default=None, ge=0, le=1)  # 1男 0女，影响大运排法


@router.post("/bazi")
def bazi(req: BaziRequest) -> dict:
    """计算八字命盘（纯确定性计算，不调用任何模型）。"""
    return compute_bazi(req.birth_date, req.birth_hour, req.gender)


@router.post("/reading")
def reading(req: BaziRequest) -> dict:
    """命盘 + 解读。可用性设计：解读失败时仍返回命盘——命盘永远可用。"""
    chart = compute_bazi(req.birth_date, req.birth_hour, req.gender)
    try:
        result = generate_reading(req.birth_date, req.birth_hour, req.gender, chart)
        return {"chart": chart, "reading": result}
    except AppError as e:
        logger.warning("解读降级（只返回命盘）: %s", e.message)
        return {"chart": chart, "reading": None, "reading_error": e.message}


@router.get("/almanac")
def almanac(date: str | None = None) -> dict:
    """今日黄历；可传 ?date=YYYY-MM-DD 查指定日期。"""
    return get_almanac(date)
