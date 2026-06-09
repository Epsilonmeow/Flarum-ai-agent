"""
AI Provider 基类架构
借鉴 Odysseia 设计，统一多模型接口
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List, Callable
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class FinishReason(Enum):
    """生成结束原因"""
    STOP = "stop"
    MAX_TOKENS = "max_tokens"
    SAFETY = "safety"
    TOOL_CALL = "tool_call"
    ERROR = "error"
    UNKNOWN = "unknown"


@dataclass
class GenerationResult:
    """
    AI 生成结果标准数据类
    
    Attributes:
        content: 生成的文本内容（已应用Output Regex）
        raw_content: 原始响应内容
        model_used: 实际使用的模型名称
        tokens_used: 总token数
        input_tokens: 输入token数
        output_tokens: 输出token数
        finish_reason: 结束原因
        thinking_content: 思考链内容（如DeepSeek的think标签）
        latency_ms: 响应延迟（毫秒）
        timestamp: 生成时间戳
    """
    content: str
    raw_content: str
    model_used: str
    tokens_used: Optional[int] = None
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    finish_reason: FinishReason = FinishReason.STOP
    thinking_content: Optional[str] = None
    latency_ms: Optional[float] = None
    timestamp: Optional[str] = field(default=None)
    
    def __post_init__(self):
        if self.timestamp is None:
            from datetime import datetime
            self.timestamp = datetime.now().isoformat()
    
    @property
    def has_thinking(self) -> bool:
        """是否有思考链内容"""
        return bool(self.thinking_content and self.thinking_content.strip())


@dataclass
class GenerationConfig:
    """
    生成配置数据类
    
    统一各Provider的配置参数
    """
    temperature: float = 0.7
    top_p: float = 0.95
    max_output_tokens: int = 800
    presence_penalty: Optional[float] = None
    frequency_penalty: Optional[float] = None
    stop_sequences: Optional[List[str]] = None
    response_format: Optional[Dict[str, Any]] = None
    
    def to_openai_config(self) -> Dict[str, Any]:
        """转换为OpenAI格式"""
        config = {
            "temperature": self.temperature,
            "top_p": self.top_p,
            "max_tokens": self.max_output_tokens,
        }
        if self.presence_penalty is not None:
            config["presence_penalty"] = self.presence_penalty
        if self.frequency_penalty is not None:
            config["frequency_penalty"] = self.frequency_penalty
        if self.stop_sequences:
            config["stop"] = self.stop_sequences
        if self.response_format:
            config["response_format"] = self.response_format
        return config


@dataclass
class ProviderInfo:
    """Provider信息"""
    name: str
    provider_type: str
    supported_models: List[str] = field(default_factory=list)
    supports_vision: bool = False
    supports_tools: bool = False
    supports_thinking: bool = False
    
    # 成本信息（每1K tokens）
    input_cost_per_1k: float = 0.0
    output_cost_per_1k: float = 0.0


class BaseProvider(ABC):
    """
    AI服务提供者抽象基类
    
    所有Provider必须实现此方法，确保接口统一
    """
    
    provider_type: str = "base"
    supported_models: List[str] = []
    supports_vision: bool = False
    supports_tools: bool = False
    supports_thinking: bool = False
    
    def __init__(self, api_key: str, base_url: Optional[str] = None, **kwargs):
        self.api_key = api_key
        self.base_url = base_url
        self._client = None
        self._is_available = False
    
    @abstractmethod
    async def generate(
        self,
        messages: List[Dict[str, Any]],
        config: Optional[GenerationConfig] = None,
        **kwargs
    ) -> GenerationResult:
        """生成回复"""
        pass
    
    @abstractmethod
    async def is_available(self) -> bool:
        """检查服务是否可用"""
        pass
    
    @abstractmethod
    async def generate_embedding(self, text: str, **kwargs) -> Optional[List[float]]:
        """生成文本向量嵌入"""
        pass
    
    def get_info(self) -> ProviderInfo:
        """获取Provider信息"""
        return ProviderInfo(
            name=self.__class__.__name__,
            provider_type=self.provider_type,
            supported_models=self.supported_models,
            supports_vision=self.supports_vision,
            supports_tools=self.supports_tools,
            supports_thinking=self.supports_thinking
        )
    
    async def close(self):
        """关闭连接"""
        pass


# 异常类
class ProviderError(Exception):
    """Provider错误基类"""
    pass


class ProviderNotAvailableError(ProviderError):
    """Provider不可用"""
    pass


class ModelNotSupportedError(ProviderError):
    """模型不支持"""
    pass


class GenerationError(ProviderError):
    """生成错误"""
    def __init__(self, message: str, provider_type: Optional[str] = None, original_error: Optional[Exception] = None):
        self.provider_type = provider_type
        self.original_error = original_error
        super().__init__(message)