"""RAG 检索测试：用临时知识库目录验证分块、建索引、检索全链路（离线，无模型依赖）。"""

import pytest

from app.config import settings
from app.db import init_db
from app.services.fortune import rag


@pytest.fixture
def kb_env(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "db_path", str(tmp_path / "test.db"))
    init_db()
    # 用临时目录替换知识库位置，写入两节测试内容
    kb_dir = tmp_path / "kb"
    kb_dir.mkdir()
    (kb_dir / "01_测试.md").write_text(
        "# 测试\n\n"
        "## 甲木日主\n甲木如参天大树，正直宽厚，进取心强。\n\n"
        "## 乙木日主\n乙木如藤蔓花草，柔韧灵活，善于借势。\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(rag, "KB_DIR", kb_dir)
    return rag


def test_build_index(kb_env):
    result = kb_env.build_index(force=True)
    assert result["rebuilt"] is True
    assert result["chunks"] == 2
    assert result["method"] in ("ngram", "bge-m3")


def test_incremental_skip(kb_env):
    kb_env.build_index(force=True)
    second = kb_env.build_index()
    assert second["rebuilt"] is False  # 内容没变，跳过重建


def test_retrieve_hits_relevant_chunk(kb_env):
    kb_env.build_index(force=True)
    hits = kb_env.retrieve("乙木日主是什么性格")
    assert hits, "检索应有结果"
    assert hits[0]["section"] == "乙木日主"
    assert hits[0]["score"] > 0


def test_retrieve_scores_sorted(kb_env):
    kb_env.build_index(force=True)
    hits = kb_env.retrieve("甲木", top_k=2)
    scores = [h["score"] for h in hits]
    assert scores == sorted(scores, reverse=True)  # 按相关度降序
