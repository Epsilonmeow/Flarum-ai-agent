# 🐱 Flarum AI Agent 第一次使用指南

这份指南面向第一次接触本项目的使用者，目标是让你按照**最安全、最不容易污染正式数据**的方式完成首次上手。

建议顺序：

1. 安装依赖
2. 先跑离线沙盒测试
3. 启动管理后台
4. 配置真实 LLM
5. 启动 Webhook 服务
6. 最后再接入 Flarum

---

## 0. 项目现在能不能跑？

当前项目已经具备两种运行方式：

| 模式 | 是否需要真实 API Key | 是否会发帖 | 是否写入正式记忆 | 用途 |
|------|----------------------|------------|------------------|------|
| 离线沙盒测试 | ❌ 不需要 | ❌ 不会 | ❌ 不会 | 第一次验证项目主流程 |
| 本地管理后台 | ❌ 可不需要 | ❌ 不会 | 只读/按操作决定 | 查看状态、管理配置 |
| 真实 Webhook 服务 | ✅ 需要 LLM/Flarum 配置 | ✅ 会 | ✅ 会 | 正式接入论坛 |

第一次使用时，**请先运行沙盒测试**，不要一上来就接入真实 Flarum。

---

## 1. 环境准备

### 1.1 进入项目目录

确保当前目录是你克隆或解压后的项目根目录。如果你在其他目录，请切换到项目目录：

```powershell
cd path\to\Flarum_AI_Agent
```

### 1.2 安装依赖

```powershell
pip install -r requirements.txt
```

主要依赖包括：

- FastAPI / Uvicorn：Webhook 服务
- Streamlit：管理后台
- OpenAI SDK / httpx：LLM Provider 调用
- ChromaDB：旧版向量记忆相关能力
- python-dotenv：读取 `.env`

---

## 2. 第一次必须先跑：离线沙盒测试

沙盒测试是目前最推荐的新手入口。

它的特点：

- 使用 `MockProvider`，不调用真实 LLM
- 不需要 API Key
- 不会向 Flarum 发帖
- 不会写入正式记忆目录
- 只使用 `data/sandbox/`
- 默认测试结束后清理沙盒 memory / affection，仅保留报告

### 2.1 运行全部沙盒用例

```powershell
python sandbox_test.py
```

成功时你会看到类似：

```text
总用例: 3 | 通过: 3 | 失败: 0
报告: data/sandbox/reports/sandbox_report_YYYYMMDD_HHMMSS.json
已清理沙盒 memory/affection，仅保留报告
```

### 2.2 只运行某个测试用例

```powershell
python sandbox_test.py --case emotional_support
```

当前内置用例：

| 用例 | 说明 |
|------|------|
| `basic_memory` | 基础对话与短期记忆验证 |
| `emotional_support` | 情绪支持回复验证 |
| `affection_growth` | 感谢/陪伴类互动带来的好感度增长 |

### 2.3 保留沙盒数据方便检查

默认情况下，测试结束后会清理沙盒记忆与好感度。如果你想查看生成的数据，可以运行：

```powershell
python sandbox_test.py --keep-data
```

沙盒数据位置：

```text
data/sandbox/memory
data/sandbox/affection
data/sandbox/reports
```

---

## 3. 启动管理后台

管理后台使用 Streamlit：

```powershell
streamlit run admin_ui.py
```

默认访问：

```text
http://localhost:8501
```

### 3.1 后台页面说明

| 页面 | 作用 |
|------|------|
| 📊 系统状态 | 查看配置文件、Provider、记忆、好感度、沙盒报告状态 |
| 🔌 Provider 管理 | 查看/临时注册 Provider，支持 MockProvider |
| 🧪 沙盒测试 | 可视化运行沙盒测试、查看报告 |
| 📖 世界书编辑 | 管理世界书和条目 |
| 🧠 三层记忆 | 查看正式用户记忆，谨慎删除 |
| ❤️ 好感度系统 | 查看用户关系、好感度排行、互动历史 |
| ⚙️ 系统配置 | 编辑 `.env` 配置 |
| ⏱️ 冷却监控 | 查看用户冷却状态与白名单 |

> 注意：`🧠 三层记忆` 和 `❤️ 好感度系统` 页面读取的是正式数据目录。测试请优先使用 `🧪 沙盒测试` 页面。

---

## 4. 配置真实 LLM

如果沙盒测试通过，下一步可以配置真实 LLM。

编辑 `.env`：

```env
LLM_API_KEY=你的-api-key
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-3.5-turbo
```

DeepSeek 示例：

```env
LLM_API_KEY=你的-deepseek-key
LLM_BASE_URL=https://api.deepseek.com/v1
LLM_MODEL=deepseek-chat
```

通义千问兼容模式示例：

```env
LLM_API_KEY=你的-dashscope-key
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_MODEL=qwen-turbo
```

### 4.1 多 Provider 配置（可选）

如果你要使用多 Provider 故障转移，可以使用 `PROVIDER_CONFIGS`：

```env
PROVIDER_CONFIGS=[{"name":"deepseek","type":"deepseek","api_key":"...","model":"deepseek-chat","is_primary":true},{"name":"qwen","type":"qwen","api_key":"...","model":"qwen-turbo"}]
```

