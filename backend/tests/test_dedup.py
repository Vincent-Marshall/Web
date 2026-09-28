"""入库去重测试：url_hash 唯一约束保证重复抓取幂等。"""

from app.config import settings
from app.db import init_db, query_all
from app.services.news.repo import save_items
from app.services.news.sources import NewsItem


def test_same_url_inserted_once(tmp_path, monkeypatch):
    # 数据库指向测试临时文件，不污染开发数据
    monkeypatch.setattr(settings, "db_path", str(tmp_path / "test.db"))
    init_db()

    item = NewsItem(source="test", category="tech", title="标题", url="https://example.com/a")
    assert save_items([item]) == 1      # 第一次入库 1 条
    assert save_items([item]) == 0      # 同一 URL 再入库 0 条

    rows = query_all("SELECT COUNT(*) AS n FROM news_items")
    assert rows[0]["n"] == 1
