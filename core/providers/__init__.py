"""
Provider 模块
"""

from .base import (
    BaseProvider,
    GenerationResult,
    GenerationConfig,
    ProviderInfo,
    FinishReason,
    ProviderError,
    ProviderNotAvailableError,
    ModelNotSupportedError,
    GenerationError,
)
from .openai_provider import OpenAIProvider, DeepSeekProvider, QwenProvider
from .mock_provider import MockProvider

# 延迟导入 ProviderManager 和 provider_manager 以避免循环导入
def _get_provider_manager():
    from .manager import ProviderManager
    return ProviderManager

def _get_provider_manager_instance():
    from .manager import provider_manager
    return provider_manager

ProviderManager = _get_provider_manager()

__all__ = [
    "BaseProvider",
    "GenerationResult", 
    "GenerationConfig",
    "ProviderInfo",
    "FinishReason",
    "ProviderError",
    "ProviderNotAvailableError",
    "ModelNotSupportedError",
    "GenerationError",
    "OpenAIProvider",
    "DeepSeekProvider",
    "QwenProvider",
    "MockProvider",
    "ProviderManager",
]
