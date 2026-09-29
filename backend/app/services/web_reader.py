"""网页正文提取：trafilatura 封装。

trafilatura 是可读性提取库，内置对大量站点模板的处理与降级策略，
比手写正则可靠得多——网页结构千差万别，这是「用成熟库而非自己造轮子」的典型场景。
"""

import logging

import httpx
import trafilatura

from app.errors import AppError

logger = logging.getLogger(__name__)

UA = "Mozilla/5.0 (compatible; ai-toolbox/1.0; +https://horseforever.cn)"
FETCH_TIMEOUT = 20.0

MIN_TEXT_LEN = 50  # 提取正文过短视为失败（登录页/图片页等）


def extract_article(url: str) -> dict:
    """抓取网页并提取正文。返回 {title, text, url}；失败抛 AppError（中文原因）。"""
    if not url.startswith(("http://", "https://")):
        raise AppError("请输入以 http:// 或 https:// 开头的完整链接")

    try:
        resp = httpx.get(
            url, timeout=FETCH_TIMEOUT, headers={"User-Agent": UA}, follow_redirects=True
        )
        resp.raise_for_status()
    except httpx.HTTPError as e:
        logger.warning("网页抓取失败 %s: %s", url, e)
        raise AppError("网页抓取失败，请检查链接是否可访问") from e

    # 传入原始 URL，trafilatura 可据此选择站点模板与相对链接还原
    text = trafilatura.extract(resp.text, url=url, include_comments=False, include_tables=False)
    title = (trafilatura.extract_metadata(resp.text).title or "").strip() or url
    if not text or len(text.strip()) < MIN_TEXT_LEN:
        raise AppError("未能从该页面提取到有效正文（可能是登录页、图片页或反爬页面）")

    return {"title": title, "text": text.strip(), "url": url}
