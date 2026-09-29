"""向量化：本地 bge-m3 优先，字符 n-gram 保底。

保底方案的意义：即使 Ollama 挂了、也没有任何云端 embedding 可用，
检索仍能用字符 bigram 特征跑起来——可用性优先于检索精度。

⚠️ 一致性约定：知识库构建与查询必须使用同一套向量化方法。
调用方（rag.py）在构建时记录所用方法（kb_meta 表），查询时严格跟随。
"""

import logging
import math

import httpx

from app.config import settings
from app.llm.clients import ProviderError

logger = logging.getLogger(__name__)


def embed_texts(texts: list[str]) -> list[list[float]]:
    """bge-m3 批量向量化；失败时抛出，由调用方决定是否降级。"""
    return _ollama_embed(texts)


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


def _ngram_embed(text: str) -> dict[str, float]:
    """字符 bigram 的 TF 向量，稀疏表示 {bigram: L2 归一化权重}。

    用稀疏 dict 而非定长哈希桶：bigram 原样作键，精确匹配、零碰撞——
    中文按相邻字符对切分（「甲乙丙」→「甲乙」「乙丙」），
    这是无任何外部依赖下最简单可用的文本特征。
    """
    grams = [text[i : i + 2] for i in range(max(1, len(text) - 1))]
    if not grams:
        grams = [text[:2]]
    tf: dict[str, float] = {}
    for g in grams:
        tf[g] = tf.get(g, 0.0) + 1.0
    norm = math.sqrt(sum(v * v for v in tf.values())) or 1.0
    return {g: v / norm for g, v in tf.items()}


def cosine(a, b) -> float:
    """余弦相似度。稀疏 dict（ngram）与稠密 list（bge-m3）各自适配。"""
    if isinstance(a, dict) and isinstance(b, dict):
        # 稀疏向量：只累加共同 bigram 的乘积，天然忽略无关维度
        return sum(w * b.get(g, 0.0) for g, w in a.items())
    return sum(x * y for x, y in zip(a, b))
