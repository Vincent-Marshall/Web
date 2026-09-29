"""向量化保底路径测试：字符 n-gram 稀疏向量是纯函数，结果确定可验证。"""

from app.llm.embeddings import _ngram_embed, cosine


def test_ngram_deterministic_and_normalized():
    a = _ngram_embed("甲乙丙丁")
    b = _ngram_embed("甲乙丙丁")
    assert a == b                            # 相同输入结果完全一致
    assert abs(cosine(a, a) - 1.0) < 1e-9   # 向量已 L2 归一化


def test_ngram_sparse_exact_match():
    vec = _ngram_embed("甲乙")
    assert list(vec.keys()) == ["甲乙"]       # bigram 原样作键，零碰撞


def test_ngram_distinguishes_texts():
    a = _ngram_embed("天干地支五行生克")
    b = _ngram_embed("足球篮球网球比赛")
    assert cosine(a, b) < 0.99               # 不同文本相似度应显著低于 1
    assert cosine(a, b) == cosine(b, a)      # 对称性


def test_cosine_dense_and_sparse_self():
    assert abs(cosine([1.0, 0.0], [1.0, 0.0]) - 1.0) < 1e-9  # 稠密路径仍可用
