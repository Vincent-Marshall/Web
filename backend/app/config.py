"""集中配置层：所有可调参数从 .env 读取，代码里不允许出现魔法值。

为什么用 pydantic-settings 而不是裸 os.environ：
- 字段有类型声明，读错配置（比如端口写成字符串）启动时直接报错，而不是运行时炸；
- 所有配置集中在一个类里，看这个文件就知道整个项目有哪些开关。
"""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/ 目录（config.py 在 backend/app/ 下，向上两级）
BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",  # 固定位置，不依赖启动时的工作目录
        env_file_encoding="utf-8",
        extra="ignore",  # .env 里多写的字段不报错，方便本地调试
    )

    # ---------- 云端大模型（DeepSeek，OpenAI 兼容协议） ----------
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"

    # ---------- 本地模型（Ollama，可选：不可达时自动降级云端） ----------
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_chat_model: str = "qwen2.5:7b"
    ollama_embed_model: str = "bge-m3"
    # 单次 LLM 调用的超时上限（秒）。本地 7B 在 CPU 上较慢，给长一点；
    # 云端 10s 足够。超时属于可降级错误，由路由层捕获。
    llm_timeout: float = 60.0

    # ---------- 邮件（163 SMTP；留空则进入模拟模式，邮件写到本地文件） ----------
    smtp_host: str = "smtp.163.com"
    smtp_port: int = 465  # SSL 直连端口
    smtp_user: str = ""   # 163 邮箱地址
    smtp_pass: str = ""   # 163 的 SMTP 授权码（不是登录密码）
    smtp_to: str = ""     # 收件人，可以就写自己

    # ---------- 存储 ----------
    db_path: str = str(BASE_DIR / "data" / "app.db")

    # ---------- 早报 ----------
    digest_top_n: int = 10          # 每期早报收录的条数上限
    digest_news_hours: int = 24     # 只收录最近 N 小时发布的新闻

    # ---------- CORS（逗号分隔，.env 里好写） ----------
    cors_origins: str = "http://localhost:3000,https://horseforever.cn"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def mail_ready(self) -> bool:
        """邮件是否可用：账号、授权码、收件人三者齐了才算。"""
        return bool(self.smtp_user and self.smtp_pass and self.smtp_to)


settings = Settings()
