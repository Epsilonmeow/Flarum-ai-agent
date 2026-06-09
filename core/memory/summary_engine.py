"""
增量总结引擎 - 每2个块触发AI总结

策略：
- 每积累2个完整块，触发一次增量总结
- 生成用户画像摘要
- 保留关键对话信息
"""

import logging
from typing import List, Optional, Dict, Any
from dataclasses import dataclass

from .conversation_block import ConversationBlock
from .layered_memory import LayeredMemory
from core.providers.base import GenerationConfig

logger = logging.getLogger(__name__)


@dataclass
class SummaryResult:
    """摘要结果"""
    summary: str                    # 生成的摘要文本
    user_profile: Dict[str, Any]    # 用户画像信息
    key_topics: List[str]           # 关键主题
    emotion_trend: str              # 情感趋势
    blocks_summarized: int          # 被摘要的块数


class SummaryEngine:
    """
    增量总结引擎
    
    触发条件：
    - 每2个完成的块触发一次总结
    - 或者手动触发
    
    功能：
    - 生成对话摘要
    - 提取用户画像
    - 识别关键主题
    - 分析情感趋势
    """
    
    # 触发阈值：多少个完整块触发一次总结
    DEFAULT_TRIGGER_THRESHOLD = 2
    
    # 总结提示词模板
    SUMMARY_PROMPT_TEMPLATE = """请对以下对话进行总结。这段对话包含{turn_count}轮用户与AI助手的交流。

【对话内容】
{conversation_text}

请按以下格式输出总结：

【对话摘要】
用2-3句话概括这段对话的核心内容。

【用户状态】
- 主要情绪: (如焦虑/开心/迷茫/压力大等)
- 关注话题: (列出2-3个关键词)
- 可能需求: (用户可能需要什么帮助)

【重要信息】
列出需要记住的关键信息（如果有）：
- 

请确保总结简洁、准确，便于后续对话时快速回忆上下文。"""

    def __init__(
        self,
        layered_memory: LayeredMemory,
        trigger_threshold: int = 2,
        llm_provider = None
    ):
        """
        初始化
        
        Args:
            layered_memory: 三层记忆系统
            trigger_threshold: 触发阈值（块数）
            llm_provider: LLM提供器（用于生成摘要）
        """
        self.memory = layered_memory
        self.trigger_threshold = trigger_threshold
        self.llm_provider = llm_provider
        
        logger.info(f"📝 增量总结引擎初始化 (threshold={trigger_threshold})")
    
    def should_trigger_summary(self, user_id: str, blocks: List[ConversationBlock]) -> bool:
        """
        检查是否应该触发总结
        
        Args:
            user_id: 用户ID
            blocks: 待检查的块列表
            
        Returns:
            bool: 是否触发
        """
        # 获取已完成但未摘要的块
        pending_blocks = [
            b for b in blocks
            if b.is_full and not b.summary
        ]
        
        return len(pending_blocks) >= self.trigger_threshold
    
    async def trigger_summary_if_needed(self, user_id: str) -> Optional[SummaryResult]:
        """
        检查并触发总结（如果需要）
        
        Args:
            user_id: 用户ID
            
        Returns:
            Optional[SummaryResult]: 摘要结果（如果需要且成功）
        """
        # 获取需要摘要的块
        blocks = await self.memory.get_blocks_needing_summary(
            user_id,
            min_completed=self.trigger_threshold
        )
        
        if len(blocks) < self.trigger_threshold:
            return None
        
        logger.info(f"🔄 触发增量总结: 用户={user_id}, 块数={len(blocks)}")
        
        # 执行总结
        return await self.summarize_blocks(user_id, blocks)
    
    async def summarize_blocks(
        self,
        user_id: str,
        blocks: List[ConversationBlock]
    ) -> Optional[SummaryResult]:
        """
        为指定块生成摘要
        
        Args:
            user_id: 用户ID
            blocks: 要总结的块
            
        Returns:
            Optional[SummaryResult]: 摘要结果
        """
        if not blocks:
            return None
        
        # 合并对话内容
        conversation_parts = []
        total_turns = 0
        
        for i, block in enumerate(blocks, 1):
            conversation_parts.append(f"=== 第{i}段对话 ===")
            conversation_parts.append(block.get_conversation_text())
            total_turns += block.turn_count
        
        conversation_text = "\n\n".join(conversation_parts)
        
        # 生成摘要
        if self.llm_provider:
            summary = await self._generate_summary_with_llm(conversation_text, total_turns)
        else:
            # 降级方案：使用简单规则生成摘要
            summary = self._generate_simple_summary(blocks, total_turns)
        
        # 更新块的摘要
        for block in blocks:
            await self.memory.update_block_summary(user_id, block.block_id, summary)
        
        # 添加到用户的摘要列表（L1层）
        await self.memory.add_summary(user_id, summary)
        
        # 解析用户画像（简化版）
        user_profile = self._extract_user_profile(blocks)
        key_topics = self._extract_key_topics(blocks)
        emotion_trend = self._analyze_emotion_trend(blocks)
        
        result = SummaryResult(
            summary=summary,
            user_profile=user_profile,
            key_topics=key_topics,
            emotion_trend=emotion_trend,
            blocks_summarized=len(blocks)
        )
        
        logger.info(
            f"✅ 增量总结完成: 用户={user_id}, "
            f"块数={len(blocks)}, 摘要长度={len(summary)}"
        )
        
        return result
    
    async def _generate_summary_with_llm(self, conversation_text: str, turn_count: int) -> str:
        """
        使用LLM生成摘要
        
        Args:
            conversation_text: 对话文本
            turn_count: 轮数
            
        Returns:
            str: 生成的摘要
        """
        prompt = self.SUMMARY_PROMPT_TEMPLATE.format(
            turn_count=turn_count,
            conversation_text=conversation_text[:3000]  # 限制长度
        )
        
        try:
            logger.debug("🤖 调用LLM生成摘要")
            messages = [
                {
                    "role": "system",
                    "content": "你是一个谨慎、简洁的对话摘要助手，负责为长期记忆系统生成准确摘要。"
                },
                {"role": "user", "content": prompt}
            ]
            config = GenerationConfig(
                temperature=0.3,
                top_p=0.9,
                max_output_tokens=600
            )
            result = await self.llm_provider.generate(messages, config)
            summary = (result.content or "").strip()
            if not summary:
                raise ValueError("LLM 返回了空摘要")
            return summary
        except Exception as e:
            logger.error(f"❌ LLM摘要生成失败: {e}")
            return self._generate_simple_summary_from_text(conversation_text, turn_count)
    
    def _generate_simple_summary(
        self,
        blocks: List[ConversationBlock],
        total_turns: int
    ) -> str:
        """使用简单规则生成摘要"""
        # 统计信息
        total_msgs = sum(len(b.messages) for b in blocks)
        
        # 提取第一个用户消息作为主题
        first_topics = []
        for block in blocks:
            for msg in block.messages:
                if msg.role == "user":
                    topic = msg.content[:40] + "..." if len(msg.content) > 40 else msg.content
                    first_topics.append(topic)
                    break
        
        # 简单摘要
        lines = [
            f"【对话摘要】这段对话共{total_turns}轮，{total_msgs}条消息。",
            f"【主题】{' | '.join(first_topics[:2])}",
            "【状态】用户正在与树洞喵交流"
        ]
        
        return "\n".join(lines)
    
    def _generate_simple_summary_from_text(self, text: str, turn_count: int) -> str:
        """从文本生成简单摘要"""
        # 提取前100字作为预览
        preview = text[:100].replace("\n", " ")
        return f"【对话摘要】共{turn_count}轮对话。开头: {preview}..."
    
    def _extract_user_profile(self, blocks: List[ConversationBlock]) -> Dict[str, Any]:
        """
        从块中提取用户画像
        
        Args:
            blocks: 对话块
            
        Returns:
            Dict: 用户画像
        """
        # 统计用户消息
        user_msgs = []
        for block in blocks:
            for msg in block.messages:
                if msg.role == "user":
                    user_msgs.append(msg.content)
        
        # 简单分析
        profile = {
            "total_messages": len(user_msgs),
            "avg_message_length": sum(len(m) for m in user_msgs) / len(user_msgs) if user_msgs else 0,
            "interaction_style": self._detect_interaction_style(user_msgs)
        }
        
        return profile
    
    def _detect_interaction_style(self, messages: List[str]) -> str:
        """检测用户交互风格"""
        if not messages:
            return "unknown"
        
        avg_len = sum(len(m) for m in messages) / len(messages)
        
        if avg_len < 20:
            return "concise"  # 简洁型
        elif avg_len > 100:
            return "detailed"  # 详细型
        else:
            return "balanced"  # 平衡型
    
    def _extract_key_topics(self, blocks: List[ConversationBlock]) -> List[str]:
        """
        提取关键主题
        
        Args:
            blocks: 对话块
            
        Returns:
            List[str]: 关键主题列表
        """
        # 关键词列表
        topic_keywords = {
            "学业": ["挂科", "考试", "成绩", "学分", "毕业", "论文", "作业", "学习"],
            "情感": ["分手", "恋爱", "失恋", "喜欢", "男朋友", "女朋友", "感情", "暧昧"],
            "人际关系": ["室友", "朋友", "同学", "宿舍", "矛盾", "孤立", "社交"],
            "心理健康": ["焦虑", "抑郁", "失眠", "压力", "难过", "想哭", "迷茫", "无助"],
            "生活": ["食堂", "宿舍", "外卖", "熬夜", "作息", "运动", "健身"],
            "未来规划": ["实习", "工作", "考研", "就业", "方向", "选择", "迷茫"]
        }
        
        # 统计词频
        all_text = ""
        for block in blocks:
            for msg in block.messages:
                if msg.role == "user":
                    all_text += msg.content + " "
        
        topic_scores = {}
        for topic, keywords in topic_keywords.items():
            score = sum(all_text.count(kw) for kw in keywords)
            if score > 0:
                topic_scores[topic] = score
        
        # 按得分排序，返回前3
        sorted_topics = sorted(topic_scores.items(), key=lambda x: x[1], reverse=True)
        return [topic for topic, _ in sorted_topics[:3]]
    
    def _analyze_emotion_trend(self, blocks: List[ConversationBlock]) -> str:
        """
        分析情感趋势
        
        Args:
            blocks: 对话块
            
        Returns:
            str: 情感趋势描述
        """
        # 情感关键词
        positive_words = ["开心", "高兴", "喜欢", "感谢", "感动", "温暖", "幸福", "希望"]
        negative_words = ["难过", "伤心", "焦虑", "抑郁", "孤独", "无助", "绝望", "崩溃", "痛苦"]
        
        positive_count = 0
        negative_count = 0
        
        for block in blocks:
            for msg in block.messages:
                if msg.role == "user":
                    text = msg.content
                    positive_count += sum(1 for w in positive_words if w in text)
                    negative_count += sum(1 for w in negative_words if w in text)
        
        # 判断趋势
        if positive_count > negative_count * 1.5:
            return "positive"  # 积极趋势
        elif negative_count > positive_count * 1.5:
            return "negative"  # 消极趋势
        elif positive_count > 0 or negative_count > 0:
            return "mixed"  # 混合情感
        else:
            return "neutral"  # 中性
    
    async def force_summary(self, user_id: str) -> Optional[SummaryResult]:
        """
        强制触发总结（不管是否达到阈值）
        
        Args:
            user_id: 用户ID
            
        Returns:
            Optional[SummaryResult]: 摘要结果
        """
        memory = await self.memory.load_user_memory(user_id)
        
        # 获取所有已完成但未摘要的块
        pending_blocks = [
            b for b in memory.blocks
            if b.is_full and not b.summary
        ]
        
        if len(pending_blocks) < 1:
            logger.info(f"ℹ️ 用户 {user_id} 没有待总结的块")
            return None
        
        return await self.summarize_blocks(user_id, pending_blocks)
    
    async def get_user_summary_history(self, user_id: str) -> List[str]:
        """
        获取用户的所有历史摘要
        
        Args:
            user_id: 用户ID
            
        Returns:
            List[str]: 摘要列表
        """
        memory = await self.memory.load_user_memory(user_id)
        return memory.summaries.copy()
    
    async def rebuild_all_summaries(self, user_id: str) -> int:
        """
        重建所有摘要（用于初始化或修复）
        
        Args:
            user_id: 用户ID
            
        Returns:
            int: 生成的摘要数
        """
        memory = await self.memory.load_user_memory(user_id)
        
        # 清空现有摘要
        memory.summaries = []
        
        # 获取所有块
        all_blocks = [b for b in memory.blocks if b.is_full]
        
        # 分批总结
        summary_count = 0
        for i in range(0, len(all_blocks), self.trigger_threshold):
            batch = all_blocks[i:i + self.trigger_threshold]
            if len(batch) >= 1:
                result = await self.summarize_blocks(user_id, batch)
                if result:
                    summary_count += 1
        
        logger.info(f"🔄 重建摘要完成: 用户={user_id}, 摘要数={summary_count}")
        return summary_count


# ============ 便捷函数 ============

async def auto_summarize_on_threshold(
    user_id: str,
    layered_memory: LayeredMemory,
    llm_provider = None
) -> Optional[SummaryResult]:
    """
    自动检查并触发总结
    
    Args:
        user_id: 用户ID
        layered_memory: 三层记忆系统
        llm_provider: LLM提供器
        
    Returns:
        Optional[SummaryResult]: 摘要结果（如果需要且成功）
    """
    engine = SummaryEngine(layered_memory, llm_provider=llm_provider)
    return await engine.trigger_summary_if_needed(user_id)