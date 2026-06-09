"""
互动奖励机制 - 根据对话质量计算好感度奖励
"""

import logging
import re
from enum import Enum
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

from .affection_manager import AffectionManager

logger = logging.getLogger(__name__)


class InteractionType(Enum):
    """互动类型"""
    NORMAL = "normal"              # 普通对话
    EMOTIONAL_SUPPORT = "emotional_support"  # 情感支持
    DEEP_CONVERSATION = "deep_conversation"  # 深度交流
    THANKS = "thanks"              # 感谢
    COMPLAINT = "complaint"        # 抱怨/负面情绪
    REJECTION = "rejection"        # 拒绝/不友好
    IDLE = "idle"                  # 闲聊/无意义


@dataclass
class RewardConfig:
    """奖励配置"""
    # 基础分
    base_points: int = 1
    
    # 奖励系数
    emotional_support_bonus: int = 5      # 情感支持奖励
    deep_conversation_bonus: int = 3      # 深度交流奖励
    thanks_bonus: int = 3                 # 感谢奖励
    consecutive_bonus: int = 2            # 连续对话奖励
    length_bonus_factor: float = 0.1      # 长度奖励系数
    
    # 惩罚
    complaint_penalty: int = -2           # 抱怨惩罚
    rejection_penalty: int = -5           # 拒绝惩罚
    idle_penalty: int = -1                # 无意义对话惩罚
    
    # 特殊
    first_interaction_bonus: int = 3      # 首次互动奖励
    return_user_bonus: int = 2            # 回归用户奖励


