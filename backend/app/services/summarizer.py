"""链接一键摘要：正文提取 → quality 档结构化摘要 → 持久化。

链路与命理解读一致：确定性获取（网页抓取）+ 概率性生成（模型摘要），
模型失败时报中文业务错误，由接口层统一转成 JSON 响应。
"""

import json
import logging
from datetime import datetime, timezone

from pydantic import BaseModel, ValidationError

from app.db import db_cursor
from app.errors import AppError
from app.llm.structured import chat_json
from app.services.web_reader import extract_article

logger = logging.getLogger(__name__)

MAX_PROMPT_CHARS = 5000  # 送入模型的正文上限，防 token 爆炸

PROMPT_TEMPLATE = """请阅读下面的文章，生成结构化摘要，用简体中文输出 JSON：
- gist：一句话核心观点（40 字内）；
- points：3-5 条要点，每条 30 字内，数组；
- quote：原文中最打动人的一句话（20-60 字；若确实没有金句，写「无」）。
只输出 JSON 对象，不要任何其他文字。

文章标题：{title}

文章内容：
{text}"""


class Summary(BaseModel):
    gist: str
    points: list[str]
    quote: str


def summarize_url(url: str) -> dict:
    """对任意网页链接生成结构化摘要，并写入历史。"""
    article = extract_article(url)
    prompt = PROMPT_TEMPLATE.format(
        title=article["title"], text=article["text"][:MAX_PROMPT_CHARS]
    )
    try:
        summary = chat_json("url_summary", prompt, Summary, temperature=0.4)
    except (ValidationError, json.JSONDecodeError) as e:
        raise AppError("摘要生成失败，请稍后重试", status_code=502) from e

    created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with db_cursor() as cur:
        cur.execute(
            """INSERT INTO summaries (url, title, gist, points_json, quote, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                article["url"],
                article["title"],
                summary.gist,
                json.dumps(summary.points, ensure_ascii=False),
                summary.quote,
                created_at,
            ),
        )
    logger.info("链接摘要完成: %s", article["url"])
    return {
        "url": article["url"],
        "title": article["title"],
        "gist": summary.gist,
        "points": summary.points,
        "quote": summary.quote,
        "created_at": created_at,
    }
