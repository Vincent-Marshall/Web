"""模型路由：业务按「任务档位」请求生成，路由层决定由哪家模型执行。

设计目标（也是面试里最有讲头的一层）：
1. 成本分层——fast 档（分类、标题、短赏析）优先本地免费模型，quality 档（长文摘要、命理解读）优先云端强模型；
2. 可用性降级——首选失败自动切备选，任何一家挂了都不影响功能，全挂才报错；
3. 可观测——每次调用记录实际使用的 provider，排障先看日志就知道问题出在哪一层。

升级路径：将来买 GPU 服务器后，把某档的首选模型在 .env 里换大，
链路的代码一行不用动——「模型选择是配置，不是代码」。
"""

import logging
from enum import Enum

from app.config import settings
from app.errors import AppError
from app.llm.clients import OllamaClient, OpenAICompatClient, ProviderError

logger = logging.getLogger(__name__)


class Tier(str, Enum):
    FAST = "fast"        # 短文本、低难度任务
    QUALITY = "quality"  # 长文本、高质量要求任务


# 任务注册表：新任务在这里登记档位，路由即生效。
# 分档依据：输出长度、质量要求、时延容忍度三个维度。
TASKS: dict[str, Tier] = {
    "news_classify": Tier.FAST,        # 新闻二分类（时政/日常）
    "short_appreciation": Tier.FAST,   # 首页三区短赏析
    "news_summary": Tier.QUALITY,      # 早报新闻摘要
    "url_summary": Tier.QUALITY,       # 文章结构化摘要
    "fortune_reading": Tier.QUALITY,   # 命理解读
}


class ModelRouter:
    def __init__(self) -> None:
        self._ollama = OllamaClient(settings.ollama_base_url, settings.ollama_chat_model)
        self._deepseek = OpenAICompatClient(
            settings.deepseek_base_url, settings.deepseek_api_key, settings.deepseek_model
        )
        # 每档的调用链：列表顺序即优先级，前一环失败自动落到下一环
        self._chains: dict[Tier, list] = {
            Tier.FAST: [self._ollama, self._deepseek],
            Tier.QUALITY: [self._deepseek, self._ollama],
        }

    def chat(
        self,
        task: str,
        messages: list[dict],
        *,
        json_mode: bool = False,
        temperature: float = 0.7,
    ) -> tuple[str, str]:
        """执行任务。

        返回 (生成文本, 实际使用的 provider)。
        全链失败抛 AppError(503)——调用方把它当「业务错误」处理，前端有统一文案。
        """
        if task not in TASKS:
            raise ValueError(f"未登记的任务: {task}")
        tier = TASKS[task]

        for client in self._chains[tier]:
            try:
                text = client.chat(messages, json_mode=json_mode, temperature=temperature)
                logger.info("task=%s tier=%s provider=%s ok", task, tier.value, client.name)
                return text, client.name
            except ProviderError as e:
                logger.warning("task=%s provider=%s 调用失败，切换下一家: %s", task, client.name, e)
            except Exception as e:  # 网络异常（超时/连接拒绝）等一切意外都触发降级
                logger.warning("task=%s provider=%s 异常，切换下一家: %s: %s", task, client.name, type(e).__name__, e)

        raise AppError("模型服务暂时不可用，请稍后重试", status_code=503)


# 全项目共享的单例
router = ModelRouter()
