"""
Provider 管理器 - 支持多 Provider 故障转移
"""

import asyncio
import logging
from typing import List, Dict, Optional, Any

from .base import BaseProvider, GenerationResult, GenerationConfig, ProviderNotAvailableError
from .openai_provider import OpenAIProvider, DeepSeekProvider, QwenProvider

logger = logging.getLogger(__name__)


class ProviderManager:
    """
    Provider 管理器
    
    功能：
    - 管理多个 Provider 实例
    - 自动故障转移（主备切换）
    - 健康检查
    """
    
    def __init__(self):
        self.providers: Dict[str, BaseProvider] = {}
        self.primary_provider: Optional[str] = None
        self.fallback_order: List[str] = []
    
    def register_provider(self, name: str, provider: BaseProvider, is_primary: bool = False):
        """注册 Provider"""
        self.providers[name] = provider
        if is_primary or not self.primary_provider:
            self.primary_provider = name
        if name not in self.fallback_order:
            self.fallback_order.append(name)
        logger.info(f"✅ 注册 Provider: {name} (primary={is_primary})")
    
    def register_from_config(self, configs: List[Dict]):
        """从配置批量注册"""
        for cfg in configs:
            if not cfg.get("enabled", True):
                continue
            
            provider_type = cfg.get("type", "openai")
            name = cfg.get("name", provider_type)
            
            if provider_type == "deepseek":
                provider = DeepSeekProvider(
                    api_key=cfg["api_key"],
                    model=cfg.get("model", "deepseek-chat")
                )
            elif provider_type == "qwen":
                provider = QwenProvider(
                    api_key=cfg["api_key"],
                    model=cfg.get("model", "qwen-turbo")
                )
            else:
                provider = OpenAIProvider(
                    api_key=cfg["api_key"],
                    base_url=cfg.get("base_url"),
                    model=cfg.get("model", "gpt-3.5-turbo")
                )
            
            self.register_provider(name, provider, cfg.get("is_primary", False))
    
    async def generate(
        self,
        messages: List[Dict[str, Any]],
        config: Optional[GenerationConfig] = None,
        **kwargs
    ) -> GenerationResult:
        """
        生成回复，带故障转移
        
        依次尝试每个 Provider，直到成功
        """
        config = config or GenerationConfig()
        errors = []
        
        for name in self.fallback_order:
            provider = self.providers.get(name)
            if not provider:
                continue
            
            try:
                # 快速可用性检查
                if not await provider.is_available():
                    logger.warning(f"⏭️ Provider {name} 不可用，跳过")
                    continue
                
                logger.info(f"🤖 使用 Provider: {name}")
                result = await provider.generate(messages, config, **kwargs)
                
                # 标记实际使用的 provider
                result.provider_used = name
                return result
                
            except Exception as e:
                logger.error(f"❌ Provider {name} 失败: {str(e)}")
                errors.append(f"{name}: {str(e)}")
                continue
        
        # 全部失败
        raise ProviderNotAvailableError(f"所有 Provider 都失败: {'; '.join(errors)}")
    
    async def health_check(self) -> Dict[str, bool]:
        """健康检查所有 Provider"""
        results = {}
        for name, provider in self.providers.items():
            try:
                results[name] = await provider.is_available()
            except Exception:
                results[name] = False
        return results
    
    def get_primary(self) -> Optional[BaseProvider]:
        """获取主 Provider"""
        return self.providers.get(self.primary_provider) if self.primary_provider else None


# 全局管理器实例
provider_manager = ProviderManager()