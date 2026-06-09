# 🧪 Flarum AI Agent V2 测试指南

## 📋 测试前准备

### 1. 环境检查

确保以下文件已存在：
```bash
# 核心文件
core/providers/base.py              # Provider基类
core/providers/manager.py           # Provider管理器
core/memory/layered_memory.py       # 三层记忆系统
core/affection/affection_manager.py # 好感度系统
core/llm_engine_v2.py               # 新引擎
config.py                           # 更新后的配置

# 工具文件
init_system.py                      # 初始化脚本
example_usage.py                    # 使用示例
```

### 2. 配置环境变量

编辑 `.env` 文件（在项目根目录创建）：

```env
# ==========================================
# 必需配置
# ==========================================

# LLM API配置（至少填一个）
LLM_API_KEY=your-api-key-here
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-3.5-turbo

# 或 DeepSeek
# LLM_BASE_URL=https://api.deepseek.com/v1
# LLM_MODEL=deepseek-chat

# 或通义千问
# LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
# LLM_MODEL=qwen-turbo

# Flarum论坛配置（用于实际发帖）
FLARUM_BASE_URL=https://your-forum.com
FLARUM_API_TOKEN=your-flarum-token

# ==========================================
# V2新配置（可选，用于测试高级功能）
# ==========================================

# Embedding（用于语义检索）
DASHSCOPE_API_KEY=your-dashscope-key

# 好感度系统
DAILY_BONUS_POINTS=5
CONSECUTIVE_BONUS_POINTS=10

# 记忆系统
MEMORY_BLOCK_SIZE=10
SUMMARY_TRIGGER_THRESHOLD=2
```

### 3. 安装依赖

```bash
pip install -r requirements.txt

# 如果使用本地BGE模型，额外安装
pip install transformers torch numpy
```

---

## 🚀 开始测试

### 测试步骤1：初始化系统

```bash
python init_system.py
```

**预期输出：**
```
==================================================
Flarum AI Agent 系统初始化
==================================================
✅ 目录初始化完成: 4 个
🚀 初始化 Provider 管理器...
✅ Provider 初始化完成: 1 个
🔤 初始化 Embedding 管理器...
✅ Embedding 初始化完成: 0 个
🏥 执行健康检查...
  Provider default: ✅ 可用
==================================================
✅ 系统初始化完成
==================================================
```

**如果出现错误：**
- `ModuleNotFoundError`: 运行 `pip install -r requirements.txt`
- `NameError`: 检查 `config.py` 是否有 `from typing import Optional`
- API错误: 检查 `.env` 中的 API Key 是否正确

---

### 测试步骤2：运行基础示例

```bash
python example_usage.py
```

**测试内容：**
1. ✅ 三层记忆系统 - 创建对话块、保存消息
2. ✅ 好感度系统 - 加分、升级、成就解锁
3. ✅ 奖励系统 - 互动类型识别、分数计算
4. ✅ Embedding系统 - 模型注册（如有API Key）
5. ✅ 完整流程 - 生成回复（如有API Key）

**预期输出示例：**
```
==================================================
Flarum AI Agent V2 使用示例
==================================================

==================================================
示例1: 基础三层记忆系统
==================================================
💬 用户: 你好，我最近压力很大...
🤖 AI: 你好！听起来你最近压力很大...

📊 用户统计:
  总轮数: 3
  总块数: 1

📝 Prompt 记忆:
  有摘要: False
  近期消息数: 6

==================================================
示例2: 好感度系统
==================================================
❤️ 互动类型: normal
   得分: +3
   当前好感度: 3
   等级: 陌生人

...

==================================================
所有示例运行完成！
==================================================
```

---

### 测试步骤3：使用新引擎生成回复

创建测试脚本 `test_v2.py`：

