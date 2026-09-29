"""首页三区服务测试：第三方全挂时的兜底、日期缓存、赏析降级（全部离线）。"""

import pytest

from app.config import settings
from app.db import init_db
from app.errors import AppError
from app.llm import router as router_mod
from app.services import daily


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "db_path", str(tmp_path / "test.db"))
    init_db()
    return daily


def _all_sources_down(monkeypatch):
    monkeypatch.setattr(daily, "_fetch_poem", lambda: None)
    monkeypatch.setattr(daily, "_fetch_quote", lambda: None)
    monkeypatch.setattr(daily, "_fetch_painting", lambda: None)


def test_fallback_when_all_apis_down(env, monkeypatch):
    _all_sources_down(monkeypatch)

    def boom(task, messages, **kw):
        raise AppError("模型挂了", 503)

    monkeypatch.setattr(router_mod.router, "chat", boom)

    data = env.get_daily()
    assert data["poem"]["content"] in [p["content"] for p in daily.FALLBACK_POEMS]
    assert data["quote"]["content"] in [q["content"] for q in daily.FALLBACK_QUOTES]
    assert data["painting"]["title"] in [p["title"] for p in daily.FALLBACK_PAINTINGS]
    assert data["poem"]["appreciation"] is None  # 赏析失败置空，卡片照常渲染


def test_date_cache_hits_once(env, monkeypatch):
    calls = {"n": 0}

    def fake_fetch():
        calls["n"] += 1
        return None

    monkeypatch.setattr(daily, "_fetch_poem", fake_fetch)
    monkeypatch.setattr(daily, "_fetch_quote", fake_fetch)
    monkeypatch.setattr(daily, "_fetch_painting", fake_fetch)
    monkeypatch.setattr(router_mod.router, "chat", lambda task, messages, **kw: ("赏析", "fake"))

    first = env.get_daily()
    second = env.get_daily()
    assert first == second
    assert calls["n"] == 3  # 三个源各抓取一次，第二次请求全部走缓存


def test_pick_fallback_deterministic():
    a = daily._pick_fallback(daily.FALLBACK_POEMS, "2026-09-29")
    b = daily._pick_fallback(daily.FALLBACK_POEMS, "2026-09-29")
    assert a == b  # 同一天结果稳定
