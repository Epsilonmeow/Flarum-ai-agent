"""
LLM 引擎 V2 - 重构版
集成 ProviderManager + 三层记忆系统 + 好感度系统
"""

import logging
from typing import Optional, List, Dict, Any, Tuple
from pathlib import Path
from dataclasses import dataclass

import config
from core.providers.manager import ProviderManager, provider_manager, GenerationConfig
from core.memory.layered_memory import LayeredMemory
from core.memory.summary_engine import SummaryEngine
from core.affection.affection_manager import AffectionManager, get_user_familiarity_level
from core.affection.rewards import RewardEngine

logger = logging.getLogger(__name__)


@dataclass
class GenerationContext:
    """
    生成上下文
    
    包含所有用于生成回复的上下文信息
    """
    user_id: str
    user_message: str
    system_prompt: str = ""
    memory_summaries: str = ""
    recent_context: List[Dict[str, str]] = None
    familiarity_hint: str = ""
    matched_worldbook_uids: List[str] = None
    
    def __post_init__(self):
        if self.recent_context is None:
            self.recent_context = []
        if self.matched_worldbook_uids is None:
            self.matched_worldbook_uids = []


class LLMEngineV2:
    """
    LLM 引擎 V2
    
    新特性：
    - 使用 ProviderManager 支持多Provider故障转移
    - 集成三层记忆系统
    - 集成好感度系统
    - 更丰富的上下文注入
    """
    
    def __init__(
        self,
        provider_manager: ProviderManager = None,
        memory_storage_dir: Optional[Path] = None,
        affection_storage_dir: Optional[Path] = None
    ):
        """
        初始化
        
        Args:
            provider_manager: Provider管理器
            memory_storage_dir: 记忆存储目录
            affection_storage_dir: 好感度存储目录
        """
        from core.providers.manager import provider_manager as global_pm
        
        # 如果传入的 manager 为空，使用全局 manager
        pm = provider_manager or global_pm
        
        # 如果全局 manager 也没有 provider，尝试自动初始化
        if not pm.providers:
            pm = _ensure_provider_initialized()
        
        self.provider_manager = pm
        
        # 初始化三层记忆系统
        memory_dir = memory_storage_dir or (config.DATA_DIR / "memory")
        self.layered_memory = LayeredMemory(memory_dir)
        self.summary_engine = SummaryEngine(
            self.layered_memory,
            trigger_threshold=config.SUMMARY_TRIGGER_THRESHOLD,
            llm_provider=self.provider_manager
        )
        
        # 初始化好感度系统
        affection_dir = affection_storage_dir or (config.DATA_DIR / "affection")
        self.affection_manager = AffectionManager(affection_dir)
        self.reward_engine = RewardEngine(self.affection_manager)
        
        # 保持旧版 llm_engine 的部分功能（世界书）
        self._init_legacy_components()
        
        logger.info("🧠 LLMEngineV2 初始化完成")
    
    def _init_legacy_components(self):
        """初始化旧版组件（世界书等）"""
        # 导入旧版组件，保持兼容性
        try:
            from core.llm_engine import WorldBookMatcher, OutputRegexManager
            
            self.worldbook_matcher = WorldBookMatcher()
            self.output_regex = OutputRegexManager()
            
            logger.debug("✅ 旧版组件初始化完成")
        except Exception as e:
            logger.warning(f"⚠️ 旧版组件初始化失败: {e}")
            self.worldbook_matcher = None
            self.output_regex = None
    
    async def prepare_context(self, user_id: str, user_message: str) -> GenerationContext:
        """
        准备生成上下文
        
        Args:
            user_id: 用户ID
            user_message: 用户消息
            
        Returns:
            GenerationContext: 上下文
        """
        # 1. 获取三层记忆
        memory_data = await self.layered_memory.get_memory_for_prompt(
            user_id,
            include_summaries=True,
            max_recent_blocks=1,
            max_context_messages=config.MAX_CONTEXT_MESSAGES,
            max_summaries=config.MAX_SUMMARIES_IN_PROMPT
        )
        
        # 2. 获取好感度提示
        familiarity_hint = await get_user_familiarity_level(user_id, self.affection_manager)
        
        # 3. 匹配世界书
        matched_uids = []
        if self.worldbook_matcher:
            _, matched_uids = self.worldbook_matcher.match(user_message)
        
        # 4. 构建系统提示词
        system_prompt = self._build_system_prompt(
            memory_data.get("summaries", ""),
            familiarity_hint
        )
        
        return GenerationContext(
            user_id=user_id,
            user_message=user_message,
            system_prompt=system_prompt,
            memory_summaries=memory_data.get("summaries", ""),
            recent_context=memory_data.get("recent_context", []),
            familiarity_hint=familiarity_hint,
            matched_worldbook_uids=matched_uids
        )
    
    def _build_system_prompt(self, summaries: str, familiarity: str) -> str:
        """
        构建系统提示词
        
        Args:
            summaries: 历史摘要
            familiarity: 熟悉度提示
            
        Returns:
            str: 系统提示词
        """
        parts = [config.SYSTEM_PROMPT]
        
        # 注入记忆摘要
        if summaries:
            parts.append(f"\n\n[历史对话摘要]\n{summaries}")
        
        # 注入熟悉度提示
        if familiarity:
            parts.append(f"\n\n[关系提示]\n{familiarity}")
        
        # 最高指令
        parts.append(
            "\n\n[最高指令]\n"
            "请严格遵守上述设定，禁止 OOC（角色扮演）。\n"
            "回复应当自然、温暖、符合人设，避免机械感。"
        )
        
        return "\n".join(parts)
    
    def _build_messages(self, context: GenerationContext) -> List[Dict[str, str]]:
        """
        构建消息列表
        
        Args:
            context: 上下文
            
        Returns:
            List[Dict]: 消息列表
        """
        messages = [
            {"role": "system", "content": context.system_prompt}
        ]
        
        # 注入近期上下文（L2/L3层记忆）
        for msg in context.recent_context:
            messages.append({
                "role": msg["role"],
                "content": msg["content"]
            })
        
        # 当前用户消息
        messages.append({
            "role": "user",
            "content": context.user_message
        })
        
        return messages
    
    async def generate(
        self,
        user_id: str,
        user_message: str,
        temperature: float = 0.7,
        max_tokens: int = 500,
        save_memory: bool = True,
        **kwargs
    ) -> Dict[str, Any]:
        """
        生成回复（完整流程）
        
        Args:
            user_id: 用户ID
            user_message: 用户消息
            temperature: 温度
            max_tokens: 最大token数
            save_memory: 是否将本次交互写入三层记忆系统
            **kwargs: 额外参数
            
        Returns:
            Dict: 生成结果
        """
        # 1. 准备上下文
        context = await self.prepare_context(user_id, user_message)
        
        # 2. 构建消息
        messages = self._build_messages(context)
        
        # 3. 调用 LLM
        gen_config = GenerationConfig(
            temperature=temperature,
            max_output_tokens=max_tokens
        )
        
        try:
            result = await self.provider_manager.generate(messages, gen_config, **kwargs)
            
            # 4. 应用 Output Regex
            processed_content = result.content
            if self.output_regex:
                processed_content = self.output_regex.apply(result.content)
            
            # 5. 按记忆价值评估结果保存到记忆系统
            if save_memory:
                await self._save_interaction(
                    user_id,
                    user_message,
                    processed_content
                )
            else:
                logger.info(f"🗑️ 本次交互未写入记忆系统: user={user_id}")
            
            # 6. 计算好感度奖励
            reward_result = await self.reward_engine.process_interaction(
                user_id,
                user_message,
                processed_content,
                conversation_turn=len(context.recent_context) // 2 + 1
            )
            
            return {
                "reply": processed_content,
                "raw_reply": result.raw_content,
                "model": result.model_used,
                "provider": result.provider_used if hasattr(result, 'provider_used') else 'unknown',
                "tokens": result.tokens_used,
                "context": {
                    "summaries_included": bool(context.memory_summaries),
                    "recent_messages": len(context.recent_context),
                    "familiarity_level": context.familiarity_hint[:20] + "..." if len(context.familiarity_hint) > 20 else context.familiarity_hint,
                    "matched_worldbooks": context.matched_worldbook_uids,
                    "memory_saved": save_memory
                },
                "reward": reward_result
            }
            
        except Exception as e:
            logger.exception(f"❌ 生成失败: {e}")
            raise
    
    async def _save_interaction(self, user_id: str, user_msg: str, ai_msg: str):
        """
        保存交互到记忆系统
        
        Args:
            user_id: 用户ID
            user_msg: 用户消息
            ai_msg: AI消息
        """
        try:
            # 添加用户消息
            await self.layered_memory.add_message(user_id, "user", user_msg)
            
            # 添加AI回复
            await self.layered_memory.add_message(user_id, "assistant", ai_msg)
            
            # 检查是否需要触发摘要
            await self.summary_engine.trigger_summary_if_needed(user_id)
            
            logger.debug(f"💾 交互已保存: {user_id}")
        except Exception as e:
            logger.error(f"❌ 保存交互失败: {e}")
    
    async def get_user_memory_stats(self, user_id: str) -> Dict[str, Any]:
        """
        获取用户记忆统计
        
        Args:
            user_id: 用户ID
            
        Returns:
            Dict: 统计信息
        """
        memory_stats = await self.layered_memory.get_user_stats(user_id)
        affection_stats = await self.affection_manager.get_affection_summary(user_id)
        
        return {
            "user_id": user_id,
            "memory": memory_stats,
            "affection": affection_stats
        }


