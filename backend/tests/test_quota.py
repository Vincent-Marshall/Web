"""配额分配纯函数测试：最大余数法 + 缺额让渡。"""

from app.services.news.quota import allocate_quota, parse_quotas


def test_parse_quotas():
    quotas = parse_quotas("tech:0.5,cn_politics:0.15,world_politics:0.2,world_life:0.15")
    assert quotas["tech"] == 0.5
    assert sum(quotas.values()) == 1.0


def test_full_candidates_exact_split():
    # 各类候选充足时，10 条 = 5/1/2/2（与 50/15/20/15 配比一致）
    available = {"tech": 100, "cn_politics": 100, "world_politics": 100, "world_life": 100}
    plan = allocate_quota(available, 10)
    assert plan == {"tech": 5, "cn_politics": 1, "world_politics": 2, "world_life": 2}


def test_shortage_transfers_to_largest_pool():
    # cn_politics 候选为 0：缺额让渡给候选最多的类别，总数仍凑满
    # （返回结果只含名额 > 0 的类别，零名额类别不出现）
    available = {"tech": 100, "cn_politics": 0, "world_politics": 5, "world_life": 5}
    plan = allocate_quota(available, 10)
    assert sum(plan.values()) == 10
    assert plan.get("cn_politics", 0) == 0
    assert plan["tech"] > 5


def test_total_capped_by_available():
    # 候选总量不足 top_n 时，总名额 = 实际候选量
    plan = allocate_quota({"tech": 3, "cn_politics": 0, "world_politics": 0, "world_life": 0}, 10)
    assert sum(plan.values()) == 3
