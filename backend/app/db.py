"""SQLite 访问层：所有表结构定义在这里，业务代码只 import 函数。

设计说明（面试常问「为什么用 SQLite 不用 MySQL」）：
- 本项目是单机、低并发的个人工具站：每天几十条新闻、偶尔一次命理查询，
  SQLite 单文件 + 零运维完全够用，引入 MySQL 反而是成本；
- 所有访问都收口在本文件，未来要换 MySQL 只改这一层，业务代码不动——
  这就是「存储层与业务层解耦」。
"""

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from app.config import settings

# ---------- 表结构 ----------
# 一次定义全部建表语句：幂等（IF NOT EXISTS），服务每次启动跑一遍即可，
# 不需要引入迁移框架——单机小项目用 alembic 是过度设计。
SCHEMA = """
-- 文字实验室：文本分析历史（v1 遗留，保留原结构）
CREATE TABLE IF NOT EXISTS history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    text TEXT,
    score REAL,
    label TEXT,
    pinyin TEXT,
    created_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_history_created ON history(created_at);

-- 科技早报：抓到的新闻条目。
-- url_hash 唯一约束 = 天然去重：同一个链接只入库一次，重跑任务不会重复收录。
CREATE TABLE IF NOT EXISTS news_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url_hash TEXT UNIQUE NOT NULL,
    source TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT 'tech',  -- tech/cn_politics/world_politics/world_life
    title TEXT NOT NULL,
    url TEXT NOT NULL,
    summary TEXT,
    published_at TEXT,
    fetched_at TEXT NOT NULL,
    digest_date TEXT,
    sort_score REAL
);
CREATE INDEX IF NOT EXISTS idx_news_fetched ON news_items(fetched_at);
CREATE INDEX IF NOT EXISTS idx_news_digest ON news_items(digest_date);

-- 每期早报的成品：网页展示和邮件发送都读这张表。
-- sent_at 为 NULL 表示「已生成、未发送」，定时任务据此补发。
CREATE TABLE IF NOT EXISTS digests (
    date TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    items_json TEXT NOT NULL,
    html TEXT,
    created_at TEXT NOT NULL,
    sent_at TEXT
);

-- 命理知识库分块：embedding 存 JSON 数组（TEXT）。
-- 知识库只有几十条，暴力余弦检索在毫秒级完成，不上向量数据库。
CREATE TABLE IF NOT EXISTS kb_chunks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT,
    section TEXT,
    content TEXT NOT NULL,
    embedding TEXT
);

-- 知识库索引元信息：内容指纹与向量化方法（bge-m3 / ngram）
CREATE TABLE IF NOT EXISTS kb_meta (
    key TEXT PRIMARY KEY,
    value TEXT
);

-- 命理解读缓存：同一生日+时辰+性别只生成一次（重复查询不重复烧 token）
CREATE TABLE IF NOT EXISTS readings (
    chart_key TEXT PRIMARY KEY,
    reading_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

-- 页面总结：链接摘要历史
CREATE TABLE IF NOT EXISTS summaries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url TEXT NOT NULL,
    title TEXT,
    gist TEXT,
    points_json TEXT,
    quote TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_summaries_created ON summaries(created_at);
"""


def _ensure_data_dir() -> None:
    Path(settings.db_path).parent.mkdir(parents=True, exist_ok=True)


def get_conn() -> sqlite3.Connection:
    """每次操作取一个新连接，用完即关。

    SQLite 是文件数据库，多线程共享一个连接反而要处理锁和事务边界；
    低频场景下「短连接」是最简单可靠的模型。
    """
    _ensure_data_dir()
    conn = sqlite3.connect(settings.db_path)
    conn.row_factory = sqlite3.Row  # 查询结果按列名取值，而不是下标
    return conn


@contextmanager
def db_cursor(commit: bool = True):
    """统一的事务入口：业务代码不再手写 commit/close。

    用法：
        with db_cursor() as cur:
            cur.execute(...)
    """
    conn = get_conn()
    try:
        yield conn.cursor()
        if commit:
            conn.commit()
    finally:
        conn.close()


def _migrate(cur) -> None:
    """轻量 schema 演进：给已存在的旧库补新列。

    单机小项目不引入 alembic 迁移框架——检查缺列 + ALTER TABLE 足够，
    迁移逻辑集中在这一处，将来加列照抄即可。
    """
    cols = {row[1] for row in cur.execute("PRAGMA table_info(news_items)").fetchall()}
    if "category" not in cols:
        cur.execute("ALTER TABLE news_items ADD COLUMN category TEXT NOT NULL DEFAULT 'tech'")


def init_db() -> None:
    with db_cursor() as cur:
        cur.executescript(SCHEMA)
        _migrate(cur)


def query_all(sql: str, params: tuple = ()) -> list[dict]:
    """只读查询：返回字典列表。"""
    conn = get_conn()
    try:
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def query_one(sql: str, params: tuple = ()) -> dict | None:
    rows = query_all(sql, params)
    return rows[0] if rows else None


# ---------- 序列化小工具 ----------

def dumps_json(obj) -> str:
    return json.dumps(obj, ensure_ascii=False)


def loads_json(text: str | None):
    if not text:
        return None
    return json.loads(text)
