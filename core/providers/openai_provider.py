"""
OpenAI 兼容 Provider 实现
支持 OpenAI / DeepSeek / 通义千问等
"""

import time
import logging
from typing import Optional, List, Dict, Any
import httpx

from openai import AsyncOpenAI
from .base import BaseProvider, GenerationResult, GenerationConfig, FinishReason, ProviderError

logger = logging.getLogger(__name__)


class OpenAIProvider(BaseProvider):
    """
    OpenAI 格式兼容 Provider
    
    支持:
    - OpenAI 官方 API
    - DeepSeek
    - 通义千问
    - 任何 OpenAI 兼容端点
    """
    
    provider_type = "openai_compatible"
    supports_vision = False
    supports_tools = True
    supports_thinking = True  # DeepSeek-R1 等支持
    
    DEFAULT_MODELS = [
        "gpt-3.5-turbo",
        "gpt-4",
        "gpt-4-turbo",
        "deepseek-chat",
        "deepseek-reasoner",
        "qwen-turbo",
        "qwen-plus",
    ]
    
    def __init__(
        self,
        api_key: str,
        base_url: Optional[str] = "https://api.openai.com/v1",
        model: str = "gpt-3.5-turbo",
        timeout: float = 60.0,
        **kwargs
    ):
        super().__init__(api_key, base_url)
        self.model = model
        self.timeout = timeout
        self._client: Optional[AsyncOpenAI] = None
    
    async def _get_client(self) -> AsyncOpenAI:
        """获取或创建客户端"""
        if self._client is None:
            self._client = AsyncOpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
                timeout=self.timeout,
                http_client=httpx.AsyncClient(
                    limits=httpx.Limits(max_keepalive_connections=5, max_connections=10)
                )
            )
        return self._client
    
    async def is_available(self) -> bool:
        """检查服务是否可用"""
        try:
            client = await self._get_client()
            # 简单检查：获取模型列表
            await client.models.list()
            return True
        except Exception as e:
            logger.warning(f"Provider不可用: {str(e)}")
            return False
    
    async def generate(
        self,
        messages: List[Dict[str, Any]],
        config: Optional[GenerationConfig] = None,
        **kwargs
    ) -> GenerationResult:
        """生成回复"""
        start_time = time.time()
        config = config or GenerationConfig()
        
        try:
            client = await self._get_client()
            
            response = await client.chat.completions.create(
                model=self.model,
                messages=messages,
                **config.to_openai_config()
            )
            
            latency_ms = (time.time() - start_time) * 1000
            
            # 提取内容
            choice = response.choices[0]
            raw_content = choice.message.content or ""
            
            # 提取思考链（DeepSeek等）
            thinking_content = getattr(choice.message, "reasoning_content", None)
            
            # 判断结束原因
            finish_reason_map = {
                "stop": FinishReason.STOP,
                "length": FinishReason.MAX_TOKENS,
                "content_filter": FinishReason.SAFETY,
            }
            finish_reason = finish_reason_map.get(
                choice.finish_reason, FinishReason.UNKNOWN
            )
            
            # Token统计
            usage = response.usage
            tokens_used = usage.total_tokens if usage else None
            input_tokens = usage.prompt_tokens if usage else None
            output_tokens = usage.completion_tokens if usage else None
            
            return GenerationResult(
                content=raw_content,  # 外层会应用Output Regex
                raw_content=raw_content,
                model_used=self.model,
                tokens_used=tokens_used,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                finish_reason=finish_reason,
                thinking_content=thinking_content,
                latency_ms=latency_ms
            )
            
        except Exception as e:
            logger.exception(f"生成失败: {str(e)}")
            raise ProviderError(f"生成失败: {str(e)}")
    
    async def generate_embedding(self, text: str, **kwargs) -> Optional[List[float]]:
        """生成嵌入向量"""
        try:
            client = await self._get_client()
            model = kwargs.get("model", "text-embedding-3-small")
            
            response = await client.embeddings.create(
                model=model,
                input=text
            )
            
            return response.data[0].embedding if response.data else None
            
        except Exception as e:
            logger.error(f"Embedding生成失败: {str(e)}")
            return None
    
    async def close(self):
        """关闭连接"""
        if self._client:
            await self._client.close()
            self._client = None


class DeepSeekProvider(OpenAIProvider):
    """DeepSeek专用Provider"""
    
    provider_type = "deepseek"
    supports_thinking = True
    
    def __init__(self, api_key: str, model: str = "deepseek-chat", **kwargs):
        super().__init__(
            api_key=api_key,
            base_url="https://api.deepseek.com/v1",
            model=model,
            **kwargs
        )


class QwenProvider(OpenAIProvider):
    """通义千问专用Provider"""
    
    provider_type = "qwen"
    
    def __init__(self, api_key: str, model: str = "qwen-turbo", **kwargs):
        super().__init__(
            api_key=api_key,
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            model=model,
            **kwargs
        )