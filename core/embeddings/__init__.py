"""
双模型 Embedding 系统

支持模型：
- BGE-M3: 跨语言语义检索
- Qwen3: 阿里云 Embedding API
"""

from .base_embedding import BaseEmbedding, EmbeddingResult, embedding_manager
from .bge_embedding import BGEEmbedding
from .qwen_embedding import QwenEmbedding, create_qwen_embedding_v3

__all__ = [
    "BaseEmbedding",
    "EmbeddingResult",
    "embedding_manager",
    "BGEEmbedding",
    "QwenEmbedding",
    "create_qwen_embedding_v3",
]