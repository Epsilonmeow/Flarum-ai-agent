"""
系统初始化脚本
注册 Providers、Embedding 模型等
"""

import asyncio
import logging
from pathlib import Path

import config

# 直接从 manager 模块导入，避免循环导入
from core.providers.manager import provider_manager
from core.providers.openai_provider import OpenAIProvider, DeepSeekProvider, QwenProvider

from core.embeddings.base_embedding import embedding_manager
from core.embeddings.qwen_embedding import create_qwen_embedding_v3
from core.embeddings.bge_embedding import BGEEmbedding

logging.basicConfig(level=getattr(logging, config.LOG_LEVEL))
logger = logging.getLogger(__name__)


def init_providers():
    """
    初始化 Provider 管理器
    从配置注册所有启用的 Provider
    """
    logger.info("🚀 初始化 Provider 管理器...")
    
    # 如果有配置，从配置加载
    if config.PROVIDER_CONFIGS:
        logger.info(f"📋 从配置加载 {len(config.PROVIDER_CONFIGS)} 个 Provider")
        provider_manager.register_from_config(config.PROVIDER_CONFIGS)
    else:
        # 默认配置：使用环境变量的单 Provider
        logger.info("⚙️ 使用默认 Provider 配置")
        
        # 尝试注册默认 Provider
        if config.LLM_API_KEY and config.LLM_API_KEY != "your-api-key-here":
            # 根据 base_url 判断类型
            base_url = config.LLM_BASE_URL.lower()
            
            if "deepseek" in base_url:
                provider = DeepSeekProvider(
                    api_key=config.LLM_API_KEY,
                    model=config.LLM_MODEL
                )
                provider_manager.register_provider("deepseek", provider, is_primary=True)
            elif "qwen" in base_url or "aliyun" in base_url:
                provider = QwenProvider(
                    api_key=config.LLM_API_KEY,
                    model=config.LLM_MODEL
                )
                provider_manager.register_provider("qwen", provider, is_primary=True)
            else:
                provider = OpenAIProvider(
                    api_key=config.LLM_API_KEY,
                    base_url=config.LLM_BASE_URL,
                    model=config.LLM_MODEL
                )
                provider_manager.register_provider("default", provider, is_primary=True)
    
    logger.info(f"✅ Provider 初始化完成: {len(provider_manager.providers)} 个")


async def init_embeddings():
    """
    初始化 Embedding 管理器
    """
    logger.info("🔤 初始化 Embedding 管理器...")
    
    # 注册 Qwen Embedding（如果有 API Key）
    if config.DASHSCOPE_API_KEY:
        try:
            qwen_emb = create_qwen_embedding_v3(config.DASHSCOPE_API_KEY)
            embedding_manager.register("qwen", qwen_emb, is_primary=True)
            logger.info("✅ Qwen Embedding 注册成功")
        except Exception as e:
            logger.warning(f"⚠️ Qwen Embedding 注册失败: {e}")
    
    # 注册 BGE Embedding（如果是本地模式）
    if config.BGE_MODEL_PATH:
        try:
            bge_emb = BGEEmbedding(
                model_path=config.BGE_MODEL_PATH,
                use_local=True,
                device="cpu"
            )
            embedding_manager.register(
                "bge",
                bge_emb,
                is_primary=(not config.DASHSCOPE_API_KEY)
            )
            logger.info("✅ BGE Embedding 注册成功")
        except Exception as e:
            logger.warning(f"⚠️ BGE Embedding 注册失败: {e}")
    
    logger.info(f"✅ Embedding 初始化完成: {len(embedding_manager.embeddings)} 个")


async def init_directories():
    """创建必要的目录"""
    dirs = [
        config.DATA_DIR,
        config.MEMORY_STORAGE_DIR,
        config.AFFECTION_STORAGE_DIR,
        config.CHROMA_DB_PATH
    ]
    
    for dir_path in dirs:
        dir_path.mkdir(parents=True, exist_ok=True)
    
    logger.info(f"✅ 目录初始化完成: {len(dirs)} 个")


async def health_check():
    """健康检查"""
    logger.info("🏥 执行健康检查...")
    
    # 检查 Providers
    provider_health = await provider_manager.health_check()
    for name, available in provider_health.items():
        status = "✅ 可用" if available else "❌ 不可用"
        logger.info(f"  Provider {name}: {status}")
    
    # 检查 Embeddings
    for name, emb in embedding_manager.embeddings.items():
        available = await emb.is_available()
        status = "✅ 可用" if available else "❌ 不可用"
        logger.info(f"  Embedding {name}: {status}")


async def main():
    """主初始化流程"""
    logger.info("=" * 50)
    logger.info("Flarum AI Agent 系统初始化")
    logger.info("=" * 50)
    
    # 1. 创建目录
    await init_directories()
    
    # 2. 初始化 Providers
    init_providers()
    
    # 3. 初始化 Embeddings
    await init_embeddings()
    
    # 4. 健康检查
    await health_check()
    
    logger.info("=" * 50)
    logger.info("✅ 系统初始化完成")
    logger.info("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())