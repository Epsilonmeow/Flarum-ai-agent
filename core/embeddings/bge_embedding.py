"""
BGE-M3 Embedding 实现
支持本地模型或 API 调用
"""

import time
import logging
from typing import List, Optional
import numpy as np

from .base_embedding import BaseEmbedding, EmbeddingResult

logger = logging.getLogger(__name__)


class BGEEmbedding(BaseEmbedding):
    """
    BGE-M3 Embedding 模型
    
    特性：
    - 多语言支持（中英日韩等）
    - 向量维度：1024
    - 最大长度：8192 tokens
    """
    
    model_name = "BAAI/bge-m3"
    dimensions = 1024
    max_tokens = 8192
    
    def __init__(
        self,
        model_path: Optional[str] = None,
        use_local: bool = False,
        device: str = "cpu",
        normalize_embeddings: bool = True,
        **kwargs
    ):
        """
        初始化
        
        Args:
            model_path: 本地模型路径（如果使用本地）
            use_local: 是否使用本地模型
            device: 设备（cpu/cuda）
            normalize_embeddings: 是否归一化向量
        """
        super().__init__(**kwargs)
        
        self.model_path = model_path
        self.use_local = use_local
        self.device = device
        self.normalize_embeddings = normalize_embeddings
        
        self._model = None
        self._tokenizer = None
        
        if use_local and model_path:
            self._init_local_model()
    
    def _init_local_model(self):
        """初始化本地模型"""
        try:
            # 尝试导入 transformers
            from transformers import AutoTokenizer, AutoModel
            
            logger.info(f"🔄 加载 BGE-M3 本地模型: {self.model_path}")
            
            self._tokenizer = AutoTokenizer.from_pretrained(self.model_path)
            self._model = AutoModel.from_pretrained(self.model_path)
            self._model.to(self.device)
            self._model.eval()
            
            self._is_initialized = True
            logger.info("✅ BGE-M3 本地模型加载完成")
            
        except ImportError:
            logger.error("❌ 需要安装 transformers: pip install transformers")
            raise
        except Exception as e:
            logger.error(f"❌ BGE-M3 模型加载失败: {e}")
            raise
    
    async def embed(self, text: str, **kwargs) -> Optional[EmbeddingResult]:
        """
        嵌入单条文本
        
        Args:
            text: 输入文本
            **kwargs: 额外参数
            
        Returns:
            Optional[EmbeddingResult]: 结果
        """
        start_time = time.time()
        
        try:
            if self.use_local:
                embedding = await self._embed_local(text, **kwargs)
            else:
                # API 调用（需要实现）
                embedding = await self._embed_api(text, **kwargs)
            
            if embedding is None:
                return None
            
            latency = (time.time() - start_time) * 1000
            
            return EmbeddingResult(
                embedding=embedding,
                text=text,
                model=self.model_name,
                dimensions=self.dimensions,
                normalized=self.normalize_embeddings,
                latency_ms=latency
            )
            
        except Exception as e:
            logger.error(f"❌ BGE Embedding 失败: {e}")
            return None
    
    async def _embed_local(self, text: str, **kwargs) -> Optional[List[float]]:
        """本地模型推理"""
        import torch
        
        # 截断文本
        text = self.truncate_text(text)
        
        # Tokenize
        encoded = self._tokenizer(
            text,
            padding=True,
            truncation=True,
            max_length=self.max_tokens,
            return_tensors="pt"
        )
        
        # 移动到设备
        encoded = {k: v.to(self.device) for k, v in encoded.items()}
        
        # 推理
        with torch.no_grad():
            model_output = self._model(**encoded)
        
        # 使用 CLS token 的 embedding
        embeddings = model_output.last_hidden_state[:, 0]
        
        # 归一化
        if self.normalize_embeddings:
            embeddings = torch.nn.functional.normalize(embeddings, p=2, dim=1)
        
        # 转换为列表
        return embeddings[0].cpu().tolist()
    
    async def _embed_api(self, text: str, **kwargs) -> Optional[List[float]]:
        """
        通过 API 调用（如果可用）
        
        需要配置 API 端点
        """
        # TODO: 实现 API 调用
        logger.warning("BGE API 调用未实现，请使用本地模型")
        return None
    
    async def embed_batch(
        self,
        texts: List[str],
        batch_size: int = 32,
        **kwargs
    ) -> List[Optional[EmbeddingResult]]:
        """
        批量嵌入
        
        Args:
            texts: 文本列表
            batch_size: 批大小
            **kwargs: 额外参数
            
        Returns:
            List[Optional[EmbeddingResult]]: 结果列表
        """
        if not self.use_local:
            # 非本地模式，逐个处理
            return [await self.embed(t, **kwargs) for t in texts]
        
        results = []
        
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            batch_results = await self._embed_batch_local(batch, **kwargs)
            results.extend(batch_results)
        
        return results
    
    async def _embed_batch_local(
        self,
        texts: List[str],
        **kwargs
    ) -> List[Optional[EmbeddingResult]]:
        """本地批量推理"""
        import torch
        
        start_time = time.time()
        
        # 截断文本
        texts = [self.truncate_text(t) for t in texts]
        
        # Tokenize
        encoded = self._tokenizer(
            texts,
            padding=True,
            truncation=True,
            max_length=self.max_tokens,
            return_tensors="pt"
        )
        
        # 移动到设备
        encoded = {k: v.to(self.device) for k, v in encoded.items()}
        
        # 推理
        with torch.no_grad():
            model_output = self._model(**encoded)
        
        # 提取 embedding
        embeddings = model_output.last_hidden_state[:, 0]
        
        # 归一化
        if self.normalize_embeddings:
            embeddings = torch.nn.functional.normalize(embeddings, p=2, dim=1)
        
        latency = (time.time() - start_time) * 1000
        avg_latency = latency / len(texts)
        
        # 构建结果
        results = []
        for i, emb in enumerate(embeddings):
            results.append(EmbeddingResult(
                embedding=emb.cpu().tolist(),
                text=texts[i],
                model=self.model_name,
                dimensions=self.dimensions,
                normalized=self.normalize_embeddings,
                latency_ms=avg_latency
            ))
        
        return results
    
    async def is_available(self) -> bool:
        """检查服务是否可用"""
        if self.use_local:
            return self._is_initialized and self._model is not None
        else:
            # API 模式需要检查
            return await super().is_available()
    
    def similarity_search(
        self,
        query_embedding: List[float],
        corpus_embeddings: List[List[float]],
        top_k: int = 5
    ) -> List[tuple]:
        """
        相似度搜索
        
        Args:
            query_embedding: 查询向量
            corpus_embeddings: 语料库向量
            top_k: 返回Top-K
            
        Returns:
            List[tuple]: [(index, score), ...]
        """
        import numpy as np
        
        query = np.array(query_embedding)
        corpus = np.array(corpus_embeddings)
        
        # 计算余弦相似度
        similarities = np.dot(corpus, query) / (
            np.linalg.norm(corpus, axis=1) * np.linalg.norm(query)
        )
        
        # 获取Top-K
        top_indices = np.argsort(similarities)[-top_k:][::-1]
        
        return [(int(i), float(similarities[i])) for i in top_indices]