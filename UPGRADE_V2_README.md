# Flarum AI Agent V2 工业级升级说明

## 🎯 升级概览

本次升级实现了完整的工业级架构，参考 Odysseia Guidance 设计理念，采用轻量级实现（JSON/文件存储，无需 PostgreSQL）。

## 📦 新增组件

### Phase 4: 三层记忆系统

| 文件 | 功能 |
|------|------|
| `core/memory/conversation_block.py` | 对话块模型（10轮打包） |
| `core/memory/layered_memory.py` | L1摘要/L2块/L3历史 三层结构 |
| `core/memory/block_manager.py` | 块生命周期管理 |

**架构设计:**
```
L1 摘要层 - 长期记忆（AI总结的历史摘要）
    ↓
L2 块层 - 中期记忆（最近2个完整对话块）
    ↓
L3 历史层 - 短期记忆（当前块的实时消息）
```

### Phase 5: 增量总结策略

| 文件 | 功能 |
|------|------|
| `core/memory/summary_engine.py` | 每2个块触发AI总结 |

**触发条件:**
- 每积累2个完整块触发一次总结
- 生成用户画像摘要
- 提取关键主题和情感趋势

### Phase 6: 双模型 Embedding

| 文件 | 功能 |
|------|------|
| `core/embeddings/base_embedding.py` | Embedding基类 + 管理器 |
| `core/embeddings/bge_embedding.py` | BGE-M3 本地模型 |
| `core/embeddings/qwen_embedding.py` | Qwen3 API 模型 |

**特性:**
- 支持故障转移
- 批量嵌入
- 相似度计算

### Phase 7: 好感度系统

| 文件 | 功能 |
|------|------|
| `core/affection/affection_manager.py` | 好感度计算与存储 |
| `core/affection/rewards.py` | 互动奖励机制 |

**好感度等级:**
| 等级 | 分数范围 | 标签 |
|------|---------|------|
| 陌生人 | 0-19 | 初次相遇 |
| 熟人 | 20-49 | 渐生好感 |
| 朋友 | 50-99 | 温暖陪伴 |
| 好友 | 100-199 | 知心伙伴 |
| 挚友 | 200+ | 灵魂知己 |

**奖励规则:**
- 每日首次互动: +5分
- 连续互动奖励: +10分
- 情感支持: +5分
- 深度交流: +3分
- 感谢: +3分

### Phase 8: 重构 llm_engine.py

| 文件 | 功能 |
|------|------|
| `core/llm_engine_v2.py` | 集成所有新系统的引擎 |

**新特性:**
- ✅ 集成 ProviderManager（多Provider故障转移）
- ✅ 集成三层记忆注入 Prompt
- ✅ 集成好感度提示
- ✅ 完整上下文准备流程
- ✅ 自动生成回复

**主接口:**
```python
from core.llm_engine_v2 import generate_reply_v2

reply = await generate_reply_v2(
    user_id="user_123",
    user_message="你好",
    temperature=0.7,
    max_tokens=500
)
```

### Phase 9: 配置更新

新增配置项（`config.py`）:

```python
# 记忆系统
MEMORY_STORAGE_DIR = DATA_DIR / "memory"
MEMORY_BLOCK_SIZE = 10
SUMMARY_TRIGGER_THRESHOLD = 2
MAX_CONTEXT_MESSAGES = 5

# 好感度系统
AFFECTION_STORAGE_DIR = DATA_DIR / "affection"
DAILY_BONUS_POINTS = 5
CONSECUTIVE_BONUS_POINTS = 10

# Embedding
DEFAULT_EMBEDDING_MODEL = "qwen"
BGE_MODEL_PATH = os.getenv("BGE_MODEL_PATH")
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY")

# Provider
PROVIDER_CONFIGS = []  # JSON格式配置
DEFAULT_PROVIDER_TYPE = "openai"
```

## 🚀 快速开始

### 1. 初始化系统

```bash
python init_system.py
```

### 2. 运行示例

```bash
python example_usage.py
```

### 3. 使用新引擎

```python
import asyncio
from core.llm_engine_v2 import generate_reply_v2

async def main():
    reply = await generate_reply_v2(
        user_id="user_001",
        user_message="你好，最近压力很大",
        temperature=0.7
    )
    print(reply)

asyncio.run(main())
```

## 📁 项目结构