```python
import asyncio
from core.llm_engine_v2 import generate_reply_v2, get_user_profile

async def test_basic():
    """测试基础对话"""
    print("=" * 50)
    print("测试1: 基础对话")
    print("=" * 50)
    
    user_id = "test_user_001"
    
    # 第一轮对话
    reply1 = await generate_reply_v2(
        user_id=user_id,
        user_message="你好，我是新来的",
        temperature=0.7
    )
    print(f"用户: 你好，我是新来的")
    print(f"AI: {reply1[:100]}...\n")
    
    # 第二轮对话（测试记忆）
    reply2 = await generate_reply_v2(
        user_id=user_id,
        user_message="你记得我刚才说了什么吗？",
        temperature=0.7
    )
    print(f"用户: 你记得我刚才说了什么吗？")
    print(f"AI: {reply2[:100]}...\n")
    
    # 查看用户画像
    profile = await get_user_profile(user_id)
    print("📊 用户画像:")
    print(f"  记忆轮数: {profile['memory']['total_turns']}")
    print(f"  好感度: {profile['affection']['score']}")
    print(f"  等级: {profile['affection']['level_label']}")

async def test_affection():
    """测试好感度积累"""
    print("\n" + "=" * 50)
    print("测试2: 好感度积累")
    print("=" * 50)
    
    user_id = "test_user_002"
    
    # 多次互动
    messages = [
        "你好",
        "谢谢你的回复",
        "我今天心情不太好",
        "能和你说说话真好",
        "谢谢你的陪伴",
    ]
    
    for msg in messages:
        reply = await generate_reply_v2(user_id=user_id, user_message=msg)
        print(f"用户: {msg}")
        print(f"AI: {reply[:50]}...\n")
    
    # 查看最终好感度
    profile = await get_user_profile(user_id)
    print(f"❤️ 最终好感度: {profile['affection']['score']}")
    print(f"🏆 等级: {profile['affection']['level_label']}")

async def main():
    await test_basic()
    await test_affection()
    print("\n✅ 所有测试完成!")

if __name__ == "__main__":
    asyncio.run(main())
```

运行测试：
```bash
python test_v2.py
```

---

### 测试步骤4：测试管理界面（Admin UI）

启动管理后台：
```bash
streamlit run admin_ui.py
```

访问 http://localhost:8501

**测试功能：**
1. 系统状态页 - 查看 Provider 健康状态
2. 世界书编辑 - 添加/修改规则
3. 记忆管理 - 查看用户记忆（V2新增）
4. 冷却监控 - 查看用户冷却状态

---

## 🔍 详细功能测试

### 1. Provider 故障转移测试

创建测试脚本 `test_provider_failover.py`：

```python
import asyncio
from core.providers.manager import provider_manager, GenerationConfig

async def test_failover():
    """测试Provider故障转移"""
    
    # 注册两个Provider（一个有效，一个无效）
    from core.providers.openai_provider import OpenAIProvider
    
    # 主Provider（使用错误key测试失败）
    bad_provider = OpenAIProvider(
        api_key="invalid-key",
        model="gpt-3.5-turbo"
    )
    provider_manager.register_provider("bad", bad_provider, is_primary=True)
    
    # 备用Provider（使用正确key）
    good_provider = OpenAIProvider(
        api_key="your-real-api-key",
        model="gpt-3.5-turbo"
    )
    provider_manager.register_provider("good", good_provider)
    
    # 测试生成（应该自动切换到备用）
    messages = [{"role": "user", "content": "你好"}]
    config = GenerationConfig()
    
    try:
        result = await provider_manager.generate(messages, config)
        print(f"✅ 故障转移成功！使用模型: {result.model_used}")
    except Exception as e:
        print(f"❌ 故障转移失败: {e}")

asyncio.run(test_failover())
```

### 2. 三层记忆测试

```python
import asyncio
from core.memory import LayeredMemory
from pathlib import Path

async def test_memory_layers():
    """测试三层记忆"""
    memory = LayeredMemory(Path("./data/test_memory"))
    user_id = "test_memory_user"
    
    # 添加11条消息（触发块完成）
    for i in range(11):
        await memory.add_message(user_id, "user", f"消息{i+1}")
        await memory.add_message(user_id, "assistant", f"回复{i+1}")
    
    # 检查块状态
    stats = await memory.get_user_stats(user_id)
    print(f"总轮数: {stats['total_turns']}")
    print(f"总块数: {stats['total_blocks']}")
    print(f"完整块: {stats['completed_blocks']}")
    
    # 获取Prompt记忆
    prompt_memory = await memory.get_memory_for_prompt(user_id)
    print(f"摘要数: {len(prompt_memory.get('summaries', []))}")
    print(f"近期消息: {len(prompt_memory.get('recent_context', []))}")

asyncio.run(test_memory_layers())
```

