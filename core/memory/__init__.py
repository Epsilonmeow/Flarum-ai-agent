"""
三层记忆系统 - 轻量级实现 (JSON/文件存储)

架构：
- 摘要层 (Summary): 长期对话摘要
- 块层 (Block): 10轮对话打包
- 历史层 (History): 完整原始对话
"""

from .conversation_block import ConversationBlock, BlockStatus
from .layered_memory import LayeredMemory
from .block_manager import BlockManager
from .summary_engine import SummaryEngine

__all__ = [
    "ConversationBlock",
    "BlockStatus", 
    "LayeredMemory",
    "BlockManager",
    "SummaryEngine",
]