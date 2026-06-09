"""
好感度管理器 - 用户互动好感度计算与存储
轻量级实现（JSON文件存储）
"""

import asyncio
import json
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class AffectionLevel(Enum):
    """好感度等级"""
    STRANGER = ("stranger", 0, 20, "陌生人")      # 0-19
    ACQUAINTANCE = ("acquaintance", 20, 50, "熟人")  # 20-49
    FRIEND = ("friend", 50, 100, "朋友")          # 50-99
    CLOSE_FRIEND = ("close_friend", 100, 200, "好友")  # 100-199
    BEST_FRIEND = ("best_friend", 200, 9999, "挚友")   # 200+
    
    def __init__(self, key: str, min_score: int, max_score: int, label: str):
        self.key = key
        self.min_score = min_score
        self.max_score = max_score
        self.label = label
    
    @classmethod
    def from_score(cls, score: int) -> "AffectionLevel":
        """根据分数获取等级"""
        for level in cls:
            if level.min_score <= score < level.max_score:
                return level
        return cls.BEST_FRIEND


@dataclass
class UserAffection:
    """
    用户好感度数据
    
    Attributes:
        user_id: 用户ID
        score: 当前好感度分数
        total_interactions: 总互动次数
        last_interaction: 最后互动时间
        interaction_history: 互动历史（最近30天）
        achievements: 解锁的成就
        metadata: 额外元数据
    """
    
    user_id: str
    score: int = 0
    total_interactions: int = 0
    last_interaction: Optional[str] = None
    interaction_history: List[Dict[str, Any]] = field(default_factory=list)
    achievements: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def __post_init__(self):
        """初始化后清理历史数据"""
        self._cleanup_old_history()
    
    def _cleanup_old_history(self, days: int = 30):
        """清理过期的历史记录"""
        cutoff = datetime.now() - timedelta(days=days)
        self.interaction_history = [
            h for h in self.interaction_history
            if datetime.fromisoformat(h.get("timestamp", "2000-01-01")) > cutoff
        ]
    
    @property
    def level(self) -> AffectionLevel:
        """当前等级"""
        return AffectionLevel.from_score(self.score)
    
    @property
    def level_progress(self) -> float:
        """当前等级进度（0.0-1.0）"""
        level = self.level
        if level == AffectionLevel.BEST_FRIEND:
            return 1.0
        
        level_range = level.max_score - level.min_score
        progress = self.score - level.min_score
        return progress / level_range
    
    def add_score(self, points: int, interaction_type: str = "default", metadata: Optional[Dict] = None):
        """
        增加好感度分数
        
        Args:
            points: 分数（可为负）
            interaction_type: 互动类型
            metadata: 额外元数据
        """
        old_score = self.score
        old_level = self.level
        
        self.score = max(0, self.score + points)
        self.total_interactions += 1
        self.last_interaction = datetime.now().isoformat()
        
        # 记录历史
        self.interaction_history.append({
            "timestamp": datetime.now().isoformat(),
            "type": interaction_type,
            "points": points,
            "score_after": self.score,
            "metadata": metadata or {}
        })
        
        # 检查等级变化
        new_level = self.level
        level_up = new_level != old_level and new_level.min_score > old_level.min_score
        
        self.updated_at = datetime.now().isoformat()
        
        # 清理历史
        self._cleanup_old_history()
        
        return {
            "old_score": old_score,
            "new_score": self.score,
            "old_level": old_level,
            "new_level": new_level,
            "level_up": level_up,
            "points_added": points
        }
    
    def check_achievement(self, achievement_id: str) -> bool:
        """检查是否已解锁成就"""
        return achievement_id in self.achievements
    
    def unlock_achievement(self, achievement_id: str) -> bool:
        """
        解锁成就
        
        Returns:
            bool: 是否新解锁（False表示已拥有）
        """
        if achievement_id in self.achievements:
            return False
        
        self.achievements.append(achievement_id)
        self.updated_at = datetime.now().isoformat()
        return True
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "user_id": self.user_id,
            "score": self.score,
            "total_interactions": self.total_interactions,
            "last_interaction": self.last_interaction,
            "interaction_history": self.interaction_history,
            "achievements": self.achievements,
            "metadata": self.metadata,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UserAffection":
        """从字典创建"""
        return cls(
            user_id=data["user_id"],
            score=data.get("score", 0),
            total_interactions=data.get("total_interactions", 0),
            last_interaction=data.get("last_interaction"),
            interaction_history=data.get("interaction_history", []),
            achievements=data.get("achievements", []),
            metadata=data.get("metadata", {}),
            created_at=data.get("created_at", datetime.now().isoformat()),
            updated_at=data.get("updated_at", datetime.now().isoformat())
        )


