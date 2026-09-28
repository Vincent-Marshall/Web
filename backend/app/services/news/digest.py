"""早报摘要流水线：候选池按配额取数 → 逐条 AI 摘要 → 组装 HTML → 存库。

贯穿全链的一条原则：每一步失败都可容忍。
- 单条摘要失败 → 用原文摘要兜底；
- 模型整批挂掉 → 发原文标题版；
- 邮件发送失败 → 内容已入库，下轮自动补发。

早报可以「朴素」，但不可以「没有」。
"""

import html
import json
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from app.config import settings
from app.llm.router import router
from app.services.news import pipeline, repo
from app.services.news.quota import allocate_quota

logger = logging.getLogger(__name__)

TZ = ZoneInfo("Asia/Shanghai")  # 早报是给中国人看的，日期按北京时间算（与 timer 时区一致）

CATEGORY_LABELS = {
    "tech": "科技",
    "cn_politics": "国内时政",
    "world_politics": "国际时政",
    "world_life": "国际生活",
}


def today_str() -> str:
    return datetime.now(TZ).strftime("%Y-%m-%d")


def _summarize_item(item: dict) -> dict:
    """单条新闻的 AI 摘要（quality 档，结构化 JSON 输出）。

    失败时返回原文兜底，绝不抛异常中断整期。
    """
    title = item["title"]
    source_text = (item.get("summary") or "").strip()
    prompt = (
        "请为下面这条新闻写中文摘要，要求：\n"
        "1. gist：一句话讲清核心事实；\n"
        "2. detail：两句话补充背景或影响。\n"
        "信息不足（只有标题）时据实概括，不要编造细节。\n"
        '只输出 JSON：{"gist":"...","detail":"..."}\n\n'
        f"标题：{title}\n原始摘要：{source_text or '（无）'}"
    )
    try:
        text, _ = router.chat(
            "news_summary", [{"role": "user", "content": prompt}], json_mode=True, temperature=0.4
        )
        data = json.loads(text)
        return {
            "gist": str(data.get("gist") or "").strip() or title,
            "detail": str(data.get("detail") or "").strip() or source_text or "",
        }
    except Exception as e:
        logger.warning("新闻摘要失败，用原文兜底: %s: %s", item["url"], e)
        return {"gist": title, "detail": source_text or ""}


def build_digest() -> dict:
    """按配额从候选池取数并逐条摘要。返回 {date, sections, used_ids}。"""
    available = repo.count_by_category()
    plan = allocate_quota(available, settings.digest_top_n)

    sections = []
    used_ids: list[int] = []
    for cat, quota in plan.items():
        items = repo.take_items(cat, quota)
        if not items:
            continue
        used_ids.extend(it["id"] for it in items)
        summarized = []
        for it in items:
            s = _summarize_item(it)
            summarized.append({**it, "ai_gist": s["gist"], "ai_detail": s["detail"]})
        sections.append({"category": cat, "label": CATEGORY_LABELS.get(cat, cat), "items": summarized})

    return {"date": today_str(), "title": f"科技早报 · {today_str()}", "sections": sections, "used_ids": used_ids}


def render_html(digest: dict) -> str:
    """组装邮件与网页共用的 HTML（内联样式，邮件客户端兼容）。"""
    parts = []
    for section in digest["sections"]:
        parts.append(f'<h2 style="color:#1d1d1f;margin:28px 0 12px;">{section["label"]}</h2>')
        for it in section["items"]:
            parts.append(
                '<div style="border-bottom:1px solid #eee;padding:14px 0;">'
                f'<h3 style="margin:0 0 6px;font-size:16px;">'
                f'<a href="{html.escape(it["url"])}" style="color:#0071e3;text-decoration:none;">'
                f'{html.escape(it["title"])}</a></h3>'
                f'<p style="margin:4px 0;color:#1d1d1f;"><strong>{html.escape(it["ai_gist"])}</strong></p>'
                f'<p style="margin:4px 0;color:rgba(29,29,31,0.72);">{html.escape(it["ai_detail"])}</p>'
                f'<p style="margin:4px 0;color:rgba(29,29,31,0.5);font-size:12px;">来源：{html.escape(it["source"])}</p>'
                "</div>"
            )
    body = "\n".join(parts)
    return (
        '<!DOCTYPE html><html><body style="font-family:-apple-system,PingFang SC,Microsoft YaHei,sans-serif;'
        "max-width:680px;margin:0 auto;padding:16px;background:#f5f5f7;\">"
        f'<h1 style="font-size:22px;color:#1d1d1f;">{digest["title"]}</h1>'
        f'<p style="color:rgba(29,29,31,0.5);">由 AI 工具箱每日 9:00 自动生成与推送</p>{body}'
        '<p style="color:rgba(29,29,31,0.4);font-size:12px;margin-top:24px;">'
        "摘要由大模型生成，仅供参考；点击标题跳转原文。</p></body></html>"
    )


def run_digest() -> dict:
    """完整执行一期早报：采集 → 摘要 → 存库 → 发邮件。

    定时脚本与手动触发接口共用这一个入口，保证两处行为一致。
    """
    from app.services.news.mailer import send_digest  # 局部导入避免 mailer 与 digest 循环依赖

    stats = pipeline.fetch_and_store()
    digest = build_digest()
    if not digest["sections"]:
        logger.warning("候选池为空，本期早报跳过")
        return {**stats, "digest": None}

    html_body = render_html(digest)
    repo.save_digest(digest, html_body)
    sent_ok = send_digest(digest["title"], html_body)
    repo.mark_sent(digest["date"], sent_ok)
    repo.mark_items_used(digest["used_ids"], digest["date"])
    logger.info("早报 %s 完成：%d 条，发送=%s", digest["date"], len(digest["used_ids"]), sent_ok)
    return {**stats, "digest_date": digest["date"], "items": len(digest["used_ids"]), "sent": sent_ok}
