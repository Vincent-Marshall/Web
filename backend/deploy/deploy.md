# 上线部署手册

> 按顺序照抄即可。目标服务器：4 核 8G / 60G 云服务器（Ubuntu/Debian 系），域名 horseforever.cn。
> 假设部署目录为 `/opt/ai-toolbox`，前端静态目录为 `/var/www/ai-toolbox`。

## 0. 前置检查

- [ ] 域名 A 记录已解析到服务器公网 IP（ping horseforever.cn 验证）
- [ ] 已准备好 DeepSeek API Key 与 163 邮箱 SMTP 授权码
- [ ] 服务器已能免密 SSH 登录

## 1. 服务器准备

```bash
# 1.1 基础工具
sudo apt update && sudo apt install -y git python3 python3-venv nginx

# 1.2 安装 Ollama（本地模型：fast 档任务 + 向量化）
curl -fsSL https://ollama.com/install.sh | sh
# ⚠️ 国内服务器实测：官方安装脚本的二进制下载（ollama.com CDN / GitHub）
# 可能零速卡死。若脚本超过 3 分钟无进展，Ctrl+C 改手动安装：
#   a. 确认 /usr/local/bin/ollama 与 /usr/local/lib/ollama 已存在（脚本可能已装完二进制）
#   b. 手动补 systemd 单元（注意系统用户无家目录，必须指定 HOME）：
sudo tee /etc/systemd/system/ollama.service > /dev/null << 'EOF'
[Unit]
Description=Ollama Service
After=network-online.target
[Service]
ExecStart=/usr/local/bin/ollama serve
User=ollama
Group=ollama
Environment="HOME=/usr/share/ollama"
Environment="OLLAMA_MODELS=/usr/share/ollama/.ollama/models"
Restart=always
RestartSec=3
[Install]
WantedBy=default.target
EOF
sudo useradd -r -s /usr/sbin/nologin ollama 2>/dev/null || true
sudo mkdir -p /usr/share/ollama && sudo chown ollama:ollama /usr/share/ollama
sudo systemctl daemon-reload && sudo systemctl enable --now ollama

# 模型拉取（默认 registry 实测约 5MB/s，两个模型共 6G，约 20 分钟）
ollama pull qwen2.5:7b   # 约 5G，fast 档对话模型
ollama pull bge-m3       # 约 1.2G，RAG 向量化模型

# 1.3 创建专用运行用户（服务不用 root 跑，缩小攻击面）
sudo useradd -r -s /usr/sbin/nologin aitoolbox || true

# 1.4 目录
sudo mkdir -p /opt/ai-toolbox /var/www/ai-toolbox
```

## 2. 后端部署

```bash
# 2.1 拉取代码（GitHub 慢的话：本地 scp -r backend 目录到服务器同路径）
sudo chown -R $USER /opt/ai-toolbox
cd /opt/ai-toolbox
git clone https://github.com/Vincent-Marshall/Web.git
mv Web/backend/* . && rm -rf Web          # 或按你的实际结构放置
cd backend

# 2.2 Python 环境
# 注意：部分系统 python3-venv 未装（venv 创建报 ensurepip 缺失），先补：
sudo apt install -y python3.12-venv || sudo apt install -y python3-venv
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# 2.3 配置
cp .env.example .env
vim .env   # 填入 DEEPSEEK_API_KEY、SMTP_USER/SMTP_PASS/SMTP_TO
           # 确认 CORS_ORIGINS 含 https://horseforever.cn

# 2.4 验证可启动（先手动跑一次，Ctrl+C 退出）
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8001
curl http://127.0.0.1:8001/api/health   # 应返回 {"status":"ok"}
```

## 3. systemd 守护与定时任务

```bash
sudo chown -R aitoolbox:aitoolbox /opt/ai-toolbox

sudo cp deploy/backend.service deploy/digest.service deploy/digest.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now backend
sudo systemctl enable --now digest.timer

systemctl status backend       # active (running)
systemctl list-timers | grep digest   # 每天 09:00（Asia/Shanghai）
```