# 全局引擎实例
_llm_engine_v2: Optional[LLMEngineV2] = None


async def get_llm_engine_v2() -> LLMEngineV2:
    """
    获取全局 LLMEngineV2 实例
    
    Returns:
        LLMEngineV2: 引擎实例
    """
    global _llm_engine_v2
    
    if _llm_engine_v2 is None:
        _llm_engine_v2 = LLMEngineV2()
    
    return _llm_engine_v2




def _ensure_provider_initialized():
    """确保 Provider 已初始化"""
    from core.providers.manager import provider_manager
    
    if not provider_manager.providers:
        # 优先使用多 Provider 配置，确保文档中的故障转移能力在运行时自然生效
        if config.PROVIDER_CONFIGS:
            provider_manager.register_from_config(config.PROVIDER_CONFIGS)
            logger.info(f"✅ 已从 PROVIDER_CONFIGS 初始化 {len(provider_manager.providers)} 个 Provider")

        # 如果没有多 Provider 配置，再尝试从旧版单 Provider 配置初始化
        if config.LLM_API_KEY and config.LLM_API_KEY != "your-api-key-here":
            from core.providers.openai_provider import OpenAIProvider, DeepSeekProvider, QwenProvider
            
            base_url = config.LLM_BASE_URL.lower()
            if "deepseek" in base_url:
                provider = DeepSeekProvider(api_key=config.LLM_API_KEY, model=config.LLM_MODEL)
                provider_type = "deepseek"
            elif "qwen" in base_url or "aliyun" in base_url:
                provider = QwenProvider(api_key=config.LLM_API_KEY, model=config.LLM_MODEL)
                provider_type = "qwen"
            else:
                provider = OpenAIProvider(
                    api_key=config.LLM_API_KEY,
                    base_url=config.LLM_BASE_URL,
                    model=config.LLM_MODEL
                )
                provider_type = "openai"
            
            provider_manager.register_provider(provider_type, provider, is_primary=True)
            logger.info(f"✅ 自动初始化 Provider: {provider_type}")
    
    return provider_manager


