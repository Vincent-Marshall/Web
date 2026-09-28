"""科技早报定时任务的执行入口（systemd timer 每天 9:00 调用）。

独立脚本 + timer，而不是把调度器嵌进 Web 进程，理由：
- 定时任务与 Web 服务解耦：Web 崩溃/重启不影响早报；
- 将来 Web 扩多 worker 不会重复触发；
- oneshot 服务有独立日志与启停控制。

手动执行（backend/ 目录下）：.venv/bin/python scripts/run_digest.py
"""

import sys
from pathlib import Path

# 把 backend/ 加入模块搜索路径，保证脚本从任何目录被调用都能 import app 包
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db import init_db  # noqa: E402
from app.logging_conf import setup_logging  # noqa: E402

setup_logging()

from app.services.news.digest import run_digest  # noqa: E402


def main() -> int:
    init_db()
    result = run_digest()
    print(result)
    # 没有生成早报（候选池为空）不算失败——正常退 0，避免 systemd 反复告警
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        # 未捕获异常：交给日志记录，退出码 1 让 systemd 感知失败
        import logging

        logging.getLogger(__name__).exception("早报任务执行失败")
        sys.exit(1)
