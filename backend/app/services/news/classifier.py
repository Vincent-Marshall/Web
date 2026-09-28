"""国外类新闻的二级分类：world → world_politics / world_life。

主路径：fast 档模型批量分类（一次调用处理一批，省 token、够快）；
降级路径：关键词规则——模型不可用时保底，功能不受影响。
"""

import json
import logging

from app.llm.router import router

logger = logging.getLogger(__name__)

BATCH_SIZE = 20

# 日常生活类关键词（模型降级时的规则兜底，宁缺毋滥——时政是默认值更稳）
LIFE_KEYWORDS = (
    "文化", "艺术", "美食", "旅游", "体育", "娱乐", "电影", "音乐", "生活",
    "健康", "动物", "趣闻", "天气", "节日", "时尚", "游戏", "考古", "展览", "摄影",
)

VALID = {"world_politics", "world_life"}


def classify_world(items: list) -> list[str]:
    """输入带 title/summary 的条目列表，返回等长的类别列表。"""
    if not items:
        return []
    labels: list[str | None] = [None] * len(items)
    try:
        for start in range(0, len(items), BATCH_SIZE):
            batch = items[start : start + BATCH_SIZE]
            for offset, label in enumerate(_classify_by_model(batch)):
                labels[start + offset] = label
    except Exception as e:
        logger.warning("模型批量分类失败，全部改用关键词规则: %s: %s", type(e).__name__, e)
    # 模型漏掉的条目（单条解析失败或整体失败）用规则补齐
    return [label or _classify_by_rules(it) for label, it in zip(labels, items)]


def _title(it) -> str:
    """兼容 dict 与 NewsItem 对象两种输入（测试与内部调用各自方便）。"""
    if isinstance(it, dict):
        return (it.get("title") or "").strip()
    return (getattr(it, "title", None) or "").strip()


def _summary(it) -> str:
    if isinstance(it, dict):
        return (it.get("summary") or "").strip()
    return (getattr(it, "summary", None) or "").strip()


def _classify_by_model(items: list) -> list[str]:
    listing = "\n".join(f"{i}. {_title(it)} | {_summary(it)[:60]}" for i, it in enumerate(items))
    prompt = (
        "下面是一批国际新闻。请判断每条属于哪一类，只输出 JSON：\n"
        "- world_politics（时政）：政治、外交、军事、国际关系、经济政策；\n"
        "- world_life（日常生活）：文化、体育、娱乐、生活方式、社会趣闻。\n"
        '输出格式：{"results":[{"index":0,"category":"world_politics"},...]}，index 与编号一一对应。\n\n'
        + listing
    )
    text, _ = router.chat(
        "news_classify", [{"role": "user", "content": prompt}], json_mode=True, temperature=0.2
    )
    data = json.loads(text)
    mapping = {}
    for r in data.get("results", []):
        cat = str(r.get("category", ""))
        mapping[int(r["index"])] = cat if cat in VALID else "world_politics"
    return [mapping.get(i, "world_politics") for i in range(len(items))]


def _classify_by_rules(item) -> str:
    text = f"{_title(item)} {_summary(item)[:100]}"
    return "world_life" if any(k in text for k in LIFE_KEYWORDS) else "world_politics"
