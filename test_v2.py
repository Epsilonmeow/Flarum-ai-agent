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