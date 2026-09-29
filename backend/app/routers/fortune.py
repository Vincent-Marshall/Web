"""命理小站接口：八字命盘 + 今日黄历。

解读接口在后续提交加入（需要 RAG 知识库就绪）。
"""

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.services.fortune.bazi import compute_bazi, get_almanac

router = APIRouter(prefix="/api/fortune", tags=["fortune"])


class BaziRequest(BaseModel):
    birth_date: str            # YYYY-MM-DD
    birth_hour: int = Field(default=12, ge=0, le=23)  # 时辰 0-23
    gender: int | None = Field(default=None, ge=0, le=1)  # 1男 0女，影响大运排法


@router.post("/bazi")
def bazi(req: BaziRequest) -> dict:
    """计算八字命盘（纯确定性计算，不调用任何模型）。"""
    return compute_bazi(req.birth_date, req.birth_hour, req.gender)


@router.get("/almanac")
def almanac(date: str | None = None) -> dict:
    """今日黄历；可传 ?date=YYYY-MM-DD 查指定日期。"""
    return get_almanac(date)
