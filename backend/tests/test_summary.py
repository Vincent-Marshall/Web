"""链接摘要测试：mock 网页抓取与模型调用，验证结构化输出与历史落库。"""

import pytest

from app.config import settings
from app.db import init_db, query_all
from app.errors import AppError
from app.llm import router as router_mod
from app.services import summarizer

GOOD_JSON = '{"gist":"核心观点","points":["要点一","要点二"],"quote":"金句"}'


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "db_path", str(tmp_path / "test.db"))
    init_db()
    monkeypatch.setattr(
        summarizer,
        "extract_article",
        lambda url: {"title": "测试文章", "text": "正文内容" * 200, "url": url},
    )
    monkeypatch.setattr(router_mod.router, "chat", lambda task, messages, **kw: (GOOD_JSON, "fake"))
    return summarizer


def test_summarize_and_history(env):
    result = env.summarize_url("https://example.com/a")
    assert result["gist"] == "核心观点"
    assert result["points"] == ["要点一", "要点二"]

    rows = query_all("SELECT url, gist FROM summaries")
    assert len(rows) == 1
    assert rows[0]["url"] == "https://example.com/a"


def test_extract_failure_propagates(env, monkeypatch):
    def fail(url):
        raise AppError("网页抓取失败，请检查链接是否可访问")

    monkeypatch.setattr(env, "extract_article", fail)
    with pytest.raises(AppError):
        env.summarize_url("https://example.com/dead")
    # 抓取失败时不应写入历史
    assert query_all("SELECT COUNT(*) AS n FROM summaries")[0]["n"] == 0


def test_invalid_url_rejected(env, monkeypatch):
    # 还原真实校验逻辑：非 http(s) 链接在 extract_article 之前就被拒绝
    from app.services.web_reader import extract_article

    monkeypatch.setattr(env, "extract_article", extract_article)
    with pytest.raises(AppError):
        env.summarize_url("ftp://example.com/a")
