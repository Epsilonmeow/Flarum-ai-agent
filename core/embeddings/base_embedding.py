"""
Embedding 基类
定义统一的 Embedding 接口
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)


@dataclass
class EmbeddingResult:
    """
    Embedding 结果
    
    Attributes:
        embedding: 向量列表
        text: 原始文本
        model: 使用的模型
        dimensions: 向量维度
        normalized: 是否已归一化
        latency_ms: 延迟（毫秒）
        metadata: 额外元数据
    """
    
    embedding: List[float]
    text: str
    model: str
    dimensions: int
    normalized: bool = False
    latency_ms: Optional[float] = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
    
    def cosine_similarity(self, other: "EmbeddingResult") -> float:
        """
        计算与另一个向量的余弦相似度
        
        Args:
            other: 另一个 EmbeddingResult
            
        Returns:
            float: 相似度 (-1.0 ~ 1.0)
        """
        if self.dimensions != other.dimensions:
            raise ValueError(f"维度不匹配: {self.dimensions} vs {other.dimensions}")
        
        import math
        
        # 计算点积
        dot_product = sum(a * b for a, b in zip(self.embedding, other.embedding))
        
        # 计算模长
        norm_a = math.sqrt(sum(x * x for x in self.embedding))
        norm_b = math.sqrt(sum(x * x for x in other.embedding))
        
        if norm_a == 0 or norm_b == 0:
            return 0.0
        
        return dot_product / (norm_a * norm_b)
    
    def euclidean_distance(self, other: "EmbeddingResult") -> float:
        """
        计算与另一个向量的欧氏距离
        
        Args:
            other: 另一个 EmbeddingResult
            
        Returns:
            float: 距离（越小越相似）
        """
        if self.dimensions != other.dimensions:
            raise ValueError(f"维度不匹配: {self.dimensions} vs {other.dimensions}")
        
        return sum((a - b) ** 2 for a, b in zip(self.embedding, other.embedding)) ** 0.5


class BaseEmbedding(ABC):
    """
    Embedding 基类
    
    所有 Embedding 实现必须继承此类
    """
    
    # 模型信息
    model_name: str = "base"
    dimensions: int = 768
    max_tokens: int = 512
    
    def __init__(self, **kwargs):
        self._is_initialized = False
        self.config = kwargs
    
    @abstractmethod
    async def embed(self, text: str, **kwargs) -> Optional[EmbeddingResult]:
        """
        将文本转换为向量
        
        Args:
            text: 输入文本
            **kwargs: 额外参数
            
        Returns:
            Optional[EmbeddingResult]: 结果
        """
        pass
    
    @abstractmethod
    async def embed_batch(
        self,
        texts: List[str],
        **kwargs
    ) -> List[Optional[EmbeddingResult]]:
        """
        批量嵌入
        
        Args:
            texts: 文本列表
            **kwargs: 额外参数
            
        Returns:
            List[Optional[EmbeddingResult]]: 结果列表
        """
        pass
    
    async def is_available(self) -> bool:
        """
        检查服务是否可用
        
        Returns:
            bool: 是否可用
        """
        try:
            result = await self.embed("test")
            return result is not None
        except Exception as e:
            logger.debug(f"Embedding 服务不可用: {e}")
            return False
    
    def truncate_text(self, text: str, max_chars: Optional[int] = None) -> str:
        """
        截断文本以符合模型限制
        
        Args:
            text: 原始文本
            max_chars: 最大字符数（默认 self.max_tokens * 4）
            
        Returns:
            str: 截断后的文本
        """
        max_chars = max_chars or self.max_tokens * 4
        
        if len(text) <= max_chars:
            return text
        
        # 智能截断：尽量在句子边界截断
        truncated = text[:max_chars]
        
        # 寻找最后一个句号、问号或感叹号
        for punct in ["。", "？", "！", ".", "?", "!"]:
            last_punct = truncated.rfind(punct)
            if last_punct > max_chars * 0.5:  # 至少保留一半内容
                return truncated[:last_punct + 1]
        
        return truncated
    
    def normalize_vector(self, vector: List[float]) -> List[float]:
        """
        归一化向量
        
        Args:
            vector: 原始向量
            
        Returns:
            List[float]: 归一化后的向量
        """
        import math
        
        norm = math.sqrt(sum(x * x for x in vector))
        
        if norm == 0:
            return vector
        
        return [x / norm for x in vector]


class EmbeddingManager:
    """
    Embedding 管理器
    
    管理多个 Embedding 模型，支持故障转移
    """
    
    def __init__(self):
        self.embeddings: Dict[str, BaseEmbedding] = {}
        self.primary: Optional[str] = None
        self.fallback_order: List[str] = []
    
    def register(self, name: str, embedding: BaseEmbedding, is_primary: bool = False):
        """
        注册 Embedding 模型
        
        Args:
            name: 名称
            embedding: Embedding 实例
            is_primary: 是否为主模型
        """
        self.embeddings[name] = embedding
        
        if is_primary or self.primary is None:
            self.primary = name
        
        if name not in self.fallback_order:
            self.fallback_order.append(name)
        
        logger.info(f"✅ 注册 Embedding 模型: {name} (primary={is_primary})")
    
    async def embed(
        self,
        text: str,
        preferred_model: Optional[str] = None,
        **kwargs
    ) -> Optional[EmbeddingResult]:
        """
        嵌入文本，支持故障转移
        
        Args:
            text: 文本
            preferred_model: 优先使用的模型
            **kwargs: 额外参数
            
        Returns:
            Optional[EmbeddingResult]: 结果
        """
        # 确定尝试顺序
        if preferred_model and preferred_model in self.fallback_order:
            order = [preferred_model] + [m for m in self.fallback_order if m != preferred_model]
        else:
            order = self.fallback_order
        
        errors = []
        
        for name in order:
            embedding = self.embeddings.get(name)
            if not embedding:
                continue
            
            try:
                if not await embedding.is_available():
                    continue
                
                result = await embedding.embed(text, **kwargs)
                if result:
                    result.metadata["model_used"] = name
                    return result
            except Exception as e:
                logger.warning(f"❌ Embedding 模型 {name} 失败: {e}")
                errors.append(f"{name}: {str(e)}")
                continue
        
        logger.error(f"❌ 所有 Embedding 模型都失败: {'; '.join(errors)}")
        return None
    
    async def embed_batch(
        self,
        texts: List[str],
        preferred_model: Optional[str] = None,
        **kwargs
    ) -> List[Optional[EmbeddingResult]]:
        """
        批量嵌入
        
        Args:
            texts: 文本列表
            preferred_model: 优先使用的模型
            **kwargs: 额外参数
            
        Returns:
            List[Optional[EmbeddingResult]]: 结果列表
        """
        # 确定使用的模型
        model_name = preferred_model or self.primary
        embedding = self.embeddings.get(model_name)
        
        if not embedding:
            # 逐个使用故障转移
            return [await self.embed(t, **kwargs) for t in texts]
        
        try:
            return await embedding.embed_batch(texts, **kwargs)
        except Exception as e:
            logger.error(f"❌ 批量嵌入失败 ({model_name}): {e}")
            # 降级为逐个处理
            return [await self.embed(t, **kwargs) for t in texts]
    
    def get_info(self) -> Dict[str, Any]:
        """获取所有模型信息"""
        return {
            name: {
                "model_name": emb.model_name,
                "dimensions": emb.dimensions,
                "max_tokens": emb.max_tokens
            }
            for name, emb in self.embeddings.items()
        }


# 全局管理器实例
embedding_manager = EmbeddingManager()