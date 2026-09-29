"""命理知识库的 RAG 检索层。

流程：Markdown 按二级标题分块 → 向量化入库（SQLite）→ 查询时余弦相似度取 top-k。
向量化方法（bge-m3 或 ngram）随索引记录在 kb_meta 表，查询严格跟随——
维度一致，余弦相似度才有意义。

可用性设计：bge-m3 在查询时不可用 → 自动把索引重建为 ngram 保底
（知识库只有几十个分块，重建毫秒级），检索功能永不中断。
"""

import hashlib
import logging
from pathlib import Path

from app.db import db_cursor, dumps_json, loads_json, query_all, query_one
from app.llm.embeddings import _ngram_embed, cosine, embed_texts

logger = logging.getLogger(__name__)

KB_DIR = Path(__file__).resolve().parent / "kb"


def _load_chunks() -> list[dict]:
    """按 Markdown 二级标题（##）切块：一个标题一节，节即检索单元。"""
    chunks: list[dict] = []
    for md in sorted(KB_DIR.glob("*.md")):
        source = md.stem
        section, buf = "", []

        def flush():
            text = "\n".join(buf).strip()
            if text:
                chunks.append({"source": source, "section": section, "content": text})

        for line in md.read_text(encoding="utf-8").splitlines():
            if line.startswith("# "):
                continue  # 一级标题是文件名重复信息，不入索引
            if line.startswith("## "):
                flush()
                section = line[3:].strip()
                buf = [line]
            else:
                buf.append(line)
        flush()
    return chunks


def _fingerprint() -> str:
    """知识库内容指纹：文件集合有任何变化，指纹即变。"""
    h = hashlib.md5()
    for md in sorted(KB_DIR.glob("*.md")):
        h.update(md.read_bytes())
    return h.hexdigest()


def _meta(key: str) -> str | None:
    row = query_one("SELECT value FROM kb_meta WHERE key=?", (key,))
    return row["value"] if row else None


def _set_meta(cur, key: str, value: str) -> None:
    cur.execute(
        "INSERT INTO kb_meta (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, value),
    )


def build_index(force: bool = False) -> dict:
    """构建/刷新索引。内容指纹未变且已有索引时直接跳过（增量成本为零）。

    特例：现有索引是 ngram（降级产物），而 bge-m3 现在可用 → 自动重建升级，
    保证向量化服务恢复后索引回到最优状态。
    """
    fingerprint = _fingerprint()
    if not force and _meta("fingerprint") == fingerprint and _meta("method"):
        count = query_one("SELECT COUNT(*) AS n FROM kb_chunks")["n"]
        method = _meta("method")
        if method == "ngram":
            try:
                embed_texts(["向量化可用性探测"])  # bge-m3 恢复则触发下方重建
                force = True
            except Exception:
                pass
        if not force:
            return {"rebuilt": False, "chunks": count, "method": method}

    chunks = _load_chunks()
    if not chunks:
        logger.warning("知识库目录为空，索引未构建")
        return {"rebuilt": False, "chunks": 0, "method": None}

    # 向量化走降级链：bge-m3 可用则用之，否则自动落到字符 n-gram（稀疏向量）
    contents = [c["content"] for c in chunks]
    try:
        vectors = embed_texts(contents)
        method = "bge-m3"
    except Exception as e:
        logger.warning("bge-m3 不可用，改用字符 n-gram 建索引: %s", e)
        vectors = [_ngram_embed(t) for t in contents]
        method = "ngram"

    with db_cursor() as cur:
        cur.execute("DELETE FROM kb_chunks")
        for c, v in zip(chunks, vectors):
            cur.execute(
                "INSERT INTO kb_chunks (source, section, content, embedding) VALUES (?, ?, ?, ?)",
                (c["source"], c["section"], c["content"], dumps_json(v)),
            )
        _set_meta(cur, "fingerprint", fingerprint)
        _set_meta(cur, "method", method)

    logger.info("知识库索引已构建：%d 个分块，向量化=%s", len(chunks), method)
    return {"rebuilt": True, "chunks": len(chunks), "method": method}


def retrieve(query: str, top_k: int = 4) -> list[dict]:
    """检索与查询最相关的知识库分块，返回 [{source, section, content, score}]。"""
    method = _meta("method")
    if method is None:
        build_index(force=True)
        method = _meta("method") or "ngram"

    if method == "bge-m3":
        try:
            vec = embed_texts([query])[0]
        except Exception as e:
            logger.warning("bge-m3 查询不可用，重建 ngram 索引保底: %s", e)
            build_index(force=True)
            method = _meta("method") or "ngram"
    if method == "ngram":
        vec = _ngram_embed(query)

    scored = []
    for row in query_all("SELECT * FROM kb_chunks WHERE embedding IS NOT NULL"):
        emb = loads_json(row["embedding"])
        scored.append((cosine(vec, emb), dict(row)))
    scored.sort(key=lambda x: -x[0])
    # 相似度为 0 的分块没有任何特征重合，属于噪音，直接过滤
    scored = [(s, d) for s, d in scored if s > 0]
    return [{**d, "score": round(s, 4)} for s, d in scored[:top_k]]
