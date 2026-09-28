"""日志配置：控制台 + 滚动文件，业务代码直接 logging.getLogger(__name__)。

不引入第三方日志库：标准库 logging 对单机项目完全够用。
"""

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
LOG_FILE = LOG_DIR / "app.log"

# 单文件 2MB，最多留 5 份——防止磁盘被日志写满（服务器上这是真实事故来源）
_FORMAT = "%(asctime)s %(levelname)s [%(name)s] %(message)s"


def setup_logging(level: int = logging.INFO) -> None:
    LOG_DIR.mkdir(exist_ok=True)

    root = logging.getLogger()
    root.setLevel(level)

    if any(isinstance(h, logging.StreamHandler) for h in root.handlers):
        return  # 已被调用过（比如测试里），不重复挂 handler

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(logging.Formatter(_FORMAT))

    file_handler = RotatingFileHandler(
        LOG_FILE, maxBytes=2 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    file_handler.setFormatter(logging.Formatter(_FORMAT))

    root.addHandler(console)
    root.addHandler(file_handler)

    # uvicorn 自带的 access 日志很吵，调低一档
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
