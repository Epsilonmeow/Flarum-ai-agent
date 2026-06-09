"""
三层记忆系统 - 轻量级JSON实现

架构层次：
L1 - 摘要层 (Summary Layer): 长期对话摘要，用于快速回忆用户历史
L2 - 块层 (Block Layer): 10轮对话块，用于中等粒度检索  
L3 - 历史层 (History Layer): 完整原始对话，用于精确回溯
"""

import asyncio
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field

from .conversation_block import ConversationBlock, Message, BlockStatus

logger = logging.getLogger(__name__)


@dataclass
class UserMemory:
    """
    用户完整记忆结构
    
    Attributes:
        user_id: 用户ID
        summaries: 所有摘要列表（L1）
        blocks: 所有对话块（L2）
        current_block: 当前活跃块
        total_turns: 总对话轮数
        created_at: 首次对话时间
        updated_at: 最后更新时间
        metadata: 用户元数据
    """
    
    user_id: str
    summaries: List[str] = field(default_factory=list)
    blocks: List[ConversationBlock] = field(default_factory=list)
    current_block: Optional[ConversationBlock] = None
    total_turns: int = 0
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """确保有当前活跃块"""
        if self.current_block is None:
            self._create_new_block()
    
    def _create_new_block(self) -> ConversationBlock:
        """创建新块作为当前块"""
        block = ConversationBlock.create_new(
            self.user_id,
            block_index=len(self.blocks)
        )
        self.current_block = block
        self.blocks.append(block)
        logger.debug(f"🆕 为用户 {self.user_id} 创建新块: {block.block_id}")
        return block
    
    def add_message(self, role: str, content: str, metadata: Optional[Dict] = None) -> Message:
        """
        添加消息到记忆
        
        Args:
            role: 角色
            content: 内容
            metadata: 元数据
            
        Returns:
            Message: 添加的消息
        """
        # 检查当前块是否已满
        if self.current_block and self.current_block.is_full:
            self._create_new_block()
        
        # 确保有当前块
        if self.current_block is None:
            self._create_new_block()
        
        # 添加消息
        msg = self.current_block.add_message(role, content, metadata)
        
        # 更新统计
        if role == "assistant":
            self.total_turns += 1
        
        self.updated_at = datetime.now().isoformat()
        
        return msg
    
    def add_summary(self, summary: str):
        """
        添加摘要到L1层
        
        Args:
            summary: 摘要文本
        """
        self.summaries.append(summary)
        self.updated_at = datetime.now().isoformat()
        logger.debug(f"📝 为用户 {self.user_id} 添加摘要 #{len(self.summaries)}")
    
    def get_recent_blocks(self, n: int = 2) -> List[ConversationBlock]:
        """
        获取最近n个块
        
        Args:
            n: 块数量
            
        Returns:
            List[ConversationBlock]: 块列表（从新到旧）
        """
        # 排除当前活跃块（如果未满）
        completed_blocks = [b for b in self.blocks if b.is_full]
        
        # 按创建时间排序（最新的在前）
        sorted_blocks = sorted(
            completed_blocks,
            key=lambda b: b.created_at,
            reverse=True
        )
        
        return sorted_blocks[:n]
    
    def get_all_summaries_text(self, max_summaries: Optional[int] = None) -> str:
        """
        获取所有摘要文本（用于Prompt注入）

        Args:
            max_summaries: 最多注入的摘要数量；None 表示全部注入
        
        Returns:
            str: 格式化摘要
        """
        if not self.summaries:
            return ""
        
        summaries = self.summaries[-max_summaries:] if max_summaries else self.summaries

        lines = ["【历史对话摘要】"]
        for i, summary in enumerate(summaries, 1):
            lines.append(f"  {i}. {summary}")
        
        return "\n".join(lines)
    
    def get_recent_context(self, max_messages: int = 5) -> List[Dict[str, str]]:
        """
        获取最近对话上下文（用于Prompt）
        
        Args:
            max_messages: 最大消息数
            
        Returns:
            List[Dict]: [{"role": "...", "content": "..."}]
        """
        messages = []
        
        # 1. 首先尝试从当前块获取
        if self.current_block:
            messages = self.current_block.messages[-max_messages:]
        
        # 2. 如果不够，从之前的块补充
        if len(messages) < max_messages and len(self.blocks) > 1:
            remaining = max_messages - len(messages)
            # 获取倒数第二个块
            if len(self.blocks) >= 2:
                prev_block = self.blocks[-2]
                prev_messages = prev_block.messages[-remaining:]
                messages = prev_messages + messages
        
        # 转换为字典格式
        return [{"role": m.role, "content": m.content} for m in messages]
    
    def get_full_conversation(self) -> List[Dict[str, str]]:
        """
        获取完整对话历史（L3层）
        
        Returns:
            List[Dict]: 所有消息
        """
        messages = []
        for block in self.blocks:
            for msg in block.messages:
                messages.append({
                    "role": msg.role,
                    "content": msg.content,
                    "timestamp": msg.timestamp
                })
        return messages
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "user_id": self.user_id,
            "summaries": self.summaries,
            "blocks": [b.to_dict() for b in self.blocks],
            "current_block_id": self.current_block.block_id if self.current_block else None,
            "total_turns": self.total_turns,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UserMemory":
        """从字典创建"""
        memory = cls(
            user_id=data["user_id"],
            summaries=data.get("summaries", []),
            blocks=[ConversationBlock.from_dict(b) for b in data.get("blocks", [])],
            total_turns=data.get("total_turns", 0),
            created_at=data.get("created_at", datetime.now().isoformat()),
            updated_at=data.get("updated_at", datetime.now().isoformat()),
            metadata=data.get("metadata", {})
        )
        
        # 恢复当前块引用
        current_block_id = data.get("current_block_id")
        if current_block_id:
            for block in memory.blocks:
                if block.block_id == current_block_id:
                    memory.current_block = block
                    break
        
        # 如果没有当前块，创建新块
        if memory.current_block is None and memory.blocks:
            memory.current_block = memory.blocks[-1]
        
        return memory


