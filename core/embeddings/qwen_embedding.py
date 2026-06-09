"""
Qwen3 Embedding 实现
通过阿里云 API 调用
"""

import time
import logging
from typing import List, Optional

from .base_embedding import BaseEmbedding, EmbeddingResult

logger = logging.getLogger(__name__)


class QwenEmbedding(BaseEmbedding):
    """
    通义千问 Embedding API
    
    特性：
    - 通过阿里云 DashScope API 调用
    - 向量维度：1536
    - 最大长度：2048 tokens
    - 模型：text-embedding-v2/v3
    """
    
    model_name = "text-embedding-v3"
    dimensions = 1536
    max_tokens = 2048
    
    # API 端点
    DASHSCOPE_API_URL = "https://dashscope.aliyuncs.com/api/v1/embeddings"
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "text-embedding-v3",
        **kwargs
    ):
        """
        初始化
        
        Args:
            api_key: DashScope API Key
            model: 模型名称 (text-embedding-v2/v3)
        """
        super().__init__(**kwargs)
        
        self.api_key = api_key
        self.model = model
        
        # 根据模型设置维度
        if "v2" in model:
            self.dimensions = 1536
        elif "v3" in model:
            self.dimensions = 1024
        else:
            self.dimensions = 1536  # 默认
        
        self.model_name = f"qwen/{model}"
        self._client = None
    
    def _init_client(self):
        """初始化 HTTP 客户端"""
        try:
            import httpx
            self._client = httpx.AsyncClient(
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                timeout=30.0
            )
            self._is_initialized = True
        except ImportError:
            logger.error("❌ 需要安装 httpx: pip install httpx")
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
        if not self._is_initialized:
            self._init_client()
        
        if not self.api_key:
            logger.error("❌ 未配置 Qwen API Key")
            return None
        
        start_time = time.time()
        
        try:
            # 截断文本
            text = self.truncate_text(text)
            
            # 调用 API
            response = await self._client.post(
                self.DASHSCOPE_API_URL,
                json={
                    "model": self.model,
                    "input": {
                        "texts": [text]
                    },
                    "parameters": {
                        "text_type": "document"
                    }
                }
            )
            
            response.raise_for_status()
            data = response.json()
            
            # 解析结果
            if "output" in data and "embeddings" in data["output"]:
                embedding_data = data["output"]["embeddings"][0]
                embedding = embedding_data["embedding"]
                
                latency = (time.time() - start_time) * 1000
                
                return EmbeddingResult(
                    embedding=embedding,
                    text=text,
                    model=self.model_name,
                    dimensions=len(embedding),
                    normalized=True,  # API 返回已归一化
                    latency_ms=latency
                )
            else:
                logger.error(f"❌ Qwen API 返回格式错误: {data}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Qwen Embedding 失败: {e}")
            return None
    
    async def embed_batch(
        self,
        texts: List[str],
        batch_size: int = 25,  # API 限制
        **kwargs
    ) -> List[Optional[EmbeddingResult]]:
        """
        批量嵌入
        
        Args:
            texts: 文本列表
            batch_size: 批大小（API限制25条）
            **kwargs: 额外参数
            
        Returns:
            List[Optional[EmbeddingResult]]: 结果列表
        """
        if not self._is_initialized:
            self._init_client()
        
        results = []
        
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            batch_results = await self._embed_batch_api(batch, **kwargs)
            results.extend(batch_results)
        
        return results
    
    async def _embed_batch_api(
        self,
        texts: List[str],
        **kwargs
    ) -> List[Optional[EmbeddingResult]]:
        """批量 API 调用"""
        try:
            # 截断文本
            texts = [self.truncate_text(t) for t in texts]
            
            start_time = time.time()
            
            response = await self._client.post(
                self.DASHSCOPE_API_URL,
                json={
                    "model": self.model,
                    "input": {
                        "texts": texts
                    },
                    "parameters": {
                        "text_type": "document"
                    }
                }
            )
            
            response.raise_for_status()
            data = response.json()
            
            latency = (time.time() - start_time) * 1000
            avg_latency = latency / len(texts)
            
            # 解析结果
            if "output" in data and "embeddings" in data["output"]:
                embeddings_data = data["output"]["embeddings"]
                
                results = []
                for i, emb_data in enumerate(embeddings_data):
                    embedding = emb_data["embedding"]
                    results.append(EmbeddingResult(
                        embedding=embedding,
                        text=texts[i],
                        model=self.model_name,
                        dimensions=len(embedding),
                        normalized=True,
                        latency_ms=avg_latency
                    ))
                
                return results
            else:
                logger.error(f"❌ Qwen API 批量返回格式错误: {data}")
                return [None] * len(texts)
                
        except Exception as e:
            logger.error(f"❌ Qwen 批量 Embedding 失败: {e}")
            return [None] * len(texts)
    
    async def is_available(self) -> bool:
        """检查服务是否可用"""
        if not self.api_key:
            return False
        
        try:
            result = await self.embed("test")
            return result is not None
        except Exception as e:
            logger.debug(f"Qwen Embedding 不可用: {e}")
            return False
    
    async def close(self):
        """关闭客户端"""
        if self._client:
            await self._client.aclose()
            self._client = None


# 便捷的模型选择函数

def create_qwen_embedding_v2(api_key: str) -> QwenEmbedding:
    """
    创建 Qwen Embedding V2
    
    Args:
        api_key: DashScope API Key
        
    Returns:
        QwenEmbedding: 实例
    """
    return QwenEmbedding(
        api_key=api_key,
        model="text-embedding-v2"
    )


def create_qwen_embedding_v3(api_key: str) -> QwenEmbedding:
    """
    创建 Qwen Embedding V3
    
    Args:
        api_key: DashScope API Key
        
    Returns:
        QwenEmbedding: 实例
    """
    return QwenEmbedding(
        api_key=api_key,
        model="text-embedding-v3"
    )