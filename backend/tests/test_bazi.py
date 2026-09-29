"""八字计算测试：用与万年历对照过的已知生日断言，保证算法封装正确。"""

import pytest

from app.errors import AppError
from app.services.fortune.bazi import compute_bazi, get_almanac

# 2000-01-01 10:00 的对照结果（与万年历人工核对过）：
# 四柱 己卯/丙子/戊午/丁巳，生肖兔，星座摩羯，日主戊土
KNOWN_CHART = "2000-01-01"


def test_known_chart_pillars():
    chart = compute_bazi(KNOWN_CHART, 10)
    assert [p["ganzhi"] for p in chart["pillars"]] == ["己卯", "丙子", "戊午", "丁巳"]
    assert chart["day_master"] == "戊"
    assert chart["day_master_wuxing"] == "土"
    assert chart["shengxiao"] == "兔"
    assert chart["xingzuo"] == "摩羯"


def test_wuxing_stats_sum_to_eight():
    chart = compute_bazi(KNOWN_CHART, 10)
    assert sum(chart["wuxing_stats"].values()) == 8  # 四柱八字共 8 字
    assert chart["wuxing_stats"]["火"] == 4          # 己卯(土木)丙子(火水)戊午(土火)丁巳(火火)


def test_shishen_mapped_to_pillars():
    chart = compute_bazi(KNOWN_CHART, 10)
    assert chart["pillars"][2]["shishen_gan"] == "日主"  # 日干十神恒为日主


def test_dayun_for_gender():
    chart = compute_bazi(KNOWN_CHART, 10, gender=1)
    assert chart["dayun"]["start_year"] > 0
    assert len(chart["dayun"]["first_six"]) == 6


def test_invalid_date_rejected():
    with pytest.raises(AppError):
        compute_bazi("2000-13-99", 10)


def test_invalid_hour_rejected():
    with pytest.raises(AppError):
        compute_bazi(KNOWN_CHART, 24)


def test_almanac_fixed_date():
    a = get_almanac("2026-09-29")
    assert a["date"] == "2026-09-29"
    assert a["ganzhi"]["year"] and a["ganzhi"]["day"]
    assert a["chong"] and a["sha"]
    assert isinstance(a["yi"], list)
