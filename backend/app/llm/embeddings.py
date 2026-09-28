"""向量化：本地 bge-m3 优先，字符 n-gram 保底。

保底方案的意义：即使 Ollama 挂了、也没有任何云端 embedding 可用，
检索仍能用字符 n-gram 特征跑起来——可用性优先于检索精度。

⚠️ 一致性约定：知识库构建与查询必须使用同一套向量化方法（维度一致才能算余弦）。
调用方（rag.py）在构建时记录所用方法，查询时跟随。
"""

import hashlib
import logging
import math

import httpx

from app.config import settings
from app.llm.clients import ProviderError

logger = logging.getLogger(__name__)

NGRAM_DIM = 256  # 保底向量的固定维度


def embed_texts(texts: list[str]) -> list[list[float]]:
    """批量向量化，返回与输入等长的向量列表。"""
    try:
        return _ollama_embed(texts)
    except Exception as e:
        logger.warning("bge-m3 向量化不可用，降级字符 n-gram: %s", e)
        return [_ngram_embed(t) for t in texts]


def _ollama_embed(texts: list[str]) -> list[list[float]]:
    payload = {"model": settings.ollama_embed_model, "input": texts}
    # Ollama 新旧两版接口并存，按新版优先逐个尝试
    for path in ("/api/embeddings", "/api/embed"):
        try:
            resp = httpx.post(
                settings.ollama_base_url.rstrip("/") + path,
                json=payload,
                timeout=settings.llm_timeout,
            )
            if resp.status_code != 200:
                continue
            data = resp.json()
            if "embeddings" in data:
                return list(data["embeddings"])
        except httpx.HTTPError:
            continue
    raise ProviderError("Ollama 向量化接口不可用")


def _ngram_embed(text: str) -> list[float]:
    """字符 bigram 哈希成 256 维 TF 向量，L2 归一化。

    中文按相邻字符对切分（「甲乙丙」→「甲乙」「乙丙」），
    这是无任何外部依赖下最简单可用的文本特征。
    """
    vec = [0.0] * NGRAM_DIM
    grams = [text[i : i + 2] for i in range(max(1, len(text) - 1))]
    if not grams:
        grams = [text[:2]]
    for g in grams:
        idx = int(hashlib.md5(g.encode("utf-8")).hexdigest(), 16) % NGRAM_DIM
        vec[idx] += 1.0
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def cosine(a: list[float], b: list[float]) -> float:
    """余弦相似度（输入已归一化时等价于点积）。"""
    return sum(x * y for x, y in zip(a, b))
