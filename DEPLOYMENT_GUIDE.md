# Flarum AI Agent V2 上线指导文档

> 面向当前 V2 项目上线到已有 Ubuntu 22.04 + 1Panel + Docker 服务器的操作指南。本文不保存任何服务器密码、API Key 或 Flarum Token；真实密钥请只放在服务器 `.env` 中。

---

## 1. 上线结论

当前项目已经完成上线前本地非 Docker 检查：

- `python-dotenv` 可正常解析 `.env`。
- `python -m compileall core api admin_ui.py main.py sandbox_test.py` 通过。
- `python sandbox_test.py` 离线沙盒测试通过：`3/3 PASS`。
- FastAPI 本地启动测试通过，`/health` 返回 `healthy`。
- Streamlit 本地启动测试通过，HTTP 返回 `200`。
- `docker compose config --quiet` 通过。
- 已新增 `.dockerignore`，避免把 `.env`、备份目录、运行数据、沙盒数据打进镜像。

因此，下一步可以在服务器上做 Docker 构建与启动验证。

---

## 2. 重要判断

### 2.1 不建议增量覆盖旧版目录

如果你已经部署过旧版本，请注意旧目录可能只包含早期结构，例如：

- `core/llm_engine.py`
- `core/memory_manager.py`
- `core/cooldown_manager.py`
- 基础 `api/`、`utils/`、`data/`

当前项目是 V2，新增了关键模块：

- `core/llm_engine_v2.py`
- `core/providers/`
- `core/memory/`
- `core/affection/`
- `core/embeddings/`
- `core/worldbook.py`
- `sandbox_test.py`
- `tests/sandbox_cases.json`

所以服务器上线建议采用 **整包部署新目录** 或 **完整替换旧代码目录**，不要只复制几个 Python 文件。

### 2.2 后台不要直接公网裸露

Streamlit 管理后台默认端口是 `8501`。建议继续使用 SSH 隧道访问：

```bash
ssh -L 8501:127.0.0.1:8501 root@服务器IP
```

然后在本地浏览器打开：

```text
http://127.0.0.1:8501
```

如果后续使用独立域名反代后台，必须加 Basic Auth、访问限制或 IP 白名单。

---

## 3. 上线前本地准备

### 3.1 不要提交真实 `.env`

当前仓库历史中 `.env` 和 `备份/.env` 曾经被 Git 跟踪。上线前建议执行：

```bash
git rm --cached .env 备份/.env
```

然后确认：

```bash
git status --short
```

`.env` 应由服务器单独维护，不建议提交到远程仓库。

### 3.2 确认本地检查通过

```bash
python -m compileall core api admin_ui.py main.py sandbox_test.py
python sandbox_test.py
docker compose config --quiet
```

预期：

- 编译无错误。
- 沙盒测试 `3/3 PASS`。
- Compose 配置退出码为 `0`。

---

## 4. 服务器部署步骤

### 4.1 登录服务器

```bash
ssh root@服务器IP
```

建议先确认服务器基础环境：

```bash
uname -a
docker --version
docker compose version
df -h
free -h
```

### 4.2 备份旧版目录

假设旧项目目录为 `/opt/flarum-ai-agent`，请根据真实路径调整：

```bash
cd /opt
tar -czf flarum-ai-agent-backup-$(date +%Y%m%d_%H%M%S).tar.gz flarum-ai-agent
```

至少要备份：

- 旧 `.env`
- `data/worldbook.json`
- `data/worldbooks/`
- `data/memory/`
- `data/affection/`
- 旧 `docker-compose.yml`

### 4.3 上传新项目

方式一：使用 Git 拉取：

```bash
cd /opt
git clone <你的仓库地址> flarum-ai-agent
cd flarum-ai-agent
```

方式二：使用压缩包上传：

```bash
cd /opt
mkdir -p flarum-ai-agent
cd flarum-ai-agent
# 上传并解压项目包
```

### 4.4 准备服务器 `.env`

在服务器项目目录创建 `.env`：

```bash
cp .env.example .env 2>/dev/null || touch .env
nano .env
```

必须确认以下项：

```env
LLM_API_KEY=你的真实模型Key
LLM_BASE_URL=你的模型Base URL
LLM_MODEL=你的模型名

FLARUM_BASE_URL=https://your-forum.com
FLARUM_API_TOKEN=你的Flarum API Token

WEBHOOK_PORT=8000
ADMIN_UI_PORT=8501

BOT_USERNAMES=AI Assistant,FlarumBot
BOT_USER_IDS=真实机器人用户ID
```

可选项：

```env
REPLY_COOLDOWN_SECONDS=60
MEMORY_VALUE_THRESHOLD=0.3
MEMORY_BLOCK_SIZE=10
SUMMARY_TRIGGER_THRESHOLD=2
MAX_CONTEXT_MESSAGES=5
MAX_SUMMARIES_IN_PROMPT=3

DEFAULT_EMBEDDING_MODEL=qwen
DASHSCOPE_API_KEY=
BGE_MODEL_PATH=

PROVIDER_CONFIGS=
DEFAULT_PROVIDER_TYPE=openai
```

注意：`PROVIDER_CONFIGS` 如果启用，JSON 必须写成一行。

### 4.5 迁移旧数据

如果旧目录存在可复用数据，可以迁移：

```bash
mkdir -p data
cp -a /opt/flarum-ai-agent/data/worldbook.json ./data/ 2>/dev/null || true
cp -a /opt/flarum-ai-agent/data/worldbooks ./data/ 2>/dev/null || true
```

如果要保留 V2 正式记忆和好感度，再迁移：

