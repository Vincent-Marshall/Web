"""模型客户端：把不同供应商的协议差异封装在各自客户端里，对外收敛成同一个接口。

上层（router）只认一件事：chat(messages) -> str。
加供应商、换供应商，业务代码零改动——这是「面向接口编程」在这个项目里的具体形态。
"""

import httpx

from app.config import settings


class ProviderError(Exception):
    """某一家模型服务调用失败（超时、限流、网络、响应结构异常等）。

    属于「可降级错误」：路由层捕获它之后切换到下一家。
    """


def _post_json(url: str, payload: dict, headers: dict) -> dict:
    """POST JSON 并做状态码检查；httpx 的网络异常（超时/连接失败）原样抛出，由路由层统一兜。"""
    resp = httpx.post(url, json=payload, headers=headers, timeout=settings.llm_timeout)
    if resp.status_code != 200:
        raise ProviderError(f"{url} 返回 HTTP {resp.status_code}")
    return resp.json()


class OpenAICompatClient:
    """OpenAI 兼容协议客户端：官方 DeepSeek 与任意中转站通用（base_url 可配）。"""

    def __init__(self, base_url: str, api_key: str, model: str):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model

    @property
    def name(self) -> str:
        return "deepseek"

    def chat(self, messages: list[dict], *, json_mode: bool = False, temperature: float = 0.7) -> str:
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
        }
        if json_mode:
            # 要求模型输出合法 JSON；DeepSeek 需要 prompt 里同时出现 "json" 字样，调用方负责
            payload["response_format"] = {"type": "json_object"}
        data = _post_json(f"{self.base_url}/chat/completions", payload, {"Authorization": f"Bearer {self.api_key}"})
        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as e:
            raise ProviderError(f"响应结构异常: {e}") from e


class OllamaClient:
    """本地 Ollama 客户端（HTTP 接口，OpenAI 消息格式通用）。"""

    def __init__(self, base_url: str, model: str):
        self.base_url = base_url.rstrip("/")
        self.model = model

    @property
    def name(self) -> str:
        return "ollama"

    def chat(self, messages: list[dict], *, json_mode: bool = False, temperature: float = 0.7) -> str:
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": temperature},
        }
        if json_mode:
            payload["format"] = "json"  # Ollama 的 JSON 模式
        data = _post_json(f"{self.base_url}/api/chat", payload, {})
        try:
            return data["message"]["content"]
        except KeyError as e:
            raise ProviderError(f"响应结构异常: {e}") from e