class RewardEngine:
    """
    互动奖励引擎
    
    根据对话内容分析互动质量，计算好感度奖励
    """
    
    # 情感关键词
    EMOTIONAL_KEYWORDS = {
        "positive": [
            "谢谢", "感谢", " helpful", "有用", "开心", "舒服", "温暖",
            "好多了", "释然", "明白", "懂", "对", "是的", "嗯嗯"
        ],
        "negative": [
            "没用", "不好", "讨厌", "烦", "滚", "垃圾", "差劲",
            "失望", "愤怒", "生气", "恨", "恶心"
        ],
        "emotional_disclosure": [
            "我不知道", "难受", "痛苦", "迷茫", "害怕", "焦虑",
            "失眠", "想哭", "孤独", "无助", "压力大"
        ]
    }
    
    def __init__(
        self,
        affection_manager: AffectionManager,
        config: Optional[RewardConfig] = None
    ):
        """
        初始化
        
        Args:
            affection_manager: 好感度管理器
            config: 奖励配置
        """
        self.affection = affection_manager
        self.config = config or RewardConfig()
        
        logger.info("🎁 互动奖励引擎初始化")
    
    async def analyze_interaction(
        self,
        user_id: str,
        user_message: str,
        ai_message: str,
        conversation_turn: int = 1,
        is_new_user: bool = False,
        is_returning_user: bool = False
    ) -> Dict[str, Any]:
        """
        分析互动并计算奖励
        
        Args:
            user_id: 用户ID
            user_message: 用户消息
            ai_message: AI回复
            conversation_turn: 当前轮次
            is_new_user: 是否新用户
            is_returning_user: 是否回归用户
            
        Returns:
            Dict: 分析结果
        """
        # 检测互动类型
        interaction_type = self._detect_interaction_type(user_message)
        
        # 计算基础分
        points = self.config.base_points
        
        # 应用类型奖励/惩罚
        type_points = self._calculate_type_points(interaction_type)
        points += type_points
        
        # 分析内容质量
        content_analysis = self._analyze_content(user_message)
        points += content_analysis.get("bonus", 0)
        
        # 应用特殊奖励
        if is_new_user:
            points += self.config.first_interaction_bonus
            logger.debug(f"🎉 首次互动奖励: +{self.config.first_interaction_bonus}")
        
        if is_returning_user:
            points += self.config.return_user_bonus
            logger.debug(f"👋 回归用户奖励: +{self.config.return_user_bonus}")
        
        # 连续对话奖励
        if conversation_turn > 1:
            consecutive_bonus = min(conversation_turn, 5) * self.config.consecutive_bonus
            points += consecutive_bonus
            logger.debug(f"📈 连续对话奖励: +{consecutive_bonus} (第{conversation_turn}轮)")
        
        # 确保最低1分（除惩罚外）
        if points < 1 and interaction_type not in [InteractionType.COMPLAINT, InteractionType.REJECTION]:
            points = 1
        
        result = {
            "interaction_type": interaction_type.value,
            "points": points,
            "content_analysis": content_analysis,
            "is_new_user": is_new_user,
            "is_returning_user": is_returning_user,
            "conversation_turn": conversation_turn
        }
        
        logger.info(
            f"🎯 互动分析: {user_id} | 类型={interaction_type.value} | "
            f"得分={points} | 轮次={conversation_turn}"
        )
        
        return result
    
    def _detect_interaction_type(self, message: str) -> InteractionType:
        """检测互动类型"""
        message = message.lower()
        
        # 检测感谢
        if any(kw in message for kw in ["谢谢", "感谢", "thank", "有帮助", "有用"]):
            return InteractionType.THANKS
        
        # 检测抱怨/负面情绪
        if any(kw in message for kw in ["没用", "不好", "讨厌", "烦", "滚"]):
            return InteractionType.COMPLAINT
        
        # 检测拒绝/不友好
        if any(kw in message for kw in ["别", "不要", "不想", "闭嘴", "别说了"]):
            return InteractionType.REJECTION
        
        # 检测情感支持需求
        if any(kw in message for kw in self.EMOTIONAL_KEYWORDS["emotional_disclosure"]):
            return InteractionType.EMOTIONAL_SUPPORT
        
        # 检测闲聊/短消息
        if len(message) < 10:
            return InteractionType.IDLE
        
        # 检测深度交流
        if len(message) > 50 and "?" in message:
            return InteractionType.DEEP_CONVERSATION
        
        return InteractionType.NORMAL
    
    def _calculate_type_points(self, interaction_type: InteractionType) -> int:
        """根据类型计算点数"""
        type_points = {
            InteractionType.NORMAL: 0,
            InteractionType.EMOTIONAL_SUPPORT: self.config.emotional_support_bonus,
            InteractionType.DEEP_CONVERSATION: self.config.deep_conversation_bonus,
            InteractionType.THANKS: self.config.thanks_bonus,
            InteractionType.COMPLAINT: self.config.complaint_penalty,
            InteractionType.REJECTION: self.config.rejection_penalty,
            InteractionType.IDLE: self.config.idle_penalty
        }
        return type_points.get(interaction_type, 0)
    
    def _analyze_content(self, message: str) -> Dict[str, Any]:
        """分析内容质量"""
        bonus = 0
        analysis = {
            "length": len(message),
            "has_question": "?" in message or "？" in message,
            "emotional_indicators": []
        }
        
        # 长度奖励（每100字奖励1分，上限5分）
        length_bonus = min(len(message) / 100 * self.config.length_bonus_factor, 5)
        bonus += int(length_bonus)
        
        # 情感指示器
        for indicator in self.EMOTIONAL_KEYWORDS["emotional_disclosure"]:
            if indicator in message:
                analysis["emotional_indicators"].append(indicator)
        
        # 深度交流奖励
        if analysis["has_question"] and len(message) > 30:
            bonus += 1
        
        analysis["bonus"] = bonus
        
        return analysis
    
    async def apply_reward(
        self,
        user_id: str,
        points: int,
        interaction_type: str = "default",
        metadata: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        应用奖励
        
        Args:
            user_id: 用户ID
            points: 分数
            interaction_type: 互动类型
            metadata: 元数据
            
        Returns:
            Dict: 奖励结果
        """
        # 先应用每日奖励
        daily_bonus = await self.affection.apply_daily_bonus(user_id)
        
        # 添加互动奖励
        result = await self.affection.add_affection(
            user_id,
            points,
            interaction_type,
            metadata
        )
        
        result["daily_bonus"] = daily_bonus
        
        return result
    
    async def process_interaction(
        self,
        user_id: str,
        user_message: str,
        ai_message: str,
        conversation_turn: int = 1
    ) -> Dict[str, Any]:
        """
        处理完整互动流程
        
        Args:
            user_id: 用户ID
            user_message: 用户消息
            ai_message: AI回复
            conversation_turn: 轮次
            
        Returns:
            Dict: 完整结果
        """
        # 获取当前好感度
        summary = await self.affection.get_affection_summary(user_id)
        is_new_user = summary["total_interactions"] == 0
        
        # 分析互动
        analysis = await self.analyze_interaction(
            user_id=user_id,
            user_message=user_message,
            ai_message=ai_message,
            conversation_turn=conversation_turn,
            is_new_user=is_new_user,
            is_returning_user=False  # TODO: 检测回归用户
        )
        
        # 应用奖励
        reward_result = await self.apply_reward(
            user_id,
            analysis["points"],
            analysis["interaction_type"],
            {
                "content_analysis": analysis["content_analysis"],
                "conversation_turn": conversation_turn
            }
        )
        
        # 合并结果
        return {
            **analysis,
            "reward": reward_result,
            "affection_summary": await self.affection.get_affection_summary(user_id)
        }
    
    def get_interaction_feedback(
        self,
        interaction_type: InteractionType,
        points: int
    ) -> str:
        """
        获取互动反馈（用于调试或展示）
        
        Args:
            interaction_type: 互动类型
            points: 得分
            
        Returns:
            str: 反馈文本
        """
        if points > 5:
            return "非常积极的互动！"
        elif points > 2:
            return "良好的互动。"
        elif points > 0:
            return "普通互动。"
        elif points > -3:
            return "略显消极的互动。"
        else:
            return "需要关注的负面互动。"


# 便捷函数

async def quick_reward(
    user_id: str,
    user_message: str,
    ai_message: str,
    affection_manager: AffectionManager
) -> Dict[str, Any]:
    """
    快速计算并应用奖励
    
    Args:
        user_id: 用户ID
        user_message: 用户消息
        ai_message: AI回复
        affection_manager: 好感度管理器
        
    Returns:
        Dict: 结果
    """
    engine = RewardEngine(affection_manager)
    return await engine.process_interaction(user_id, user_message, ai_message)


def calculate_conversation_quality(
    user_messages: List[str],
    ai_messages: List[str]
) -> Dict[str, Any]:
    """
    计算对话质量（用于事后分析）
    
    Args:
        user_messages: 用户消息列表
        ai_messages: AI消息列表
        
    Returns:
        Dict: 质量分析
    """
    if not user_messages:
        return {"quality": "unknown", "score": 0}
    
    # 计算平均长度
    avg_length = sum(len(m) for m in user_messages) / len(user_messages)
    
    # 检测情感支持次数
    support_count = sum(
        1 for m in user_messages
        if any(kw in m for kw in ["难受", "痛苦", "迷茫", "焦虑"])
    )
    
    # 检测感谢次数
    thanks_count = sum(
        1 for m in user_messages
        if any(kw in m for kw in ["谢谢", "感谢"])
    )
    
    # 综合评分
    score = 0
    score += min(avg_length / 50, 5)  # 长度分
    score += support_count * 2        # 情感支持分
    score += thanks_count * 3         # 感谢分
    
    # 质量等级
    if score >= 15:
        quality = "excellent"
    elif score >= 10:
        quality = "good"
    elif score >= 5:
        quality = "average"
    else:
        quality = "poor"
    
    return {
        "quality": quality,
        "score": round(score, 2),
        "avg_message_length": round(avg_length, 2),
        "support_interactions": support_count,
        "thanks_count": thanks_count,
        "total_turns": len(user_messages)
    }