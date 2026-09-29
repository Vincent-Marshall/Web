# AI 工具箱

部署在 [horseforever.cn](https://horseforever.cn) 的个人 AI 工具箱：每天 9:00 把科技与时政新闻的 AI 摘要推送到邮箱，输入生日即可得到八字命盘与 RAG 知识库加持的命理解读，粘贴链接一键生成结构化摘要，首页每天更新诗词、英文句子与名画鉴赏。

## 四个模块

| 模块 | 页面 | 能力 |
|---|---|---|
| 门户首页 | `/` | 每日诗词 / 每日英文句子 / 每日画作鉴赏，各配一段 AI 赏析（第三方 API + 本地兜底数据集 + 按日期缓存） |
| 页面总结 | `/summary` | 粘贴任意文章链接 → 正文提取（trafilatura）→ 结构化摘要（核心观点 + 要点 + 金句），历史可查 |
| 科技早报 | `/news-digest` | 每天 09:00 聚合 7 个新闻源（科技 50% / 国内时政 15% / 国际时政 20% / 国际生活 15%）→ AI 摘要 → 邮件推送，网页可看历史期数、可手动生成 |
| 命理小站 | `/fortune` | 生日 + 时辰 → 八字命盘（lunar-python 确定性计算）+ 自建知识库 RAG + 大模型解读 + 今日黄历（宜忌/冲煞/值神），仅供传统文化参考 |

## 架构

```
horseforever.cn
     │ Nginx（443，HTTPS）
     ├── 静态文件（Next.js 构建产物）
     └── /api/* → 127.0.0.1:8000（uvicorn，systemd 守护）
              ├── 路由层：daily / news / fortune / summary
              ├── 模型路由：fast 档 Ollama qwen2.5:7b 优先、云端降级
              │            quality 档 DeepSeek 优先、本地降级
              ├── 向量化：Ollama bge-m3 → 字符 n-gram 保底
              ├── SQLite（news_items / digests / readings / summaries / kb_chunks …）
              └── 定时任务：systemd timer 每天 09:00（Asia/Shanghai）→ scripts/run_digest.py
```

## 技术栈

- **前端**：Next.js 15（React 19）静态导出 + 原生 CSS 设计变量
- **后端**：FastAPI + Pydantic（配置校验 / 结构化输出约束）
- **存储**：SQLite（单文件，存储层与业务层解耦）
- **模型**：DeepSeek（云端，quality 档）+ Ollama 本地 qwen2.5:7b / bge-m3（fast 档与向量化），逐级降级
- **运维**：Nginx + HTTPS、systemd（Web 服务 + oneshot 定时任务）、日志滚动、统一错误处理
- **测试**：pytest 38 个用例，覆盖纯函数与可 mock 链路

## 核心设计

1. **模型路由与降级链**：任务按输出长度/质量要求分 fast、quality 两档，每档首选失败自动切备选，全挂才报错；每次调用记录实际 provider（日志可观测）。
2. **计算确定性 / 解读概率性分离**：八字、黄历全部由代码确定性计算（可测试、零 token）；LLM 只负责基于检索内容组织语言。
3. **RAG 三层降级**：bge-m3 本地向量化 → 查询失败自动重建 ngram 索引 → 检索不到时明示覆盖不足。
4. **全链路容错**：新闻单源失败跳过、邮件失败下轮补发、解读失败仍返回命盘、首页第三方全挂走内置兜底——任何单点故障不阻断主功能。

## 本地开发

```bash
# 后端（backend/ 目录）
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env                # 填入 DeepSeek key（SMTP 可留空走模拟模式）
.venv/bin/uvicorn app.main:app --reload --port 8000

# 前端（frontend/ 目录）
npm install
cp .env.example .env.local          # NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
npm run dev                         # http://localhost:3000

# 测试
cd backend && .venv/bin/python -m pytest tests/
```

## 部署

完整上线手册见 [backend/deploy/deploy.md](backend/deploy/deploy.md)（Ollama 安装 → systemd → Nginx → HTTPS → 验证清单 → 排障）。

## 目录结构

```
frontend/            Next.js 15（静态导出）
  app/               路由页：/ /summary /news-digest /fortune
  components/        React 组件（各页 View + Nav 等）
  css/               设计变量与各页样式
backend/
  app/
    main.py          FastAPI 入口（路由注册 / 异常兜底 / 启动建索引）
    config.py        pydantic-settings 配置层（.env）
    db.py            SQLite 访问层 + schema + 轻量迁移
    errors.py        统一错误模型（前端只认一种 JSON 错误格式）
    llm/             模型层：clients / router（分档降级）/ embeddings / structured
    routers/         接口层：daily / news / fortune / summary
    services/        业务层：daily / web_reader / summarizer / news / fortune
  scripts/           run_digest.py（定时任务入口）
  deploy/            nginx.conf / backend.service / digest.timer+service / deploy.md
  tests/             pytest（38 个用例）
docs/INTERVIEW.md    面试要点
```

## 路线图

- 博客文章系统：把首页三区内容沉淀为文章
- 用户体系：订阅自己的早报偏好与推送时间
- RSSHub 自建：扩展新闻源覆盖
- GPU 服务器：把更多任务切到更大本地模型（改 .env 即可，架构不变）
