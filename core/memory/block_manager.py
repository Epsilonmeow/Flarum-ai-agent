"""
块生命周期管理器
管理对话块的创建、合并、归档等生命周期操作
"""

import logging
from typing import List, Optional, Dict, Any
from datetime import datetime

from .conversation_block import ConversationBlock, BlockStatus
from .layered_memory import LayeredMemory, UserMemory

logger = logging.getLogger(__name__)


class BlockManager:
    """
    块生命周期管理器
    
    职责：
    - 管理块创建策略（自动分块）
    - 块合并与压缩
    - 块归档（减少内存占用）
    - 块检索与排序
    """
    
    # 配置常量
    DEFAULT_MAX_TURNS_PER_BLOCK = 10
    DEFAULT_MAX_ACTIVE_BLOCKS = 5  # 内存中保留的最大活跃块数
    
    def __init__(
        self,
        layered_memory: LayeredMemory,
        max_turns_per_block: int = 10,
        max_active_blocks: int = 5
    ):
        """
        初始化
        
        Args:
            layered_memory: 三层记忆系统
            max_turns_per_block: 每块最大轮数
            max_active_blocks: 最大活跃块数
        """
        self.memory = layered_memory
        self.max_turns = max_turns_per_block
        self.max_active = max_active_blocks
        
        logger.info(f"🧱 块生命周期管理器初始化 (max_turns={max_turns_per_block})")
    
    async def get_or_create_active_block(self, user_id: str) -> ConversationBlock:
        """
        获取或创建活跃块
        
        Args:
            user_id: 用户ID
            
        Returns:
            ConversationBlock: 活跃块（未满的块）
        """
        memory = await self.memory.load_user_memory(user_id)
        
        # 检查当前块
        if memory.current_block and not memory.current_block.is_full:
            return memory.current_block
        
        # 创建新块
        new_block = memory._create_new_block()
        await self.memory.save_user_memory(user_id)
        
        logger.info(f"🆕 创建新块: {new_block.block_id} (用户: {user_id})")
        return new_block
    
    async def finalize_block(self, user_id: str, block_id: str) -> bool:
        """
        手动结束一个块（即使未满）
        
        Args:
            user_id: 用户ID
            block_id: 块ID
            
        Returns:
            bool: 是否成功
        """
        memory = await self.memory.load_user_memory(user_id)
        
        for block in memory.blocks:
            if block.block_id == block_id:
                if block.status == BlockStatus.ACTIVE:
                    block.status = BlockStatus.COMPLETED
                    block.updated_at = datetime.now().isoformat()
                    await self.memory.save_user_memory(user_id)
                    logger.info(f"✅ 块已结束: {block_id}")
                    return True
                return False
        
        logger.warning(f"⚠️ 未找到块: {block_id}")
        return False
    
    async def merge_blocks(
        self,
        user_id: str,
        block_ids: List[str],
        new_summary: Optional[str] = None
    ) -> Optional[ConversationBlock]:
        """
        合并多个块
        
        Args:
            user_id: 用户ID
            block_ids: 要合并的块ID列表
            new_summary: 合并后的摘要
            
        Returns:
            Optional[ConversationBlock]: 合并后的新块
        """
        if len(block_ids) < 2:
            return None
        
        memory = await self.memory.load_user_memory(user_id)
        
        # 找到要合并的块
        blocks_to_merge = []
        for block_id in block_ids:
            for block in memory.blocks:
                if block.block_id == block_id:
                    blocks_to_merge.append(block)
                    break
        
        if len(blocks_to_merge) < 2:
            logger.warning(f"⚠️ 找到的可合并块数量不足: {len(blocks_to_merge)}")
            return None
        
        # 按创建时间排序
        blocks_to_merge.sort(key=lambda b: b.created_at)
        
        # 合并消息
        merged_messages = []
        for block in blocks_to_merge:
            merged_messages.extend(block.messages)
        
        # 创建新块
        new_block = ConversationBlock.create_new(user_id, block_index=len(memory.blocks))
        new_block.messages = merged_messages
        new_block._recalculate_turn_count()
        new_block.summary = new_summary or self._generate_merge_summary(blocks_to_merge)
        
        if new_block.is_full:
            new_block.status = BlockStatus.COMPLETED
        
        # 更新内存
        # 移除旧块，添加新块
        memory.blocks = [b for b in memory.blocks if b.block_id not in block_ids]
        memory.blocks.append(new_block)
        
        # 更新当前块引用（如果被移除的是当前块）
        if memory.current_block and memory.current_block.block_id in block_ids:
            memory.current_block = new_block
        
        await self.memory.save_user_memory(user_id)
        
        logger.info(
            f"🔄 块合并完成: {len(blocks_to_merge)} 个块 -> {new_block.block_id} "
            f"({new_block.turn_count} 轮)"
        )
        
        return new_block
    
    def _generate_merge_summary(self, blocks: List[ConversationBlock]) -> str:
        """为合并的块生成摘要提示"""
        summaries = []
        for i, block in enumerate(blocks, 1):
            if block.summary:
                summaries.append(f"段{i}: {block.summary}")
            else:
                # 提取前50字作为预览
                preview = block.get_conversation_text()[:50] + "..."
                summaries.append(f"段{i}: {preview}")
        
        return " | ".join(summaries)
    
    async def archive_old_blocks(self, user_id: str, keep_recent: int = 3) -> int:
        """
        归档旧块（释放内存，但保留摘要）
        
        Args:
            user_id: 用户ID
            keep_recent: 保留的最近块数
            
        Returns:
            int: 归档的块数
        """
        memory = await self.memory.load_user_memory(user_id)
        
        # 获取已完成且未归档的块
        archivable = [
            b for b in memory.blocks 
            if b.is_full and b.status != BlockStatus.ARCHIVED
        ]
        
        # 按时间排序，保留最近的
        archivable.sort(key=lambda b: b.created_at, reverse=True)
        to_archive = archivable[keep_recent:]
        
        archived_count = 0
        for block in to_archive:
            # 归档：只保留摘要，清空消息
            if not block.summary:
                # 如果还没摘要，先生成简单摘要
                block.summary = self._quick_summarize(block)
            
            # 清空消息以节省空间（但保留摘要）
            block.messages = []
            block.status = BlockStatus.ARCHIVED
            block.updated_at = datetime.now().isoformat()
            archived_count += 1
        
        if archived_count > 0:
            await self.memory.save_user_memory(user_id)
            logger.info(f"📦 已归档 {archived_count} 个旧块 (用户: {user_id})")
        
        return archived_count
    
    def _quick_summarize(self, block: ConversationBlock) -> str:
        """快速生成块的简单摘要"""
        # 统计信息
        user_msgs = sum(1 for m in block.messages if m.role == "user")
        ai_msgs = sum(1 for m in block.messages if m.role == "assistant")
        
        # 提取第一个用户消息作为主题
        first_topic = ""
        for m in block.messages:
            if m.role == "user":
                first_topic = m.content[:30] + "..." if len(m.content) > 30 else m.content
                break
        
        return f"对话({user_msgs}问{ai_msgs}答)，主题: {first_topic}"
    
    async def get_block_by_id(self, user_id: str, block_id: str) -> Optional[ConversationBlock]:
        """
        根据ID获取块
        
        Args:
            user_id: 用户ID
            block_id: 块ID
            
        Returns:
            Optional[ConversationBlock]: 找到的块
        """
        memory = await self.memory.load_user_memory(user_id)
        
        for block in memory.blocks:
            if block.block_id == block_id:
                return block
        
        return None
    
    async def search_blocks_by_content(
        self,
        user_id: str,
        keyword: str,
        max_results: int = 5
    ) -> List[Dict[str, Any]]:
        """
        在块内容中搜索关键词（简单字符串匹配）
        
        Args:
            user_id: 用户ID
            keyword: 关键词
            max_results: 最大结果数
            
        Returns:
            List[Dict]: 匹配的块信息
        """
        memory = await self.memory.load_user_memory(user_id)
        
        results = []
        for block in memory.blocks:
            # 跳过已归档且清空的块
            if block.status == BlockStatus.ARCHIVED and not block.messages:
                # 检查摘要
                if block.summary and keyword in block.summary:
                    results.append({
                        "block_id": block.block_id,
                        "match_in": "summary",
                        "preview": block.summary[:100],
                        "created_at": block.created_at
                    })
                continue
            
            # 检查消息内容
            for msg in block.messages:
                if keyword in msg.content:
                    preview = msg.content[:100] + "..." if len(msg.content) > 100 else msg.content
                    results.append({
                        "block_id": block.block_id,
                        "match_in": msg.role,
                        "preview": preview,
                        "timestamp": msg.timestamp,
                        "created_at": block.created_at
                    })
                    break  # 每个块只返回一个结果
            
            if len(results) >= max_results:
                break
        
        return results
    
    async def get_block_statistics(self, user_id: str) -> Dict[str, Any]:
        """
        获取用户的块统计信息
        
        Args:
            user_id: 用户ID
            
        Returns:
            Dict: 统计信息
        """
        memory = await self.memory.load_user_memory(user_id)
        
        total_blocks = len(memory.blocks)
        active_blocks = sum(1 for b in memory.blocks if b.status == BlockStatus.ACTIVE)
        completed_blocks = sum(1 for b in memory.blocks if b.status == BlockStatus.COMPLETED)
        summarized_blocks = sum(1 for b in memory.blocks if b.status == BlockStatus.SUMMARIZED)
        archived_blocks = sum(1 for b in memory.blocks if b.status == BlockStatus.ARCHIVED)
        
        total_messages = sum(len(b.messages) for b in memory.blocks)
        avg_turns_per_block = sum(b.turn_count for b in memory.blocks) / total_blocks if total_blocks > 0 else 0
        
        return {
            "user_id": user_id,
            "total_blocks": total_blocks,
            "active_blocks": active_blocks,
            "completed_blocks": completed_blocks,
            "summarized_blocks": summarized_blocks,
            "archived_blocks": archived_blocks,
            "total_messages": total_messages,
            "avg_turns_per_block": round(avg_turns_per_block, 2),
            "total_summaries": len(memory.summaries)
        }
    
    async def cleanup_orphaned_blocks(self, user_id: str) -> int:
        """
        清理孤立的空块
        
        Args:
            user_id: 用户ID
            
        Returns:
            int: 清理的块数
        """
        memory = await self.memory.load_user_memory(user_id)
        
        # 保留的块（有消息或已归档的）
        blocks_to_keep = [
            b for b in memory.blocks 
            if len(b.messages) > 0 or b.status == BlockStatus.ARCHIVED
        ]
        
        removed_count = len(memory.blocks) - len(blocks_to_keep)
        
        if removed_count > 0:
            memory.blocks = blocks_to_keep
            
            # 更新当前块引用
            if memory.current_block and memory.current_block not in blocks_to_keep:
                # 找到最新的非空块
                for block in reversed(blocks_to_keep):
                    if len(block.messages) > 0:
                        memory.current_block = block
                        break
                else:
                    # 没有可用块，创建新块
                    memory._create_new_block()
            
            await self.memory.save_user_memory(user_id)
            logger.info(f"🧹 清理 {removed_count} 个孤立块 (用户: {user_id})")
        
        return removed_count


# ============ 便捷函数 ============

async def optimize_user_memory(
    user_id: str,
    layered_memory: LayeredMemory,
    archive_threshold: int = 5
):
    """
    优化用户内存（归档旧块，清理孤立块）
    
    Args:
        user_id: 用户ID
        layered_memory: 三层记忆系统
        archive_threshold: 归档阈值（保留多少块不归档）
    """
    manager = BlockManager(layered_memory)
    
    # 归档旧块
    await manager.archive_old_blocks(user_id, keep_recent=archive_threshold)
    
    # 清理孤立块
    await manager.cleanup_orphaned_blocks(user_id)
    
    logger.info(f"✅ 内存优化完成: {user_id}")