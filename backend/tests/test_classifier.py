"""新闻分类测试：只测确定性的关键词规则路径（模型路径依赖网络，不测）。"""

from app.services.news.classifier import _classify_by_rules


def test_politics_keywords_default():
    # 无生活类关键词 → 时政（默认值更稳）
    assert _classify_by_rules({"title": "某国议会选举结果揭晓"}) == "world_politics"


def test_life_keywords():
    assert _classify_by_rules({"title": "世界美食节开幕"}) == "world_life"
    assert _classify_by_rules({"title": "国际体育赛事", "summary": "精彩的比赛"}) == "world_life"
