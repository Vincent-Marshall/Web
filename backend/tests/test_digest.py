"""早报组装测试：mock 掉模型调用，验证配额取数与摘要兜底。"""

from app.config import settings
from app.db import init_db
from app.errors import AppError
from app.llm import router as router_mod
from app.services.news import repo
from app.services.news.digest import _summarize_item, build_digest
from app.services.news.sources import NewsItem


def _seed(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "db_path", str(tmp_path / "test.db"))
    monkeypatch.setattr(settings, "digest_top_n", 10)
    init_db()
    items = [NewsItem(source="s", category="tech", title=f"科技{i}", url=f"https://t.cn/t{i}") for i in range(12)]
    items += [NewsItem(source="s", category="cn_politics", title=f"时政{i}", url=f"https://t.cn/p{i}") for i in range(3)]
    items += [NewsItem(source="s", category="world_politics", title=f"国际{i}", url=f"https://t.cn/w{i}") for i in range(5)]
    items += [NewsItem(source="s", category="world_life", title=f"生活{i}", url=f"https://t.cn/l{i}") for i in range(5)]
    repo.save_items(items)


def _fake_llm(monkeypatch, output='{"gist":"要点","detail":"展开"}'):
    monkeypatch.setattr(router_mod.router, "chat", lambda task, messages, **kw: (output, "fake"))


def test_build_digest_full_split(tmp_path, monkeypatch):
    _seed(tmp_path, monkeypatch)
    _fake_llm(monkeypatch)

    digest = build_digest()
    cats = {s["category"]: len(s["items"]) for s in digest["sections"]}
    assert sum(cats.values()) == 10
    assert cats == {"tech": 5, "cn_politics": 1, "world_politics": 2, "world_life": 2}
    # 模型摘要写入条目
    assert digest["sections"][0]["items"][0]["ai_gist"] == "要点"


def test_build_digest_transfers_shortage(tmp_path, monkeypatch):
    # 只有科技与时政候选：缺额应全部让渡给科技
    _seed(tmp_path, monkeypatch)
    _fake_llm(monkeypatch)
    with repo.db_cursor() as cur:
        cur.execute("UPDATE news_items SET digest_date=NULL")
        cur.execute("DELETE FROM news_items WHERE category IN ('world_politics','world_life')")

    digest = build_digest()
    cats = {s["category"]: len(s["items"]) for s in digest["sections"]}
    assert sum(cats.values()) == 10
    assert cats["tech"] == 9 and cats["cn_politics"] == 1


def test_summarize_fallback_when_model_down(tmp_path, monkeypatch):
    _seed(tmp_path, monkeypatch)

    def boom(task, messages, **kw):
        raise AppError("模型挂了", 503)

    monkeypatch.setattr(router_mod.router, "chat", boom)
    item = {"title": "原标题", "url": "https://t.cn/x", "summary": "原文摘要"}
    s = _summarize_item(item)
    assert s["gist"] == "原标题"      # 模型失败 → 标题兜底
    assert s["detail"] == "原文摘要"  # 模型失败 → 原文摘要兜底
