"""科技早报 HTTP 接口：网页展示 + 手动触发。"""

import logging
import threading

from fastapi import APIRouter

from app.errors import AppError
from app.services.news import repo
from app.services.news.digest import run_digest, today_str

router = APIRouter(prefix="/api/news", tags=["news"])
logger = logging.getLogger(__name__)

# 手动触发任务的内存状态。单进程部署足够；将来扩多 worker 时需外置（README 路线图已注明）。
_job: dict = {"running": False, "last": None}


def _run_job() -> None:
    _job["running"] = True
    try:
        _job["last"] = run_digest()
    except Exception as e:  # 后台线程必须兜住一切异常，否则线程静默死亡
        logger.exception("手动触发早报失败")
        _job["last"] = {"error": str(e)}
    finally:
        _job["running"] = False


@router.post("/run")
def trigger_run() -> dict:
    """手动生成一期早报。生成耗时约 1-2 分钟，放后台线程执行，前端轮询 /status。"""
    if _job["running"]:
        raise AppError("早报正在生成中，请稍候", status_code=409)
    threading.Thread(target=_run_job, daemon=True).start()
    return {"status": "running"}


@router.get("/status")
def status() -> dict:
    return _job


@router.get("/today")
def today() -> dict:
    """今日早报；今天还没生成时回退到最近一期——网页永远有内容可看。"""
    digest = repo.get_digest(today_str())
    if digest is None:
        dates = repo.list_digest_dates(1)
        digest = repo.get_digest(dates[0]) if dates else None
    return {"date": today_str(), "digest": digest}


@router.get("/digest")
def get_by_date(date: str) -> dict:
    digest = repo.get_digest(date)
    if digest is None:
        raise AppError("该日期没有早报", status_code=404)
    return digest


@router.get("/archive")
def archive() -> dict:
    """最近的早报日期列表，供网页历史选择。"""
    return {"dates": repo.list_digest_dates(14)}
