"""
使用示例 - Flarum AI Agent V2

展示如何使用新的三层记忆系统和好感度系统
"""

import asyncio
import logging
from pathlib import Path

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def example_1_basic_memory():
    """
    示例1: 基础三层记忆系统使用
    """
    print("\n" + "="*50)
    print("示例1: 基础三层记忆系统")
    print("="*50)
    
    from core.memory import LayeredMemory
    
    # 初始化记忆系统
    memory = LayeredMemory(Path("./data/example_memory"))
    
    user_id = "user_001"
    
    # 模拟对话
    conversations = [
        ("你好，我最近压力很大", "你好！听起来你最近压力很大，想聊聊吗？"),
        ("是的，期末考试快到了，我很焦虑", "理解你的焦虑。考试确实会带来压力，你准备得怎么样了？"),
        ("我准备得不太好，感觉自己会挂科", "别太担心，现在还来得及。制定一个复习计划，一步一步来。"),
    ]
    
    for user_msg, ai_msg in conversations:
        # 添加用户消息
        await memory.add_message(user_id, "user", user_msg)
        # 添加AI回复
        await memory.add_message(user_id, "assistant", ai_msg)
        print(f"💬 用户: {user_msg[:30]}...")
        print(f"🤖 AI: {ai_msg[:30]}...")
    
    # 获取记忆统计
    stats = await memory.get_user_stats(user_id)
    print(f"\n📊 用户统计:")
    print(f"  总轮数: {stats['total_turns']}")
    print(f"  总块数: {stats['total_blocks']}")
    
    # 获取Prompt可用的记忆
    prompt_memory = await memory.get_memory_for_prompt(user_id)
    print(f"\n📝 Prompt 记忆:")
    print(f"  有摘要: {bool(prompt_memory['summaries'])}")
    print(f"  近期消息数: {len(prompt_memory['recent_context'])}")


async def example_2_affection_system():
    """
    示例2: 好感度系统使用
    """
    print("\n" + "="*50)
    print("示例2: 好感度系统")
    print("="*50)
    
    from core.affection import AffectionManager
    
    # 初始化好感度系统
    affection = AffectionManager(Path("./data/example_affection"))
    
    user_id = "user_002"
    
    # 模拟互动
    interactions = [
        ("你好", "normal"),
        ("谢谢你帮我", "thanks"),
        ("我今天很难过", "emotional_support"),
    ]
    
    for msg, msg_type in interactions:
        # 添加好感度
        result = await affection.add_affection(
            user_id,
            points=5 if msg_type == "thanks" else 3,
            interaction_type=msg_type
        )
        print(f"❤️ 互动类型: {msg_type}")
        print(f"   得分: +{result['points_added']}")
        print(f"   当前好感度: {result['new_score']}")
        print(f"   等级: {result['new_level'].label}")
        if result.get('level_up'):
            print(f"   🎉 等级提升！")
    
    # 获取好感度摘要
    summary = await affection.get_affection_summary(user_id)
    print(f"\n📊 好感度摘要:")
    print(f"  当前等级: {summary['level_label']}")
    print(f"  进度: {summary['level_progress']*100:.1f}%")
    print(f"  总互动: {summary['total_interactions']}")


async def example_3_reward_system():
    """
    示例3: 互动奖励系统
    """
    print("\n" + "="*50)
    print("示例3: 互动奖励系统")
    print("="*50)
    
    from core.affection import AffectionManager, RewardEngine
    
    # 初始化
    affection = AffectionManager(Path("./data/example_affection"))
    reward = RewardEngine(affection)
    
    user_id = "user_003"
    
    # 模拟不同类型的互动
    test_messages = [
        "谢谢你的帮助！",  # 感谢型
        "我最近压力好大，不知道怎么办",  # 情感支持型
        "嗯",  # 闲聊型
    ]
    
    for msg in test_messages:
        # 分析互动
        analysis = await reward.analyze_interaction(
            user_id=user_id,
            user_message=msg,
            ai_message="这是我的回复",
            conversation_turn=1
        )
        print(f"\n📝 用户消息: {msg}")
        print(f"   互动类型: {analysis['interaction_type']}")
        print(f"   奖励分数: {analysis['points']}")
        print(f"   内容分析: {analysis['content_analysis']}")


async def example_4_embedding():
    """
    示例4: Embedding 使用
    """
    print("\n" + "="*50)
    print("示例4: Embedding 系统")
    print("="*50)
    
    import config
    from core.embeddings import embedding_manager, QwenEmbedding
    
    # 如果有 API Key，注册 Qwen Embedding
    if config.DASHSCOPE_API_KEY:
        qwen_emb = QwenEmbedding(api_key=config.DASHSCOPE_API_KEY)
        embedding_manager.register("qwen", qwen_emb, is_primary=True)
        print("✅ Qwen Embedding 注册成功")
    
    # 显示可用模型
    info = embedding_manager.get_info()
    print(f"\n📊 可用 Embedding 模型:")
    for name, model_info in info.items():
        print(f"  {name}: {model_info['model_name']} ({model_info['dimensions']}维)")


async def example_5_full_pipeline():
    """
    示例5: 完整流程（需要配置 API Key）
    """
    print("\n" + "="*50)
    print("示例5: 完整对话流程")
    print("="*50)
    
    import config
    
    # 检查是否有 API Key
    if config.LLM_API_KEY == "your-api-key-here":
        print("⚠️ 请先配置 LLM_API_KEY 环境变量")
        print("   跳过此示例")
        return
    
    from core.llm_engine_v2 import LLMEngineV2
    
    from core.providers.manager import provider_manager
    
    # 初始化引擎（使用已注册的 provider_manager）
    engine = LLMEngineV2(provider_manager=provider_manager)
    
    user_id = "user_demo"
    user_message = "你好，我今天心情不太好"
    
    print(f"\n💬 用户: {user_message}")
    print("🤖 生成回复中...")
    
    try:
        # 生成回复
        result = await engine.generate(
            user_id=user_id,
            user_message=user_message,
            temperature=0.7,
            max_tokens=200
        )
        
        print(f"\n🤖 AI回复: {result['reply']}")
        print(f"\n📊 生成信息:")
        print(f"  使用模型: {result['model']}")
        print(f"  Token数: {result['tokens']}")
        print(f"  包含摘要: {result['context']['summaries_included']}")
        print(f"  上下文消息: {result['context']['recent_messages']}")
        
        if 'reward' in result:
            print(f"\n❤️ 好感度:")
            reward_info = result['reward']
            if 'affection_summary' in reward_info:
                summary = reward_info['affection_summary']
                print(f"  当前等级: {summary['level_label']}")
                print(f"  好感度: {summary['score']}")
        
    except Exception as e:
        print(f"❌ 生成失败: {e}")


async def main():
    """运行所有示例"""
    print("="*50)
    print("Flarum AI Agent V2 使用示例")
    print("="*50)
    
    # 先初始化系统（注册 Provider）
    print("\n🚀 初始化系统...")
    from init_system import init_providers, init_directories
    await init_directories()
    init_providers()
    print("✅ 系统初始化完成\n")
    
    # 示例1: 基础记忆系统
    await example_1_basic_memory()
    
    # 示例2: 好感度系统
    await example_2_affection_system()
    
    # 示例3: 奖励系统
    await example_3_reward_system()
    
    # 示例4: Embedding
    await example_4_embedding()
    
    # 示例5: 完整流程（可选）
    await example_5_full_pipeline()
    
    print("\n" + "="*50)
    print("所有示例运行完成！")
    print("="*50)


if __name__ == "__main__":
    asyncio.run(main())