"""
好感度系统 - 用户互动奖励机制

核心组件：
- AffectionManager: 好感度计算与存储
- RewardEngine: 互动奖励机制
"""

from .affection_manager import AffectionManager, AffectionLevel
from .rewards import RewardEngine, InteractionType

__all__ = [
    "AffectionManager",
    "AffectionLevel",
    "RewardEngine",
    "InteractionType",
]