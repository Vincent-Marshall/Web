"""统一错误模型：业务代码抛 AppError，全局 handler 转成一致的 JSON 响应。

前端只需认一种格式：{"detail": "人类可读的中文原因"}
而不是去猜每个接口各自的错误结构。
"""

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


class AppError(Exception):
    """业务错误：message 直接展示给用户，status_code 决定 HTTP 状态码。"""

    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError):
        logger.warning("业务错误 %s %s: %s", request.method, request.url.path, exc.message)
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})

    @app.exception_handler(Exception)
    async def handle_unexpected(request: Request, exc: Exception):
        # 兜底：未知异常必须落日志（带堆栈），但对外只给一句安全的话。
        logger.exception("未处理异常 %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=500,
            content={"detail": "服务器开小差了，请稍后重试"},
        )
