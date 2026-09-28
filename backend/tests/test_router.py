"""模型路由测试：用假客户端模拟失败，验证降级链行为（不发起任何真实请求）。"""

import pytest

from app.errors import AppError
from app.llm.clients import ProviderError
from app.llm.router import ModelRouter, Tier


class FakeClient:
    def __init__(self, name, fail_with=None, output="文本"):
        self.name = name
        self._fail = fail_with
        self._output = output
        self.calls = 0

    def chat(self, messages, *, json_mode=False, temperature=0.7):
        self.calls += 1
        if self._fail:
            raise self._fail
        return self._output


def make_router(fast, quality):
    # 绕过 __init__（它依赖 settings 构造真实客户端），直接注入假链
    r = ModelRouter.__new__(ModelRouter)
    r._chains = {Tier.FAST: fast, Tier.QUALITY: quality}
    return r


def test_first_failure_falls_to_second():
    first = FakeClient("ollama", fail_with=ProviderError("本地模型炸了"))
    second = FakeClient("deepseek", output="兜底结果")
    r = make_router([first, second], [])

    text, provider = r.chat("news_classify", [{"role": "user", "content": "hi"}])
    assert provider == "deepseek"
    assert text == "兜底结果"
    assert first.calls == 1 and second.calls == 1  # 每家只调一次


def test_all_fail_raises_apperror():
    a = FakeClient("ollama", fail_with=ConnectionError("连接拒绝"))
    b = FakeClient("deepseek", fail_with=ProviderError("超时"))
    r = make_router([a, b], [])

    with pytest.raises(AppError):
        r.chat("news_classify", [{"role": "user", "content": "hi"}])
    assert a.calls == 1 and b.calls == 1  # 全链走完才报错


def test_quality_prefers_cloud():
    cloud = FakeClient("deepseek", output="云")
    local = FakeClient("ollama", output="本地")
    r = make_router([], [cloud, local])

    _, provider = r.chat("news_summary", [{"role": "user", "content": "hi"}])
    assert provider == "deepseek"
    assert local.calls == 0  # 首选成功就不碰备选


def test_unknown_task_rejected():
    r = make_router([], [])
    with pytest.raises(ValueError):
        r.chat("没登记的任务", [{"role": "user", "content": "hi"}])