class AffectionManager:
    """
    好感度管理器
    
    轻量级实现：使用JSON文件存储
    """
    
    # 默认配置
    DAILY_INTERACTION_BONUS = 5        # 每日首次互动奖励
    CONSECUTIVE_DAY_BONUS = 10         # 连续互动奖励
    MAX_DAILY_DECAY = 2                # 每日衰减上限
    
    def __init__(self, storage_dir: Path):
        """
        初始化
        
        Args:
            storage_dir: 存储目录
        """
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        
        # 内存缓存
        self._cache: Dict[str, UserAffection] = {}
        self._locks: Dict[str, asyncio.Lock] = {}
        
        logger.info(f"❤️ 好感度管理器初始化: {self.storage_dir}")
    
    def _get_user_lock(self, user_id: str) -> asyncio.Lock:
        """获取用户级异步锁，避免同一用户好感度被并发读写覆盖"""
        if user_id not in self._locks:
            self._locks[user_id] = asyncio.Lock()
        return self._locks[user_id]
    
    def _get_user_file_path(self, user_id: str) -> Path:
        """获取用户文件路径"""
        subdir = user_id[:2] if len(user_id) >= 2 else "xx"
        user_dir = self.storage_dir / subdir
        user_dir.mkdir(exist_ok=True)
        return user_dir / f"{user_id}_affection.json"
    
    def _backup_corrupt_file(self, file_path: Path, user_id: str):
        """备份损坏的 JSON 文件，避免后续排查时丢失现场"""
        if not file_path.exists():
            return
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        backup_path = file_path.with_name(f"{file_path.name}.corrupt.{timestamp}")
        try:
            file_path.replace(backup_path)
            logger.warning(f"⚠️ 已备份损坏的好感度文件: {user_id} -> {backup_path.name}")
        except Exception as backup_error:
            logger.error(f"❌ 备份损坏好感度文件失败 {user_id}: {backup_error}")
    
    def _atomic_write_json(self, file_path: Path, data: Dict[str, Any]):
        """通过临时文件 + 原子替换写入 JSON，避免写一半导致文件损坏"""
        tmp_path = file_path.with_name(f"{file_path.name}.tmp")
        try:
            with open(tmp_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                f.flush()
            tmp_path.replace(file_path)
        finally:
            if tmp_path.exists():
                try:
                    tmp_path.unlink()
                except Exception:
                    logger.debug(f"清理临时好感度文件失败: {tmp_path}")
    
    def _get_user_affection_unlocked(self, user_id: str) -> UserAffection:
        """获取用户好感度；调用方需要自行持有用户锁"""
        # 检查缓存
        if user_id in self._cache:
            return self._cache[user_id]
        
        # 从文件加载
        file_path = self._get_user_file_path(user_id)
        
        if file_path.exists():
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                affection = UserAffection.from_dict(data)
                logger.debug(f"📂 加载好感度: {user_id} (score={affection.score})")
            except Exception as e:
                logger.error(f"❌ 加载好感度失败 {user_id}: {e}")
                self._backup_corrupt_file(file_path, user_id)
                affection = UserAffection(user_id=user_id)
        else:
            affection = UserAffection(user_id=user_id)
            logger.debug(f"🆕 新建好感度: {user_id}")
        
        # 缓存
        self._cache[user_id] = affection
        return affection
    
    def _save_user_affection_unlocked(self, user_id: str):
        """保存用户好感度；调用方需要自行持有用户锁"""
        if user_id not in self._cache:
            return
        
        affection = self._cache[user_id]
        file_path = self._get_user_file_path(user_id)
        
        try:
            self._atomic_write_json(file_path, affection.to_dict())
            logger.debug(f"💾 保存好感度: {user_id}")
        except Exception as e:
            logger.error(f"❌ 保存好感度失败 {user_id}: {e}")
    
    def _add_affection_unlocked(
        self,
        user_id: str,
        points: int,
        interaction_type: str = "default",
        metadata: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """增加好感度；调用方需要自行持有用户锁"""
        affection = self._get_user_affection_unlocked(user_id)
        result = affection.add_score(points, interaction_type, metadata)
        achievements = self._check_achievements(affection)
        result["achievements_unlocked"] = achievements
        self._save_user_affection_unlocked(user_id)
        return result
    
    async def get_user_affection(self, user_id: str) -> UserAffection:
        """
        获取用户好感度
        
        Args:
            user_id: 用户ID
            
        Returns:
            UserAffection: 好感度对象
        """
        async with self._get_user_lock(user_id):
            return self._get_user_affection_unlocked(user_id)
    
    async def save_user_affection(self, user_id: str):
        """
        保存用户好感度
        
        Args:
            user_id: 用户ID
        """
        async with self._get_user_lock(user_id):
            self._save_user_affection_unlocked(user_id)
    
    async def add_affection(
        self,
        user_id: str,
        points: int,
        interaction_type: str = "default",
        metadata: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        增加好感度
        
        Args:
            user_id: 用户ID
            points: 分数
            interaction_type: 互动类型
            metadata: 元数据
            
        Returns:
            Dict: 操作结果
        """
        async with self._get_user_lock(user_id):
            result = self._add_affection_unlocked(
                user_id,
                points,
                interaction_type,
                metadata
            )
            affection = self._cache[user_id]
            
            logger.info(
                f"❤️ 好感度更新: {user_id} +{points} "
                f"(score={affection.score}, level={affection.level.label})"
            )
            
            return result
    
    def _check_achievements(self, affection: UserAffection) -> List[str]:
        """检查并解锁成就"""
        unlocked = []
        
        # 定义成就
        achievements = {
            "first_interaction": (lambda a: a.total_interactions >= 1, "初次相遇"),
            "ten_interactions": (lambda a: a.total_interactions >= 10, "十次互动"),
            "hundred_interactions": (lambda a: a.total_interactions >= 100, "百次相伴"),
            "friend_level": (lambda a: a.level.value[1] >= 50, "成为朋友"),
            "close_friend": (lambda a: a.level.value[1] >= 100, "成为好友"),
            "best_friend": (lambda a: a.level.value[1] >= 200, "成为挚友"),
        }
        
        for achievement_id, (check_func, name) in achievements.items():
            if check_func(affection):
                if affection.unlock_achievement(f"{achievement_id}:{name}"):
                    unlocked.append(achievement_id)
                    logger.info(f"🏆 解锁成就: {name} (用户: {affection.user_id})")
        
        return unlocked
    
    async def apply_daily_bonus(self, user_id: str) -> int:
        """
        应用每日首次互动奖励
        
        Args:
            user_id: 用户ID
            
        Returns:
            int: 获得的奖励分数（0表示不是首次）
        """
        async with self._get_user_lock(user_id):
            affection = self._get_user_affection_unlocked(user_id)
            
            # 检查今天是否已互动
            today = datetime.now().strftime("%Y-%m-%d")
            
            if affection.last_interaction:
                last_date = affection.last_interaction[:10]
                if last_date == today:
                    return 0  # 今天已经互动过
            
            # 检查是否连续
            is_consecutive = False
            if affection.last_interaction:
                last_date = datetime.fromisoformat(affection.last_interaction).date()
                yesterday = (datetime.now() - timedelta(days=1)).date()
                is_consecutive = (last_date == yesterday)
            
            # 计算奖励
            bonus = self.CONSECUTIVE_DAY_BONUS if is_consecutive else self.DAILY_INTERACTION_BONUS
            
            self._add_affection_unlocked(
                user_id,
                bonus,
                "daily_bonus",
                {"consecutive": is_consecutive}
            )
            
            return bonus
    
    async def get_affection_summary(self, user_id: str) -> Dict[str, Any]:
        """
        获取好感度摘要
        
        Args:
            user_id: 用户ID
            
        Returns:
            Dict: 摘要信息
        """
        async with self._get_user_lock(user_id):
            affection = self._get_user_affection_unlocked(user_id)
            
            level = affection.level
            
            return {
                "user_id": user_id,
                "score": affection.score,
                "level_key": level.key,
                "level_label": level.label,
                "level_progress": affection.level_progress,
                "next_level_label": self._get_next_level_label(level),
                "points_to_next": level.max_score - affection.score if level != AffectionLevel.BEST_FRIEND else 0,
                "total_interactions": affection.total_interactions,
                "achievements_count": len(affection.achievements),
                "last_interaction": affection.last_interaction
            }
    
    def _get_next_level_label(self, current: AffectionLevel) -> Optional[str]:
        """获取下一级标签"""
        levels = list(AffectionLevel)
        try:
            current_idx = levels.index(current)
            if current_idx < len(levels) - 1:
                return levels[current_idx + 1].label
        except ValueError:
            pass
        return None
    
    async def get_top_users(self, n: int = 10) -> List[Dict[str, Any]]:
        """
        获取好感度排行
        
        Args:
            n: 返回数量
            
        Returns:
            List[Dict]: 排行列表
        """
        # 获取所有用户
        user_files = list(self.storage_dir.rglob("*_affection.json"))
        
        users = []
        for file_path in user_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    users.append({
                        "user_id": data["user_id"],
                        "score": data.get("score", 0),
                        "level": AffectionLevel.from_score(data.get("score", 0)).label,
                        "total_interactions": data.get("total_interactions", 0)
                    })
            except Exception:
                continue
        
        # 按分数排序
        users.sort(key=lambda x: x["score"], reverse=True)
        
        return users[:n]
    
    async def reset_affection(self, user_id: str):
        """
        重置用户好感度
        
        Args:
            user_id: 用户ID
        """
        async with self._get_user_lock(user_id):
            # 从缓存移除
            if user_id in self._cache:
                del self._cache[user_id]
            
            # 删除文件
            file_path = self._get_user_file_path(user_id)
            if file_path.exists():
                file_path.unlink()
                logger.info(f"🗑️ 好感度已重置: {user_id}")
    
    def clear_cache(self):
        """清空缓存"""
        self._cache.clear()
        logger.debug("🧹 好感度缓存已清空")


# 便捷函数

async def get_user_familiarity_level(
    user_id: str,
    manager: AffectionManager
) -> str:
    """
    获取用户熟悉度（用于Prompt调整）
    
    Args:
        user_id: 用户ID
        manager: 好感度管理器
        
    Returns:
        str: 熟悉度描述
    """
    summary = await manager.get_affection_summary(user_id)
    
    level = summary["level_key"]
    
    familiarity_map = {
        "stranger": "这是你们第一次或很少交流，请保持友好但不过分热情。",
        "acquaintance": "你们已经有过几次交流，可以适当关心对方的近况。",
        "friend": "你们是朋友，可以更加自然地交流，记住对方的偏好。",
        "close_friend": "你们是好朋友，可以更加亲密和个性化地交流。",
        "best_friend": "你们是挚友，可以用最温暖、最了解对方的方式交流。"
    }
    
    return familiarity_map.get(level, familiarity_map["stranger"])