```bash
cp -a /opt/flarum-ai-agent/data/memory ./data/ 2>/dev/null || true
cp -a /opt/flarum-ai-agent/data/affection ./data/ 2>/dev/null || true
```

旧版通常没有 V2 的 `data/memory` 和 `data/affection`，不存在是正常的。

---

## 5. Docker 构建与启动

### 5.1 构建镜像

```bash
docker compose build
```

如果服务器网络较慢，首次构建可能耗时较长。

### 5.2 启动服务

```bash
docker compose up -d
```

查看状态：

```bash
docker compose ps
```

查看日志：

```bash
docker compose logs -f webhook
docker compose logs -f admin-ui
```

### 5.3 健康检查

服务器本机执行：

```bash
curl http://127.0.0.1:8000/health
```

预期返回：

```json
{"status":"healthy"}
```

如果要确认后台：

```bash
curl -I http://127.0.0.1:8501
```

预期 HTTP 状态为 `200` 或可访问的 Streamlit 响应。

---

## 6. Flarum Webhook 配置

Webhook 地址通常为：

```text
http://服务器IP:8000/api/webhook
```

如果你给 Bot 配置了域名和反向代理，可以使用：

```text
https://你的AI服务域名/api/webhook
```

上线初期建议：

- 先只在测试板块或白名单用户范围内启用。
- 确认 `BOT_USERNAMES` 和 `BOT_USER_IDS` 包含机器人自身，防止自循环。
- 先观察 `docker compose logs -f webhook`，确认不会重复触发。

---

## 7. 上线后验证清单

### 7.1 基础服务

- [ ] `docker compose ps` 中 `webhook` 正常运行。
- [ ] `docker compose ps` 中 `admin-ui` 正常运行。
- [ ] `curl http://127.0.0.1:8000/health` 返回 `healthy`。
- [ ] SSH 隧道能访问 `http://127.0.0.1:8501`。

### 7.2 配置

- [ ] `.env` 中 `LLM_API_KEY` 是真实值。
- [ ] `.env` 中 `FLARUM_BASE_URL` 是真实论坛地址。
- [ ] `.env` 中 `FLARUM_API_TOKEN` 是真实 Token。
- [ ] `BOT_USERNAMES` 包含机器人显示名。
- [ ] `BOT_USER_IDS` 包含机器人真实用户 ID。

### 7.3 安全

- [ ] 管理后台 `8501` 未直接裸露公网。
- [ ] 如果后台配置了域名，已开启 Basic Auth 或访问限制。
- [ ] Flarum Webhook 不会响应机器人自己的帖子。
- [ ] 冷却时间符合预期。
- [ ] 敏感内容处理策略已确认。

### 7.4 数据

- [ ] `data/` 已作为卷挂载。
- [ ] 已创建 `data/worldbook.json`，或已在管理后台创建 V3 世界书。
- [ ] `data/worldbooks/` 如需使用则已迁移。
- [ ] `data/memory/`、`data/affection/` 由 V2 正常创建。
- [ ] 沙盒测试不会污染正式数据。

---

## 8. 常用运维命令

进入项目目录：

```bash
cd /opt/flarum-ai-agent
```

重启服务：

```bash
docker compose restart
```

更新代码后重建：

```bash
docker compose down
docker compose build
docker compose up -d
```

查看 Webhook 日志：

```bash
docker compose logs -f webhook
```

查看后台日志：

```bash
docker compose logs -f admin-ui
```

停止服务：

```bash
docker compose down
```

检查端口监听：

```bash
ss -tulpn | grep -E '8000|8501'
```

---

## 9. 回滚方案

如果 V2 上线后异常，按以下方式回滚：

### 9.1 停止 V2

```bash
cd /opt/flarum-ai-agent
docker compose down
```

### 9.2 恢复旧目录

如果旧目录未删除：

```bash
cd /opt/flarum-ai-agent
docker compose up -d
```

如果旧目录已被替换，从备份恢复：

```bash
cd /opt
tar -xzf flarum-ai-agent-backup-YYYYMMDD_HHMMSS.tar.gz
cd flarum-ai-agent
docker compose up -d
```

### 9.3 验证回滚

```bash
docker compose ps
curl http://127.0.0.1:8000/health
```

---

## 10. 当前已知风险

1. **真实 Flarum 配置仍需人工确认**：本地 `.env` 中 Flarum 地址和 Token 可能仍是占位值，服务器必须使用真实值。
2. **旧版目录不是 V2**：不能只覆盖部分文件，否则会缺少 Provider、三层记忆、好感度、沙盒测试等模块。
3. **`.env` 曾被 Git 跟踪**：提交前建议取消跟踪，避免密钥泄露。
4. **后台安全**：`8501` 不建议直接公网开放。
5. **首次真实发帖需灰度**：建议先测试板块或人工审核，确认不会自循环、刷屏或误回复。

---

## 11. 推荐上线顺序

1. 本地确认代码和 `.env` 模板无误。
2. 服务器备份旧项目目录和旧 `.env`。
3. 上传当前 V2 完整项目。
4. 迁移旧 `.env` 的真实配置到新 `.env`。
5. 迁移世界书和必要数据。
6. 执行 `docker compose build`。
7. 执行 `docker compose up -d`。
8. 检查 `/health` 和后台。
9. 配置或确认 Flarum Webhook。
10. 小范围灰度运行并观察日志。

---

## 12. 最小上线命令清单

```bash
cd /opt/flarum-ai-agent

# 检查配置
docker compose config --quiet

# 构建并启动
docker compose build
docker compose up -d

# 查看状态
docker compose ps

# 健康检查
curl http://127.0.0.1:8000/health

# 查看日志
docker compose logs -f webhook
```

如健康检查通过，再去 Flarum 后台配置 Webhook 地址。