> `.env` 中 JSON 必须保持在一行，且引号、逗号格式必须正确。

---

## 5. 启动 Webhook 服务

```powershell
python main.py
```

默认端口来自 `.env` / `config.py`：

```env
WEBHOOK_PORT=8000
```

启动后可访问：

```text
http://localhost:8000/
http://localhost:8000/health
http://localhost:8000/docs
```

如果 `/health` 返回 healthy，说明基础服务已启动。

---

## 6. 配置 Flarum 真实发帖

只有当你确认沙盒测试、真实 LLM、Webhook 服务都正常后，再配置 Flarum。

`.env` 中需要：

```env
FLARUM_BASE_URL=https://your-forum.com
FLARUM_API_TOKEN=your-flarum-token
```

Flarum Webhook 目标地址通常是：

```text
http://你的服务器:8000/api/webhook
```

如果是本地测试，你需要使用内网穿透或部署到服务器，否则 Flarum 无法访问你的本地服务。

---

## 7. 正式运行前检查清单

正式接入论坛前，请确认：

- [ ] `python sandbox_test.py` 通过
- [ ] `streamlit run admin_ui.py` 能打开后台
- [ ] `.env` 没有格式错误
- [ ] `LLM_API_KEY / LLM_BASE_URL / LLM_MODEL` 已配置
- [ ] Provider 管理页显示可用 Provider
- [ ] `python main.py` 能启动 Webhook 服务
- [ ] `/health` 返回正常
- [ ] `FLARUM_BASE_URL / FLARUM_API_TOKEN` 已配置
- [ ] `BOT_USERNAMES / BOT_USER_IDS` 已包含机器人自己，防止自循环
- [ ] 已创建 `data/worldbook.json`，或已在管理后台创建 V3 世界书
- [ ] 明确区分正式数据与沙盒数据

---

## 8. 数据目录说明

| 目录 | 说明 | 是否正式数据 |
|------|------|--------------|
| `data/memory` | V2 三层记忆正式数据 | ✅ 是 |
| `data/affection` | 好感度正式数据 | ✅ 是 |
| `data/sandbox/memory` | 沙盒记忆 | ❌ 否 |
| `data/sandbox/affection` | 沙盒好感度 | ❌ 否 |
| `data/sandbox/reports` | 沙盒测试报告 | ❌ 否 |
| `data/worldbooks` | V3 世界书数据 | ✅ 是 |
| `data/worldbook.json` | 旧/兼容世界书文件（公开版不内置） | ✅ 是 |

请谨慎操作正式数据目录，尤其是在管理后台中删除用户记忆时。

---

## 9. 常见问题

### Q1：出现 `python-dotenv could not parse statement starting at line ...`

说明 `.env` 某一行格式不合法。常见原因：

- 少了 `=`
- JSON 跨行
- 值里有未转义的换行
- 中文引号或多余符号

处理方式：检查提示的行号，确保格式为：

```env
KEY=value
```

### Q2：沙盒测试失败怎么办？

先运行：

```powershell
python -m compileall core sandbox_test.py
python sandbox_test.py --keep-data
```

然后查看：

```text
data/sandbox/reports
```

沙盒测试不依赖真实 API，因此失败通常意味着代码逻辑或文件路径有问题。

### Q3：Provider 不可用怎么办？

检查：

- API Key 是否正确
- Base URL 是否正确
- 模型名是否正确
- 网络是否能访问 Provider
- Provider 是否支持 OpenAI-compatible 接口

你也可以先在管理后台注册 `mock` Provider 验证本地流程。

### Q4：管理后台打不开怎么办？

确认依赖已安装：

```powershell
pip install -r requirements.txt
```

然后运行：

```powershell
streamlit run admin_ui.py
```

### Q5：Webhook 收不到 Flarum 请求怎么办？

检查：

- Flarum Webhook URL 是否是公网可访问地址
- 端口是否开放
- 反向代理是否转发到 `8000`
- Flarum Webhook 格式是否与 `/api/webhook` 兼容

### Q6：AI 回复生成了，但没有发到论坛怎么办？

检查：

- `FLARUM_BASE_URL`
- `FLARUM_API_TOKEN`
- Flarum API 权限
- 日志中 `post_reply` 是否报错

---

## 10. 推荐第一次使用路径

如果你只想最快确认项目是否能工作，按这个顺序执行：

```powershell
# 1. 安装依赖
pip install -r requirements.txt

# 2. 离线沙盒测试
python sandbox_test.py

# 3. 启动管理后台
streamlit run admin_ui.py

# 4. 配置 .env 后启动 Webhook
python main.py
```

最后再去 Flarum 配置 Webhook。

---

## 11. 下一步建议

第一次跑通后，可以继续做：

1. 在后台调整世界书条目
2. 配置多 Provider 故障转移
3. 扩展 `tests/sandbox_cases.json` 测试集
4. 使用 `--keep-data` 检查沙盒记忆和好感度变化
5. 接入真实 Flarum 前先用 `/api/webhook/test` 做手动验证

---

🐱 祝你第一次启动顺利。建议始终记住：**先沙盒，后真实；先验证，再接入。**