async def generate_reply_v2(
    user_id: str,
    user_message: str,
    temperature: float = 0.7,
    max_tokens: int = 500,
    save_memory: bool = True
) -> str:
    """
    【生成回复 V2】主入口函数
    
    Args:
        user_id: 用户ID
        user_message: 用户消息
        temperature: 温度
        max_tokens: 最大token数
        save_memory: 是否将本次交互写入三层记忆系统
        
    Returns:
        str: AI 生成的回复
    """
    _ensure_provider_initialized()
    engine = await get_llm_engine_v2()
    
    try:
        result = await engine.generate(
            user_id,
            user_message,
            temperature,
            max_tokens,
            save_memory=save_memory
        )
        return result["reply"]
        
    except Exception as e:
        logger.exception(f"❌ 生成回复失败: {e}")
        return "抱歉，我现在有点懵，能再说一遍吗？🐱"


# 兼容性：保持旧接口
async def generate_reply(user_message: str, user_id: str = "default") -> str:
    """
    兼容旧版接口
    
    Args:
        user_message: 用户消息
        user_id: 用户ID（可选）
        
    Returns:
        str: 回复
    """
    return await generate_reply_v2(user_id, user_message)


# ============ 便捷函数 ============

async def clear_user_data(user_id: str):
    """
    清空用户所有数据（记忆+好感度）
    
    Args:
        user_id: 用户ID
    """
    engine = await get_llm_engine_v2()
    
    await engine.layered_memory.clear_user_memory(user_id)
    await engine.affection_manager.reset_affection(user_id)
    
    logger.info(f"🗑️ 用户数据已清空: {user_id}")


async def get_user_profile(user_id: str) -> Dict[str, Any]:
    """
    获取用户完整画像
    
    Args:
        user_id: 用户ID
        
    Returns:
        Dict: 用户画像
    """
    engine = await get_llm_engine_v2()
    return await engine.get_user_memory_stats(user_id)