class LayeredMemory:
    """
    三层记忆系统管理器
    
    轻量级实现：使用JSON文件存储，无需PostgreSQL
    """
    
    def __init__(self, storage_dir: Path):
        """
        初始化
        
        Args:
            storage_dir: 存储目录路径
        """
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        
        # 内存缓存
        self._cache: Dict[str, UserMemory] = {}
        self._locks: Dict[str, asyncio.Lock] = {}
        
        logger.info(f"🧠 三层记忆系统初始化: {self.storage_dir}")
    
    def _get_user_lock(self, user_id: str) -> asyncio.Lock:
        """获取用户级异步锁，避免同一用户记忆被并发读写覆盖"""
        if user_id not in self._locks:
            self._locks[user_id] = asyncio.Lock()
        return self._locks[user_id]
    
    def _get_user_file_path(self, user_id: str) -> Path:
        """获取用户记忆文件路径"""
        # 使用子目录分散文件，避免单目录文件过多
        # 取user_id前2个字符作为子目录名
        subdir = user_id[:2] if len(user_id) >= 2 else "xx"
        user_dir = self.storage_dir / subdir
        user_dir.mkdir(exist_ok=True)
        return user_dir / f"{user_id}.json"
    
    def _backup_corrupt_file(self, file_path: Path, user_id: str):
        """备份损坏的 JSON 文件，避免后续排查时丢失现场"""
        if not file_path.exists():
            return
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        backup_path = file_path.with_name(f"{file_path.name}.corrupt.{timestamp}")
        try:
            file_path.replace(backup_path)
            logger.warning(f"⚠️ 已备份损坏的用户记忆文件: {user_id} -> {backup_path.name}")
        except Exception as backup_error:
            logger.error(f"❌ 备份损坏记忆文件失败 {user_id}: {backup_error}")
    
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
                    logger.debug(f"清理临时记忆文件失败: {tmp_path}")
    
    def _load_user_memory_unlocked(self, user_id: str) -> UserMemory:
        """加载用户记忆；调用方需要自行持有用户锁"""
        # 检查缓存
        if user_id in self._cache:
            return self._cache[user_id]
        
        # 从文件加载
        file_path = self._get_user_file_path(user_id)
        
        if file_path.exists():
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                memory = UserMemory.from_dict(data)
                logger.debug(f"📂 加载用户记忆: {user_id} ({len(memory.blocks)} 块)")
            except Exception as e:
                logger.error(f"❌ 加载用户记忆失败 {user_id}: {e}")
                self._backup_corrupt_file(file_path, user_id)
                memory = UserMemory(user_id=user_id)
        else:
            memory = UserMemory(user_id=user_id)
            logger.debug(f"🆕 新建用户记忆: {user_id}")
        
        # 缓存
        self._cache[user_id] = memory
        return memory
    
    def _save_user_memory_unlocked(self, user_id: str):
        """保存用户记忆；调用方需要自行持有用户锁"""
        if user_id not in self._cache:
            logger.warning(f"⚠️ 用户 {user_id} 不在缓存中，无法保存")
            return
        
        memory = self._cache[user_id]
        file_path = self._get_user_file_path(user_id)
        
        try:
            self._atomic_write_json(file_path, memory.to_dict())
            logger.debug(f"💾 保存用户记忆: {user_id}")
        except Exception as e:
            logger.error(f"❌ 保存用户记忆失败 {user_id}: {e}")
    
    async def load_user_memory(self, user_id: str) -> UserMemory:
        """
        加载用户记忆
        
        Args:
            user_id: 用户ID
            
        Returns:
            UserMemory: 用户记忆对象
        """
        async with self._get_user_lock(user_id):
            return self._load_user_memory_unlocked(user_id)
    
    async def save_user_memory(self, user_id: str):
        """
        保存用户记忆
        
        Args:
            user_id: 用户ID
        """
        async with self._get_user_lock(user_id):
            self._save_user_memory_unlocked(user_id)
    
    async def add_message(
        self,
        user_id: str,
        role: str,
        content: str,
        metadata: Optional[Dict] = None
    ) -> Tuple[Message, bool]:
        """
        添加消息到用户记忆
        
        Args:
            user_id: 用户ID
            role: 角色
            content: 内容
            metadata: 元数据
            
        Returns:
            Tuple[Message, bool]: (消息, 是否新块)
        """
        async with self._get_user_lock(user_id):
            memory = self._load_user_memory_unlocked(user_id)
            
            # 记录添加前块数
            prev_block_count = len(memory.blocks)
            
            # 添加消息
            msg = memory.add_message(role, content, metadata)
            
            # 检查是否创建了新块
            new_block_created = len(memory.blocks) > prev_block_count
            
            # 保存
            self._save_user_memory_unlocked(user_id)
            
            return msg, new_block_created
    
    async def add_summary(self, user_id: str, summary: str):
        """
        添加摘要
        
        Args:
            user_id: 用户ID
            summary: 摘要文本
        """
        async with self._get_user_lock(user_id):
            memory = self._load_user_memory_unlocked(user_id)
            memory.add_summary(summary)
            self._save_user_memory_unlocked(user_id)
    
    async def get_memory_for_prompt(
        self,
        user_id: str,
        include_summaries: bool = True,
        max_recent_blocks: int = 1,
        max_context_messages: int = 5,
        max_summaries: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        获取用于Prompt的记忆内容
        
        Args:
            user_id: 用户ID
            include_summaries: 是否包含摘要层
            max_recent_blocks: 包含的最近块数
            max_context_messages: 最大上下文消息数
            max_summaries: 最大摘要数量
            
        Returns:
            Dict: {
                "summaries": str,  # 摘要文本
                "recent_blocks": List[ConversationBlock],
                "recent_context": List[Dict]  # 可直接用于messages
            }
        """
        async with self._get_user_lock(user_id):
            memory = self._load_user_memory_unlocked(user_id)
            
            result = {
                "summaries": memory.get_all_summaries_text(max_summaries) if include_summaries else "",
                "recent_blocks": memory.get_recent_blocks(max_recent_blocks),
                "recent_context": memory.get_recent_context(max_context_messages),
                "total_turns": memory.total_turns
            }
            
            return result
    
    async def get_blocks_needing_summary(self, user_id: str, min_completed: int = 2) -> List[ConversationBlock]:
        """
        获取需要摘要的块（已完成但未摘要）
        
        Args:
            user_id: 用户ID
            min_completed: 最少完成的块数（触发摘要的阈值）
            
        Returns:
            List[ConversationBlock]: 需要摘要的块
        """
        async with self._get_user_lock(user_id):
            memory = self._load_user_memory_unlocked(user_id)
            
            # 获取已完成但未摘要的块
            pending_blocks = [
                b for b in memory.blocks 
                if b.is_full and b.status == BlockStatus.COMPLETED and not b.summary
            ]
            
            # 按创建时间排序
            pending_blocks.sort(key=lambda b: b.created_at)
            
            # 只有积累足够的块才触发摘要
            if len(pending_blocks) >= min_completed:
                return pending_blocks[:min_completed]
            
            return []
    
    async def update_block_summary(
        self,
        user_id: str,
        block_id: str,
        summary: str
    ):
        """
        更新块的摘要
        
        Args:
            user_id: 用户ID
            block_id: 块ID
            summary: 摘要文本
        """
        async with self._get_user_lock(user_id):
            memory = self._load_user_memory_unlocked(user_id)
            
            for block in memory.blocks:
                if block.block_id == block_id:
                    block.set_summary(summary)
                    break
            
            self._save_user_memory_unlocked(user_id)
    
    async def get_user_stats(self, user_id: str) -> Dict[str, Any]:
        """
        获取用户对话统计
        
        Args:
            user_id: 用户ID
            
        Returns:
            Dict: 统计信息
        """
        async with self._get_user_lock(user_id):
            memory = self._load_user_memory_unlocked(user_id)
            
            return {
                "user_id": user_id,
                "total_turns": memory.total_turns,
                "total_blocks": len(memory.blocks),
                "summaries_count": len(memory.summaries),
                "first_interaction": memory.created_at,
                "last_interaction": memory.updated_at
            }
    
    async def clear_user_memory(self, user_id: str):
        """
        清空用户记忆（隐私保护）
        
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
                logger.info(f"🗑️ 用户记忆已删除: {user_id}")
    
    async def get_all_user_ids(self) -> List[str]:
        """
        获取所有用户ID
        
        Returns:
            List[str]: 用户ID列表
        """
        user_ids = []
        
        for subdir in self.storage_dir.iterdir():
            if subdir.is_dir():
                for file_path in subdir.glob("*.json"):
                    user_id = file_path.stem
                    user_ids.append(user_id)
        
        return user_ids
    
    def clear_cache(self):
        """清空内存缓存"""
        self._cache.clear()
        logger.debug("🧹 记忆缓存已清空")