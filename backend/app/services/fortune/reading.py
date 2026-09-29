"""命理解读：RAG 检索 + 云端模型生成，与确定性计算层（bazi.py）分列。

三层分工（本项目「计算确定性 / 解读概率性」边界的核心实现）：
- bazi.py  计算命盘——确定性、零成本、可单元测试；
- rag.py   检索知识库——本地向量化、降级保底；
- 本模块   组织上下文并调用 quality 档模型生成解读——概率性、结构化输出、失败可重试。

解读缓存：同一生日+时辰+性别只生成一次，重复查询零 token 成本。
"""

import hashlib
import json
import logging
from datetime import datetime, timezone

from pydantic import BaseModel, ValidationError

from app.db import db_cursor, query_one
from app.errors import AppError
from app.llm.structured import chat_json
from app.services.fortune.bazi import WUXING_ORDER
from app.services.fortune.rag import retrieve

logger = logging.getLogger(__name__)

PROMPT_TEMPLATE = """你是传统文化命理知识的整理者。请根据下面的【命盘数据】与【知识库内容】，生成一段命理风格的性格解读。

要求：
1. 只依据【知识库内容】组织解读；知识库里没有的内容不要编造；
2. 语气温和积极，把命理当作自我认知的视角，不预言吉凶祸福，不涉及医疗、投资等建议；
3. 用简体中文输出 JSON，字段如下：
   personality：性格特质，80-120 字；
   strengths：优势，40-80 字；
   weaknesses：短板，40-80 字；
   career：事业与学习倾向，60-100 字；
   relationships：人际关系，40-80 字；
   advice：一句话建议，30 字以内。
只输出 JSON 对象，不要任何其他文字。

【命盘数据】
{chart}

【知识库内容】
{kb}"""


class Reading(BaseModel):
    """解读的结构化输出约束：字段缺失/类型错误都会被校验拦下。"""

    personality: str
    strengths: str
    weaknesses: str
    career: str
    relationships: str
    advice: str


def _chart_key(birth_date: str, birth_hour: int, gender: int | None) -> str:
    return hashlib.md5(f"{birth_date}|{birth_hour}|{gender}".encode("utf-8")).hexdigest()


def _build_queries(chart: dict) -> list[str]:
    """按命盘特征构造检索词：日主 + 五行偏旺（≥3）/偏缺（0）+ 强弱。"""
    queries = [chart["day_master"]]
    stats = chart["wuxing_stats"]
    for w in WUXING_ORDER:
        n = stats[w]
        if n >= 3:
            queries.append(f"{w}旺")
        elif n == 0:
            queries.append(f"缺{w}")
    wangshuai = chart.get("wangshuai")
    if wangshuai in ("旺", "强"):
        queries.append("身强")
    elif wangshuai in ("衰", "弱"):
        queries.append("身弱")
    return queries


def _collect_context(chart: dict, max_chunks: int = 6) -> list[str]:
    """多查询检索并去重合并，控制提示词总长度（防 token 爆炸）。"""
    seen: set[int] = set()
    contents: list[str] = []
    for q in _build_queries(chart):
        for hit in retrieve(q, top_k=2):
            if hit["id"] in seen:
                continue
            seen.add(hit["id"])
            contents.append(f"[{hit['section']}] {hit['content']}")
            if len(contents) >= max_chunks:
                return contents
    return contents


def _prompt(chart: dict, contents: list[str]) -> str:
    chart_text = (
        f"四柱：{' '.join(p['ganzhi'] for p in chart['pillars'])}；"
        f"日主：{chart['day_master']}（{chart['day_master_wuxing']}）；"
        f"五行分布：{'、'.join(f'{w}{n}' for w, n in chart['wuxing_stats'].items())}；"
        f"生肖{chart['shengxiao']}，星座{chart['xingzuo']}。"
    )
    kb_text = "\n\n".join(contents) or "（知识库检索无结果，请保守概括并提示用户信息有限。）"
    return PROMPT_TEMPLATE.format(chart=chart_text, kb=kb_text)


def generate_reading(birth_date: str, birth_hour: int, gender: int | None, chart: dict) -> dict:
    """生成（或取缓存）解读。模型全链失败时抛 AppError，由路由层降级为「只返回命盘」。"""
    key = _chart_key(birth_date, birth_hour, gender)
    cached = query_one("SELECT reading_json FROM readings WHERE chart_key=?", (key,))
    if cached and cached["reading_json"]:
        logger.info("命理解读命中缓存: %s…", key[:8])
        return json.loads(cached["reading_json"])

    contents = _collect_context(chart)
    try:
        reading = chat_json("fortune_reading", _prompt(chart, contents), Reading, temperature=0.6)
    except (ValidationError, json.JSONDecodeError) as e:
        raise AppError("解读生成失败，请稍后重试", status_code=502) from e
    data = reading.model_dump()

    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with db_cursor() as cur:
        cur.execute(
            """INSERT INTO readings (chart_key, reading_json, created_at) VALUES (?, ?, ?)
               ON CONFLICT(chart_key) DO UPDATE SET reading_json=excluded.reading_json""",
            (key, json.dumps(data, ensure_ascii=False), now),
        )
    logger.info("命理解读已生成并缓存: %s…", key[:8])
    return data
