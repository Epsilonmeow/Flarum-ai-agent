"""
Flarum AI Agent - 核心模块
"""

# Provider 架构
from core.providers import (
    BaseProvider,
    GenerationResult,
    GenerationConfig,
    ProviderManager,
    OpenAIProvider,
    DeepSeekProvider,
    QwenProvider
)

# 单独导入 provider_manager 实例（避免循环导入）
from core.providers.manager import provider_manager

# 三层记忆系统
from core.memory import (
    ConversationBlock,
    LayeredMemory,
    BlockManager,
    SummaryEngine
)

# 好感度系统
from core.affection import (
    AffectionManager,
    AffectionLevel,
    RewardEngine,
    InteractionType
)

# Embedding 系统
from core.embeddings import (
    BaseEmbedding,
    EmbeddingResult,
    BGEEmbedding,
    QwenEmbedding
)

# LLM 引擎
try:
    from core.llm_engine_v2 import LLMEngineV2, generate_reply_v2
    LLM_ENGINE_AVAILABLE = True
except ImportError:
    LLM_ENGINE_AVAILABLE = False

__all__ = [
    # Providers
    "BaseProvider",
    "GenerationResult",
    "GenerationConfig",
    "ProviderManager",
    "provider_manager",
    "OpenAIProvider",
    "DeepSeekProvider",
    "QwenProvider",
    
    # Memory
    "ConversationBlock",
    "LayeredMemory",
    "BlockManager",
    "SummaryEngine",
    
    # Affection
    "AffectionManager",
    "AffectionLevel",
    "RewardEngine",
    "InteractionType",
    
    # Embeddings
    "BaseEmbedding",
    "EmbeddingResult",
    "BGEEmbedding",
    "QwenEmbedding",
    
    # Engine
    "LLM_ENGINE_AVAILABLE",
]

if LLM_ENGINE_AVAILABLE:
    __all__.extend(["LLMEngineV2", "generate_reply_v2"])