## 4. 前端部署

```bash
# 4.1 本地构建（在开发机 frontend/ 目录）
npm install
npm run build                 # 产物在 frontend/out/

# 4.2 上传到服务器
scp -r out/* root@你的服务器:/var/www/ai-toolbox/

# 注意：若构建时报 SIGBUS/worker 崩溃，先重装编译模块再试（见文末排查 9.1）：
# rm -rf node_modules/@next/swc-linux-x64-gnu && npm install
```

## 5. Nginx 与 HTTPS

```bash
sudo cp deploy/nginx.conf /etc/nginx/conf.d/ai-toolbox.conf

# 5.1 申请证书（certbot；如已有证书可跳过）
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d horseforever.cn -d www.horseforever.cn

sudo nginx -t && sudo systemctl reload nginx
```

## 6. 上线验证清单

- [ ] https://horseforever.cn 四个页面全部打开，控制台无报错
- [ ] 首页三区有内容（诗词/句子/画作 + AI 赏析）
- [ ] `/api/health` 返回 `{"status":"ok"}`
- [ ] 页面总结：粘贴一个链接能出结构化摘要
- [ ] 命理小站：输入生日出命盘 + 解读；黄历卡片显示今日宜忌
- [ ] 科技早报页可看今天的早报；`curl -X POST https://horseforever.cn/api/news/run` 手动触发一期，约 1-2 分钟后页面刷新可见
- [ ] 收到真实早报邮件（163 收件箱；进垃圾箱就把发件人加入白名单）
- [ ] `journalctl -u backend -f` 日志正常滚动
- [ ] Ollama 工作：`journalctl -u backend | grep provider=ollama` 能看到 fast 档任务走本地模型

## 7. 日常运维

| 操作 | 命令 |
|---|---|
| 看后端状态 | `systemctl status backend` |
| 看后端日志 | `journalctl -u backend -f` |
| 应用日志文件 | `tail -f /opt/ai-toolbox/backend/logs/app.log`（2MB×5 滚动） |
| 手动生成早报 | `curl -X POST http://127.0.0.1:8001/api/news/run` |
| 手动跑定时脚本 | `cd /opt/ai-toolbox/backend && .venv/bin/python scripts/run_digest.py` |
| 前端更新 | 本地构建 → scp 到 /var/www/ai-toolbox（无需重启） |
| 后端更新 | git pull → `sudo systemctl restart backend` |
| 知识库更新 | 改 backend/app/services/fortune/kb/*.md → 重启 backend（启动时自动重建索引） |

## 8. 数据库与备份

SQLite 单文件位于 `backend/data/app.db`。备份一条命令：

```bash
cp /opt/ai-toolbox/backend/data/app.db /opt/backups/app-$(date +%F).db
```

## 9. 常见问题排查

**9.1 构建报 `SIGBUS` / `Bus error`**：编译模块二进制损坏（常见于代理网络下大文件下载不完整）。验证：`file node_modules/@next/swc-linux-x64-gnu/*.node` 若提示 missing section headers 即为损坏。修复：删包重装 `rm -rf node_modules/@next/swc-linux-x64-gnu && npm install`。

**9.2 早报邮件没收到**：先看 `journalctl -u digest` 或 app.log 里 mailer 的 WARNING；sent_at 为空的早报会在下轮自动补发；QQ/163 邮箱注意查垃圾箱。

**9.3 命理解读慢或失败**：解读走 quality 档（DeepSeek），看日志确认 provider；重复生日查询走缓存（秒回）。

**9.4 本地模型没生效**：`ollama list` 确认模型已拉取；fast 档任务日志里应有 `provider=ollama ok`，否则是 Ollama 未运行（`systemctl status ollama`）。

**9.5 服务器内存告警**：8G 内存跑 7B 模型 + Web 服务有余量；Ollama 空闲会自动卸载模型。若紧张，把 fast 档降级云端：`.env` 里 OLLAMA_BASE_URL 置空后重启 backend。
