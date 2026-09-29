"""命理解读测试：mock 模型调用，验证查询构造、结构化解析、缓存与重试。"""

from app.config import settings
from app.db import init_db
from app.llm import router as router_mod
from app.services.fortune.bazi import compute_bazi
from app.services.fortune.reading import _build_queries, generate_reading

CHART = compute_bazi("2000-01-01", 10)

GOOD_JSON = (
    '{"personality":"p","strengths":"s","weaknesses":"w",'
    '"career":"c","relationships":"r","advice":"a"}'
)


def test_build_queries_from_chart():
    queries = _build_queries(CHART)
    assert "戊" in queries          # 日主查询
    assert "火旺" in queries        # 火×4 ≥ 3 → 偏旺查询
    assert "缺金" in queries        # 金×0 → 偏缺查询


def test_generate_and_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "db_path", str(tmp_path / "test.db"))
    init_db()
    calls = {"n": 0}

    def fake(task, messages, **kw):
        calls["n"] += 1
        return GOOD_JSON, "fake"

    monkeypatch.setattr(router_mod.router, "chat", fake)

    first = generate_reading("2000-01-01", 10, None, CHART)
    assert first["personality"] == "p"
    second = generate_reading("2000-01-01", 10, None, CHART)  # 命中缓存
    assert second == first
    assert calls["n"] == 1          # 模型只被调用一次


def test_retry_on_bad_json_then_success(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "db_path", str(tmp_path / "test.db"))
    init_db()
    responses = iter(["这不是JSON", GOOD_JSON])

    monkeypatch.setattr(router_mod.router, "chat", lambda task, messages, **kw: (next(responses), "fake"))

    result = generate_reading("2000-01-01", 10, None, CHART)
    assert result["advice"] == "a"  # 第一次解析失败后重试成功