### 3. 好感度系统测试

```python
import asyncio
from core.affection import AffectionManager, RewardEngine
from pathlib import Path

async def test_affection_system():
    """测试好感度系统"""
    affection = AffectionManager(Path("./data/test_affection"))
    reward = RewardEngine(affection)
    user_id = "test_affection_user"
    
    # 测试不同类型互动
    test_cases = [
        ("谢谢你的帮助！", "感谢"),
        ("我今天很难过", "情感支持"),
        ("嗯", "闲聊"),
    ]
    
    for msg, desc in test_cases:
        result = await reward.process_interaction(
            user_id=user_id,
            user_message=msg,
            ai_message="这是我的回复",
            conversation_turn=1
        )
        print(f"\n{desc}: {msg}")
        print(f"  类型: {result['interaction_type']}")
        print(f"  得分: {result['points']}")
        print(f"  好感度: {result['affection_summary']['score']}")

asyncio.run(test_affection_system())
```

---

## 📊 测试检查清单

| 测试项 | 状态 | 备注 |
|--------|------|------|
| 系统初始化 | ⬜ | `python init_system.py` |
| 基础示例 | ⬜ | `python example_usage.py` |
| 新引擎对话 | ⬜ | `python test_v2.py` |
| 管理界面 | ⬜ | `streamlit run admin_ui.py` |
| Provider故障转移 | ⬜ | 多Provider配置 |
| 三层记忆 | ⬜ | 11条消息触发块完成 |
| 增量总结 | ⬜ | 2个块触发摘要 |
| 好感度积累 | ⬜ | 5级关系测试 |
| 奖励机制 | ⬜ | 不同类型互动 |
| Embedding | ⬜ | 需要DASHSCOPE_API_KEY |

---

## 🐛 常见问题排查

### Q1: 导入错误 `ModuleNotFoundError`
```bash
# 解决方案
pip install -r requirements.txt
pip install python-dotenv httpx
```

### Q2: `NameError: name 'Optional' is not defined`
```bash
# 检查 config.py 顶部是否有
from typing import Optional
```

### Q3: API调用失败
```bash
# 检查 .env 文件
cat .env | grep LLM_API_KEY

# 测试API连通性
curl -H "Authorization: Bearer $LLM_API_KEY" \
     $LLM_BASE_URL/models
```

### Q4: 记忆没有保存
```bash
# 检查目录权限
ls -la data/

# 手动创建目录
mkdir -p data/memory data/affection
```

### Q5: 好感度没有增加
- 检查是否在同一个用户ID下测试
- 检查 `DAILY_BONUS_POINTS` 配置
- 查看日志输出是否有 `❤️ 好感度更新`

---

## 📈 性能测试

### 并发测试
```bash
# 使用 wrk 或 ab 测试Webhook接口
wrk -t4 -c100 -d30s http://localhost:8000/webhook
```

### 内存测试
```python
# 监控内存使用
import psutil
print(f"内存使用: {psutil.Process().memory_info().rss / 1024 / 1024:.2f} MB")
```

---

## ✅ 测试通过标准

1. **基础功能**: 系统初始化无错误
2. **对话功能**: 能正常生成回复
3. **记忆功能**: 11条消息后能看到块完成
4. **好感度功能**: 5次互动后好感度>0
5. **故障转移**: 主Provider失败时自动切换
6. **管理界面**: 能正常访问和操作

---

## 📝 反馈提交

测试完成后，请提交：
1. 测试检查清单截图
2. 遇到的错误日志
3. 改进建议

提交方式：在项目中创建 Issue 或联系开发团队