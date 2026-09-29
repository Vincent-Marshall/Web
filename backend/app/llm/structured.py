"""结构化输出工具：调用模型并要求返回 JSON，解析失败自动重试一次。

命理解读与链接摘要共用此工具——「模型输出不可靠」的坑（坏 JSON、多余文字）
集中在这里处理一次，业务层拿到的永远是合法结构。
"""

import json
import logging

from pydantic import BaseModel, ValidationError

from app.llm.router import router

logger = logging.getLogger(__name__)


def chat_json(
    task: str,
    prompt: str,
    schema: type[BaseModel],
    *,
    temperature: float = 0.6,
) -> BaseModel:
    """按 schema 生成结构化结果；首次解析失败时追加「只输出 JSON」提醒重试。

    两次都失败时抛出 ValidationError/JSONDecodeError，由调用方决定如何降级。
    """
    try:
        text, _ = router.chat(
            task, [{"role": "user", "content": prompt}], json_mode=True, temperature=temperature
        )
        return schema.model_validate_json(text)
    except (ValidationError, json.JSONDecodeError, ValueError):
        logger.warning("task=%s JSON 解析失败，重试一次", task)
        text, _ = router.chat(
            task,
            [{"role": "user", "content": prompt + "\n\n注意：必须只输出一个合法 JSON 对象，不要有任何其他文字。"}],
            json_mode=True,
            temperature=temperature,
        )
        return schema.model_validate_json(text)
