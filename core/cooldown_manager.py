"""
冷却管理模块 - 防止同一用户恶意刷 API
"""

import logging
import time
from typing import Dict, Optional
from datetime import datetime, timedelta

import config

logger = logging.getLogger(__name__)


# ============ 回复冷却判断函数 ============

class CooldownManager:
    """
    用户回复冷却管理器
    
    功能：
    - 跟踪每个用户的最后回复时间
    - 判断用户是否处于冷却期
    - 支持紧急情况的冷却绕过
    """
    
    def __init__(self):
        # 内存中的冷却记录: {user_id: last_reply_timestamp}
        self._cooldown_records: Dict[str, float] = {}
        # 白名单用户（不受冷却限制）
        self._whitelist: set = set()
        logger.info("⏱️ CooldownManager 初始化")
    
    def check_cooldown(self, user_id: str) -> bool:
        """
        【回复冷却判断函数】
        
        检查用户是否可以发送新回复（是否已过冷却期）
        
        判断逻辑：
        1. 白名单用户直接通过
        2. 计算距上次回复的时间间隔
        3. 如果间隔 >= REPLY_COOLDOWN_SECONDS，允许回复
        4. 高风险内容可绕过冷却（紧急情况）
        
        Args:
            user_id: 用户唯一标识
            
        Returns:
            bool: True = 允许回复，False = 处于冷却期
        """
        if not user_id:
            return True  # 无法识别用户时允许回复
        
        # 白名单用户免冷却
        if user_id in self._whitelist:
            logger.debug(f"用户 {user_id} 在白名单中，免冷却")
            return True
        
        # 获取上次回复时间
        last_reply = self._cooldown_records.get(user_id)
        
        if last_reply is None:
            # 首次回复，允许
            logger.debug(f"用户 {user_id} 首次回复，允许")
            return True
        
        # 计算时间差
        elapsed = time.time() - last_reply
        cooldown_seconds = config.REPLY_COOLDOWN_SECONDS
        
        if elapsed >= cooldown_seconds:
            logger.debug(f"用户 {user_id} 冷却已过 ({elapsed:.0f}s > {cooldown_seconds}s)，允许回复")
            return True
        else:
            remaining = cooldown_seconds - elapsed
            logger.info(f"⏱️ 用户 {user_id} 处于冷却期，还需 {remaining:.0f} 秒")
            return False
    
    def update_cooldown(self, user_id: str, content: Optional[str] = None):
        """
        更新用户的冷却记录
        
        在成功回复后调用，记录当前时间
        
        Args:
            user_id: 用户唯一标识
            content: 可选，帖子内容（用于判断是否为紧急内容）
        """
        if not user_id:
            return
        
        # 检查是否为紧急/高风险内容，如果是则缩短冷却时间
        is_urgent = self._is_urgent_content(content) if content else False
        
        if is_urgent:
            # 紧急内容使用缩短的冷却时间
            cooldown_override = max(config.REPLY_COOLDOWN_SECONDS // 3, 10)
            logger.info(f"⚠️ 检测到紧急内容，用户 {user_id} 冷却时间缩短为 {cooldown_override} 秒")
            # 不更新记录，允许快速连续回复紧急情况
            return
        
        self._cooldown_records[user_id] = time.time()
        logger.debug(f"⏱️ 用户 {user_id} 冷却时间已更新")
    
    def _is_urgent_content(self, content: Optional[str]) -> bool:
        """
        判断内容是否为紧急情况（需要快速响应）
        
        检测关键词：自杀、自残、危机干预等
        
        Args:
            content: 帖子内容
            
        Returns:
            bool: 是否为紧急内容
        """
        if not content:
            return False
        
        urgent_keywords = [
            "自杀", "自残", "跳楼", "不想活", "活不下去",
            "kill myself", "suicide", "不想活了", "结束生命"
        ]
        
        content_lower = content.lower()
        return any(kw in content for kw in urgent_keywords)
    
    def add_to_whitelist(self, user_id: str):
        """
        将用户加入白名单（测试账号、管理员等）
        
        Args:
            user_id: 用户唯一标识
        """
        self._whitelist.add(user_id)
        logger.info(f"✅ 用户 {user_id} 已加入白名单")
    
    def remove_from_whitelist(self, user_id: str):
        """
        将用户移出白名单
        
        Args:
            user_id: 用户唯一标识
        """
        self._whitelist.discard(user_id)
        logger.info(f"🚫 用户 {user_id} 已移出白名单")
    
    def get_cooldown_info(self, user_id: str) -> Dict:
        """
        获取用户的冷却状态信息（用于管理后台显示）
        
        Args:
            user_id: 用户唯一标识
            
        Returns:
            Dict: 冷却状态信息
        """
        last_reply = self._cooldown_records.get(user_id)
        
        if last_reply is None:
            return {
                "user_id": user_id,
                "status": "从未回复",
                "last_reply": None,
                "remaining_seconds": 0,
                "can_reply": True
            }
        
        elapsed = time.time() - last_reply
        cooldown = config.REPLY_COOLDOWN_SECONDS
        remaining = max(0, cooldown - elapsed)
        
        return {
            "user_id": user_id,
            "status": "冷却中" if remaining > 0 else "可回复",
            "last_reply": datetime.fromtimestamp(last_reply).isoformat(),
            "elapsed_seconds": int(elapsed),
            "remaining_seconds": int(remaining),
            "can_reply": remaining <= 0
        }
    
    def clear_cooldown(self, user_id: str):
        """
        手动清除用户的冷却状态（管理功能）
        
        Args:
            user_id: 用户唯一标识
        """
        if user_id in self._cooldown_records:
            del self._cooldown_records[user_id]
            logger.info(f"🧹 用户 {user_id} 的冷却状态已清除")
    
    def get_all_cooldowns(self) -> Dict[str, Dict]:
        """
        获取所有用户的冷却状态（管理后台使用）
        
        Returns:
            Dict: {user_id: cooldown_info}
        """
        return {
            user_id: self.get_cooldown_info(user_id)
            for user_id in self._cooldown_records.keys()
        }


# 全局冷却管理器实例
cooldown_manager = CooldownManager()


# 便捷函数（供外部调用）

def check_reply_cooldown(user_id: str) -> bool:
    """便捷函数：检查用户是否已过冷却期"""
    return cooldown_manager.check_cooldown(user_id)


def update_cooldown(user_id: str, content: Optional[str] = None):
    """便捷函数：更新用户冷却记录"""
    cooldown_manager.update_cooldown(user_id, content)


def get_cooldown_status(user_id: str) -> Dict:
    """便捷函数：获取用户冷却状态"""
    return cooldown_manager.get_cooldown_info(user_id)