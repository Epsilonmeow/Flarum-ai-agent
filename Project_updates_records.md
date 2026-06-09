# 项目更新记录

用于记录 Flarum AI Agent V2 的项目更新、UI 调整、功能适配与重要修复。新增记录建议按时间倒序追加。

---

## 2026/6/9 14:00 UI 更新适配 V2

### 本次更新内容

- 修复 `admin_ui.py` 中"世界书编辑 -> 世界书编辑器 V3 -> 📚 世界书列表"右侧边栏状态灯在按钮方框内未正确居中的旧 UI 问题。
- 将世界书/条目状态灯从 emoji 圆点调整为 Streamlit 彩色文本状态点，降低不同平台 emoji 渲染导致的偏移风险。
- 为世界书列表中的条目适配类似 SillyTavern 的三状态灯：
  - **绿色**：条目已开启，按关键词触发后进入发送给 AI 的上下文。
  - **蓝色**：条目为 `constant` 常驻模式，会始终存在于发送给 AI 的上下文中。
  - **灰色**：条目已关闭，不会发送给 AI。
- 在条目编辑区补充"常驻模式 (constant)"选项，支持编辑已有条目的常驻状态并保存。
- 更新 `core/worldbook.py` 的扫描逻辑，使 `constant=True` 的启用条目不依赖关键词匹配，符合常驻条目的语义。
- 已通过 `python -m py_compile admin_ui.py core\worldbook.py` 进行语法检查。

---

## V2 工业级升级概览（历史里程碑）

### 核心架构升级

| 模块 | 功能 | 文件 |
|------|------|------|
| **Provider 架构** | 多模型故障转移 (OpenAI/DeepSeek/Qwen) | `core/providers/` |
| **三层记忆系统** | L1 摘要层 + L2 块层 + L3 历史层 | `core/memory/` |
| **增量总结引擎** | 每 2 个块自动触发 AI 总结 | `core/memory/summary_engine.py` |
| **双模型 Embedding** | BGE-M3 本地 + Qwen API | `core/embeddings/` |
| **好感度系统** | 5 级关系 + 智能奖励机制 | `core/affection/` |
| **LLMEngine V2** | 集成所有新系统的完整引擎 | `core/llm_engine_v2.py` |
| **世界书 V3** | 多世界书、条目管理、关键词扫描 | `core/worldbook.py` |
| **MockProvider** | 离线沙盒测试模型，不调用真实 API | `core/providers/mock_provider.py` |
| **沙盒测试 Runner** | 独立数据目录 + 测试报告 + 自动清理 | `sandbox_test.py` |
| **稳定 JSON 存储** | 用户级锁 + 原子写入 + 损坏备份 | `core/memory/layered_memory.py` |

### 新增配置项

```python
# 记忆系统
MEMORY_BLOCK_SIZE = 10
SUMMARY_TRIGGER_THRESHOLD = 2
MAX_CONTEXT_MESSAGES = 5

# 好感度系统
DAILY_BONUS_POINTS = 5
CONSECUTIVE_BONUS_POINTS = 10
EMOTIONAL_SUPPORT_BONUS = 5

# Embedding
DEFAULT_EMBEDDING_MODEL = "qwen"
BGE_MODEL_PATH = os.getenv("BGE_MODEL_PATH")
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY")

# Provider
PROVIDER_CONFIGS = []  # JSON格式配置
DEFAULT_PROVIDER_TYPE = "openai"
```

---

## 测试能力

### 快速测试命令

```bash
# 1. 系统初始化
python init_system.py

# 2. 运行基础示例
python example_usage.py

# 3. 新引擎对话测试
python test_v2.py

# 4. 管理界面
streamlit run admin_ui.py

# 5. 沙盒测试（推荐）
python sandbox_test.py

# 6. Provider 故障转移测试
python test_provider_failover.py
```

### 沙盒测试特点

- ✅ 默认使用 `MockProvider`，不调用真实 LLM API，不消耗额度
- ✅ 不调用 Flarum 发帖接口，不会向真实论坛发帖
- ✅ 使用独立目录：`data/sandbox/memory` 与 `data/sandbox/affection`
- ✅ 默认测试结束后清理沙盒记忆和好感度，仅保留测试报告
- ✅ 可验证回复生成、三层记忆、好感度增长、基础断言

### 测试检查清单

| 测试项 | 命令/方式 | 说明 |
|--------|-----------|------|
| 系统初始化 | `python init_system.py` | 检查目录与 Provider |
| 基础示例 | `python example_usage.py` | 三层记忆 + 好感度 + Embedding |
| 新引擎对话 | `python test_v2.py` | 完整对话流程 |
| 管理界面 | `streamlit run admin_ui.py` | 可视化后台操作 |
| Provider 故障转移 | `python test_provider_failover.py` | 多 Provider 切换 |
| 三层记忆 | 11 条消息触发块完成 | L1/L2/L3 记忆验证 |
| 增量总结 | 2 个块触发摘要 | AI 总结生成 |
| 好感度积累 | 5 次互动 | 5 级关系测试 |
| 奖励机制 | 不同类型互动 | 感谢/情感支持/深度交流 |
| Embedding | 需 DASHSCOPE_API_KEY | 语义检索 |

---

## 项目结构

```
Flarum_AI_Agent/
├── 📄 main.py                 # FastAPI 主入口
├── 📄 admin_ui.py             # Streamlit 管理后台
├── 📄 config.py               # 全局配置
├── 📄 requirements.txt        # Python依赖
├── 📄 sandbox_test.py         # 离线沙盒测试 Runner
├── 📄 Dockerfile              # 容器镜像
├── 📄 docker-compose.yml      # 编排配置
├── 📄 .env.example            # 环境变量示例
├── 📁 api/                    # API路由
│   └── webhook_listener.py    # Webhook接收器
├── 📁 core/                   # 核心逻辑
│   ├── llm_engine_v2.py       # V2 引擎
│   ├── memory_manager.py      # ChromaDB记忆管理
│   ├── cooldown_manager.py    # 回复冷却管理
│   ├── worldbook.py           # 世界书 V3 系统
│   ├── providers/             # 多Provider架构
│   ├── memory/                # 三层记忆系统
│   ├── embeddings/            # 双模型Embedding
│   └── affection/             # 好感度/关系系统
├── 📁 tests/                  # 测试集
│   └── sandbox_cases.json     # 沙盒测试用例
├── 📁 utils/                  # 工具函数
└── 📁 data/                   # 数据存储
    ├── worldbook.json         # 旧/兼容世界书配置（公开版不内置）
    ├── worldbooks/            # V3 世界书数据
    ├── memory/                # 正式三层记忆数据
    ├── affection/             # 正式好感度数据
    └── sandbox/               # 沙盒测试数据与报告
```

---

## 文档索引

- [README.md](README.md) - 项目概览与快速开始
- [UPGRADE_V2_README.md](UPGRADE_V2_README.md) - V2 升级详细说明
- [TESTING_GUIDE.md](TESTING_GUIDE.md) - 测试指南与常见问题
- [FIRST_USE_GUIDE.md](FIRST_USE_GUIDE.md) - 第一次使用指南
- [Project_updates_records.md](Project_updates_records.md) - 本文档

---

**记录维护建议**：后续更新请按时间倒序追加到本文档顶部，格式参考"2026/6/9 14:00 UI 更新适配 V2"章节。