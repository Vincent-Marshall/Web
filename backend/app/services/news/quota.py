"""早报配额：按类别占比从候选池取数。

两件事在这里解决：
1. 最大余数法——把 top_n 按占比切成整数名额，余数按大小补足，总数恰好等于 top_n；
2. 配额让渡——某类候选不足时，缺额让给候选最多的类别（早报可以少一类，但不断更）。
"""

from app.config import settings

DEFAULT_QUOTAS = {"tech": 0.5, "cn_politics": 0.15, "world_politics": 0.2, "world_life": 0.15}


def parse_quotas(raw: str) -> dict[str, float]:
    """解析 'tech:0.5,cn_politics:0.15,...' 形式的配置；解析失败返回默认值。"""
    quotas: dict[str, float] = {}
    for part in raw.split(","):
        if ":" not in part:
            continue
        name, value = part.split(":", 1)
        try:
            quotas[name.strip()] = float(value.strip())
        except ValueError:
            continue
    return quotas or dict(DEFAULT_QUOTAS)


def allocate_quota(
    available: dict[str, int],
    top_n: int,
    quotas: dict[str, float] | None = None,
) -> dict[str, int]:
    """返回 {类别: 名额}。available 是各类候选条数，top_n 是总数上限。"""
    quotas = quotas or parse_quotas(settings.digest_quotas)
    total_ratio = sum(quotas.values()) or 1.0

    # 第一步：最大余数法算「理想名额」
    ideal: dict[str, int] = {}
    remainders: list[tuple[float, str]] = []
    assigned = 0
    for cat, ratio in quotas.items():
        raw = top_n * ratio / total_ratio
        base = int(raw)
        ideal[cat] = base
        assigned += base
        remainders.append((raw - base, cat))
    for _, cat in sorted(remainders, reverse=True):
        if assigned >= top_n:
            break
        ideal[cat] += 1
        assigned += 1

    # 第二步：按候选量截断，缺额让渡给余量最多的类别（按名称排序保证结果确定、可测试）
    plan = {cat: min(ideal[cat], available.get(cat, 0)) for cat in ideal}
    shortage = top_n - sum(plan.values())
    if shortage > 0:
        order = sorted(plan, key=lambda c: (-(available.get(c, 0) - plan[c]), c))
        for cat in order:
            extra = available.get(cat, 0) - plan[cat]
            give = min(shortage, extra)
            if give > 0:
                plan[cat] += give
                shortage -= give
            if shortage == 0:
                break
    return {c: n for c, n in plan.items() if n > 0}
