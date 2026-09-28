"""邮件发送：163 SMTP 直连；未配置 SMTP 时进入模拟模式（HTML 写入本地 outbox 目录）。

设计立场：邮件是「尽力而为」的末端通知渠道。
发送失败绝不丢内容——早报已入库、网页可查；失败状态留在 digests.sent_at，
下一轮定时任务自动补发。
"""

import logging
import smtplib
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path

from app.config import settings

logger = logging.getLogger(__name__)

OUTBOX_DIR = Path(settings.db_path).parent / "mail_outbox"


def _send_smtp(subject: str, html_body: str) -> None:
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = settings.smtp_user
    msg["To"] = settings.smtp_to
    # 纯文本备胎 + HTML 正文：老邮件客户端也能读
    msg.set_content("本期早报为 HTML 格式，请用支持 HTML 的客户端查看。")
    msg.add_alternative(html_body, subtype="html")
    with smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=30) as server:
        server.login(settings.smtp_user, settings.smtp_pass)
        server.send_message(msg)


def _send_mock(subject: str, html_body: str) -> None:
    OUTBOX_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    path = OUTBOX_DIR / f"digest_{stamp}.html"
    path.write_text(html_body, encoding="utf-8")
    logger.info("模拟模式：邮件内容已写入 %s", path)


def send_digest(subject: str, html_body: str) -> bool:
    """发送一期早报。返回是否「送达成功」（模拟模式视为成功）。"""
    if not settings.mail_ready:
        _send_mock(subject, html_body)
        return True
    try:
        _send_smtp(subject, html_body)
        logger.info("早报邮件已发送 → %s", settings.smtp_to)
        return True
    except Exception as e:
        logger.warning("邮件发送失败（下轮自动补发）: %s: %s", type(e).__name__, e)
        return False
