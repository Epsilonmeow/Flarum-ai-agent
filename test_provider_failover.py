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