"""FastAPI 入口：路由注册、中间件、异常兜底、启动初始化。

启动方式（backend/ 目录下）：
    .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
生产环境由 systemd 守护（见 deploy/backend.service）。
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.db import init_db
from app.errors import register_exception_handlers
from app.logging_conf import setup_logging
from app.routers import news

setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    # 启动时建表/迁移：幂等，多跑无害
    init_db()
    logger.info("AI 工具箱后端启动完成")
    yield


app = FastAPI(title="AI 工具箱", version="0.2.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_methods=["GET", "POST"],
)

register_exception_handlers(app)

app.include_router(news.router)


@app.get("/api/health")
def health():
    """部署自查用：返回 200 即服务存活。"""
    return {"status": "ok"}