```
Flarum_AI_Agent/
├── core/
│   ├── __init__.py              # 模块导出
│   ├── llm_engine_v2.py         # 新引擎（V2）
│   ├── llm_engine.py            # 旧引擎（兼容）
│   ├── providers/               # Provider架构
│   │   ├── base.py
│   │   ├── manager.py
│   │   └── openai_provider.py
│   ├── memory/                  # 三层记忆系统 ⭐
│   │   ├── __init__.py
│   │   ├── conversation_block.py
│   │   ├── layered_memory.py
│   │   ├── block_manager.py
│   │   └── summary_engine.py
│   ├── embeddings/              # 双模型Embedding ⭐
│   │   ├── __init__.py
│   │   ├── base_embedding.py
│   │   ├── bge_embedding.py
│   │   └── qwen_embedding.py
│   └── affection/               # 好感度系统 ⭐
│       ├── __init__.py
│       ├── affection_manager.py
│       └── rewards.py
├── config.py                    # 更新配置
├── init_system.py               # 初始化脚本
├── example_usage.py             # 使用示例
└── data/
    ├── memory/                  # 记忆存储
    ├── affection/               # 好感度存储
    └── chroma_db/              # 向量数据库
```

## 🔧 环境变量配置

添加到 `.env` 文件:

```env
# LLM API
LLM_API_KEY=your-api-key
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-3.5-turbo

# Embedding
DASHSCOPE_API_KEY=your-dashscope-key
BGE_MODEL_PATH=/path/to/bge-m3

# 记忆系统
MEMORY_BLOCK_SIZE=10
SUMMARY_TRIGGER_THRESHOLD=2

# 好感度系统
DAILY_BONUS_POINTS=5
CONSECUTIVE_BONUS_POINTS=10

# Provider配置（JSON格式）
PROVIDER_CONFIGS=[{"name":"deepseek","type":"deepseek","api_key":"...","model":"...","is_primary":true}]
```

## 🎨 架构图

```
┌─────────────────────────────────────────────────────────────┐
│                    Flarum AI Agent V2                         │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │   Provider   │  │   Provider   │  │   Provider   │       │
│  │  Manager     │  │  (Fallback)  │  │  (Fallback)  │       │
│  └──────┬───────┘  └──────────────┘  └──────────────┘       │
│         │                                                    │
│         ▼                                                    │
│  ┌─────────────────────────────────────────┐                │
│  │         LLMEngine V2                    │                │
│  │  ┌─────────────────────────────────┐    │                │
│  │  │  Context Preparation            │    │                │
│  │  │  - System Prompt                │    │                │
│  │  │  - Memory Injection (L1/L2/L3)  │    │                │
│  │  │  - Affection Hint               │    │                │
│  │  │  - WorldBook Match              │    │                │
│  │  └─────────────────────────────────┘    │                │
│  │                     │                   │                │
│  │                     ▼                   │                │
│  │  ┌─────────────────────────────────┐    │                │
│  │  │  Response Generation            │    │                │
│  │  │  - Multi-Provider Failover      │    │                │
│  │  │  - Token Tracking               │    │                │
│  │  └─────────────────────────────────┘    │                │
│  │                     │                   │                │
│  │                     ▼                   │                │
│  │  ┌─────────────────────────────────┐    │                │
│  │  │  Post-Processing                │    │                │
│  │  │  - Save to Memory               │    │                │
│  │  │  - Update Affection             │    │                │
│  │  │  - Trigger Summary (if needed)  │    │                │
│  │  └─────────────────────────────────┘    │                │
│  └─────────────────────────────────────────┘                │
│                                                              │
├─────────────────────────────────────────────────────────────┤
│  Storage Layer (JSON/Files)                                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │  Memory     │  │  Affection  │  │  WorldBook  │         │
│  │  (L1/L2/L3) │  │  (Levels)   │  │  (Entries)  │         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
└─────────────────────────────────────────────────────────────┘
```

## ✅ 检查清单

- [x] Provider 架构（base + openai_provider + manager）
- [x] 三层记忆系统（conversation_block + layered_memory + block_manager）
- [x] 增量总结策略（summary_engine，每2块触发）
- [x] 双模型 Embedding（bge + qwen）
- [x] 好感度系统（affection_manager + rewards）
- [x] 重构 llm_engine（集成 ProviderManager + 记忆注入）
- [x] 更新 config.py（新增配置项）
- [x] 初始化脚本（init_system.py）
- [x] 使用示例（example_usage.py）

## 📝 下一步建议

1. **测试验证**: 运行 `example_usage.py` 验证所有功能
2. **数据迁移**: 如有旧数据，考虑迁移到新格式
3. **性能优化**: 根据实际使用情况调整块大小和摘要频率
4. **监控告警**: 添加健康检查和告警机制
5. **文档完善**: 根据实际使用补充 API 文档

---

**升级完成！** 🎉