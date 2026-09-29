"""八字命盘与黄历计算：lunar-python 的封装层。

八字是确定性历法计算——全部由代码完成，可复现、可单元测试、零 token 成本。
LLM 只负责「解读」（见 rag.py 与解读接口），绝不让模型碰计算：
干支推算恰恰是 LLM 幻觉的重灾区。

年柱口径说明：八字排法以立春为界，用 EightChar.getYear()（内部按节气处理）；
黄历展示的农历年用 Lunar.getYearInGanZhi()（以正月初一为界），两者口径不同，各取所需。
"""

import logging
from collections import Counter
from datetime import datetime
from zoneinfo import ZoneInfo

from lunar_python import Solar

from app.errors import AppError

logger = logging.getLogger(__name__)

TZ = ZoneInfo("Asia/Shanghai")

# 十天干五行（公共基础知识表）
GAN_WUXING = {
    "甲": "木", "乙": "木", "丙": "火", "丁": "火", "戊": "土",
    "己": "土", "庚": "金", "辛": "金", "壬": "水", "癸": "水",
}

PILLAR_NAMES = ["年柱", "月柱", "日柱", "时柱"]
WUXING_ORDER = ["木", "火", "土", "金", "水"]  # 五行统计的固定输出顺序


def _parse_date(date_str: str) -> tuple[int, int, int]:
    try:
        d = datetime.strptime(date_str, "%Y-%m-%d")
    except (ValueError, TypeError):
        raise AppError("生日格式应为 YYYY-MM-DD，例如 2000-01-01") from None
    return d.year, d.month, d.day


def compute_bazi(birth_date: str, birth_hour: int, gender: int | None = None) -> dict:
    """公历生日 + 时辰(0-23) → 八字命盘。

    gender: 1=男 0=女，用于大运顺逆排法；不填则跳过起运计算。
    """
    if not 0 <= birth_hour <= 23:
        raise AppError("时辰应在 0-23 之间")
    if gender is not None and gender not in (0, 1):
        raise AppError("性别参数应为 1（男）或 0（女）")

    year, month, day = _parse_date(birth_date)
    solar = Solar.fromYmdHms(year, month, day, birth_hour, 0, 0)
    lunar = solar.getLunar()
    ec = lunar.getEightChar()

    shishen_gan = lunar.getBaZiShiShenGan()  # [年干, 月干, 日干, 时干] 的十神
    shishen_zhi = [
        lunar.getBaZiShiShenYearZhi(),
        lunar.getBaZiShiShenMonthZhi(),
        lunar.getBaZiShiShenDayZhi(),
        lunar.getBaZiShiShenTimeZhi(),
    ]

    pillars = []
    for i, name in enumerate(PILLAR_NAMES):
        ganzhi = [ec.getYear(), ec.getMonth(), ec.getDay(), ec.getTime()][i]
        wuxing = [ec.getYearWuXing(), ec.getMonthWuXing(), ec.getDayWuXing(), ec.getTimeWuXing()][i]
        # 地支藏干十神取前两个（本气、中气），余气太弱不展示
        zhi_shishen = "/".join(shishen_zhi[i][:2])
        pillars.append(
            {
                "name": name,
                "ganzhi": ganzhi,
                "wuxing": wuxing,          # 两字符：干五行 + 支五行，如「土木」
                "shishen_gan": shishen_gan[i],
                "shishen_zhi": zhi_shishen,
            }
        )

    # 五行统计：四柱八字共 8 个字符逐个计数
    wuxing_chars = "".join(p["wuxing"] for p in pillars)
    stats = {w: wuxing_chars.count(w) for w in WUXING_ORDER}

    day_gan = ec.getDay()[0]  # 日柱天干 = 日主
    result = {
        "solar": {"date": birth_date, "hour": birth_hour},
        "lunar_text": f"农历{lunar.getYearInGanZhi()}年{lunar.getMonthInChinese()}月{lunar.getDayInChinese()}",
        "day_master": day_gan,
        "day_master_wuxing": GAN_WUXING[day_gan],
        "shengxiao": lunar.getYearShengXiao(),
        "xingzuo": solar.getXingZuo(),
        "day_nayin": lunar.getDayNaYin(),  # 日柱纳音
        "pillars": pillars,
        "wuxing_stats": stats,
    }

    if gender is not None:
        yun = ec.getYun(gender)
        # 列表第一项是起运前的空大运，过滤掉再取前六个
        da_yun = [d.getGanZhi() for d in yun.getDaYun()[:7]]
        result["dayun"] = {
            "start_year": yun.getStartYear(),      # 几岁起运
            "start_month": yun.getStartMonth(),
            "first_six": [g for g in da_yun if g][:6],
        }

    logger.info("八字计算完成: %s %s时 日主=%s", birth_date, birth_hour, day_gan)
    return result


def get_almanac(date_str: str | None = None) -> dict:
    """今日（默认）或指定日期的黄历：农历、干支、宜忌、冲煞、值神。"""
    if date_str is None:
        now = datetime.now(TZ)
        year, month, day = now.year, now.month, now.day
    else:
        year, month, day = _parse_date(date_str)

    solar = Solar.fromYmd(year, month, day)
    lunar = solar.getLunar()
    return {
        "date": solar.toYmd(),
        "lunar_text": f"农历{lunar.getYearInGanZhi()}年{lunar.getMonthInChinese()}月{lunar.getDayInChinese()}",
        "ganzhi": {
            "year": lunar.getYearInGanZhi(),
            "month": lunar.getMonthInGanZhi(),
            "day": lunar.getDayInGanZhi(),
        },
        "yi": lunar.getDayYi(),          # 宜
        "ji": lunar.getDayJi(),          # 忌
        "chong": lunar.getDayChongDesc(),  # 冲（如「冲猪」）
        "sha": lunar.getDaySha(),          # 煞（如「煞东」）
        "zhi_xing": lunar.getZhiXing(),    # 值神（建除十二神）
        "shengxiao": lunar.getYearShengXiao(),
    }
