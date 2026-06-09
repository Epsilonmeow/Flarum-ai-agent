"""
对话块模型 - 10轮对话打包
轻量级实现，支持JSON序列化
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import List, Dict, Any, Optional
from enum import Enum
import json
import hashlib
import uuid


class BlockStatus(Enum):
    """对话块状态"""
    ACTIVE = "active"           # 活跃中（未满10轮）
    COMPLETED = "completed"     # 已完成（满10轮）
    SUMMARIZED = "summarized"   # 已生成摘要
    ARCHIVED = "archived"       # 已归档


@dataclass
class Message:
    """单条消息"""
    role: str                   # "user" | "assistant" | "system"
    content: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp,
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Message":
        return cls(
            role=data.get("role", "user"),
            content=data.get("content", ""),
            timestamp=data.get("timestamp", datetime.now().isoformat()),
            metadata=data.get("metadata", {})
        )


@dataclass
class ConversationBlock:
    """
    对话块 - 最多10轮对话的容器
    
    Attributes:
        block_id: 唯一标识
        user_id: 所属用户
        messages: 消息列表
        status: 块状态
        created_at: 创建时间
        updated_at: 最后更新时间
        summary: 摘要（生成后填充）
        embedding: 向量嵌入（可选）
        turn_count: 轮次计数（user+assistant算一轮）
    """
    
    # 类常量：每块最大轮数
    MAX_TURNS_PER_BLOCK: int = 10
    
    block_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    user_id: str = field(default="unknown")
    messages: List[Message] = field(default_factory=list)
    status: BlockStatus = BlockStatus.ACTIVE
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    summary: Optional[str] = None
    embedding: Optional[List[float]] = None
    turn_count: int = 0
    
    def __post_init__(self):
        """初始化后计算轮数"""
        self._recalculate_turn_count()
    
    def _recalculate_turn_count(self):
        """重新计算对话轮数"""
        # 计算 user-assistant 对数
        turns = 0
        i = 0
        while i < len(self.messages) - 1:
            if (self.messages[i].role == "user" and 
                self.messages[i + 1].role == "assistant"):
                turns += 1
                i += 2
            else:
                i += 1
        self.turn_count = turns
    
    @property
    def is_full(self) -> bool:
        """检查是否已满10轮"""
        return self.turn_count >= self.MAX_TURNS_PER_BLOCK
    
    @property
    def is_empty(self) -> bool:
        """检查是否为空"""
        return len(self.messages) == 0
    
    @property
    def message_count(self) -> int:
        """消息数量"""
        return len(self.messages)
    
    def add_message(self, role: str, content: str, metadata: Optional[Dict] = None) -> "Message":
        """
        添加消息到块
        
        Args:
            role: 角色
            content: 内容
            metadata: 元数据
            
        Returns:
            Message: 添加的消息
            
        Raises:
            ValueError: 块已满时抛出
        """
        if self.is_full and role == "user":
            raise ValueError(f"块 {self.block_id} 已满 ({self.MAX_TURNS_PER_BLOCK}轮)")
        
        msg = Message(
            role=role,
            content=content,
            metadata=metadata or {}
        )
        self.messages.append(msg)
        self.updated_at = datetime.now().isoformat()
        
        # 更新状态
        if role == "assistant":
            self._recalculate_turn_count()
            if self.is_full:
                self.status = BlockStatus.COMPLETED
        
        return msg
    
    def add_user_message(self, content: str, metadata: Optional[Dict] = None) -> "Message":
        """添加用户消息"""
        return self.add_message("user", content, metadata)
    
    def add_assistant_message(self, content: str, metadata: Optional[Dict] = None) -> "Message":
        """添加AI回复"""
        return self.add_message("assistant", content, metadata)
    
    def get_conversation_text(self) -> str:
        """
        获取对话文本（用于摘要）
        
        Returns:
            str: 格式化的对话文本
        """
        lines = []
        for msg in self.messages:
            role_name = "用户" if msg.role == "user" else "树洞喵" if msg.role == "assistant" else "系统"
            lines.append(f"{role_name}: {msg.content}")
        return "\n".join(lines)
    
    def get_last_n_turns(self, n: int) -> List[Message]:
        """
        获取最近n轮的对话
        
        Args:
            n: 轮数
            
        Returns:
            List[Message]: 消息列表
        """
        # 找到最近n轮的起始位置
        turn_count = 0
        start_idx = len(self.messages)
        
        for i in range(len(self.messages) - 1, -1, -1):
            if i > 0 and self.messages[i].role == "assistant" and self.messages[i-1].role == "user":
                turn_count += 1
                if turn_count == n:
                    start_idx = i - 1
                    break
        
        return self.messages[start_idx:]
    
    def set_summary(self, summary: str):
        """设置摘要"""
        self.summary = summary
        self.status = BlockStatus.SUMMARIZED
        self.updated_at = datetime.now().isoformat()
    
    def set_embedding(self, embedding: List[float]):
        """设置向量嵌入"""
        self.embedding = embedding
        self.updated_at = datetime.now().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典（用于JSON序列化）"""
        return {
            "block_id": self.block_id,
            "user_id": self.user_id,
            "messages": [m.to_dict() for m in self.messages],
            "status": self.status.value,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "summary": self.summary,
            "embedding": self.embedding,
            "turn_count": self.turn_count
        }
    
    def to_json(self, indent: Optional[int] = None) -> str:
        """转换为JSON字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ConversationBlock":
        """从字典创建"""
        block = cls(
            block_id=data["block_id"],
            user_id=data["user_id"],
            messages=[Message.from_dict(m) for m in data.get("messages", [])],
            status=BlockStatus(data.get("status", "active")),
            created_at=data.get("created_at", datetime.now().isoformat()),
            updated_at=data.get("updated_at", datetime.now().isoformat()),
            summary=data.get("summary"),
            embedding=data.get("embedding"),
            turn_count=data.get("turn_count", 0)
        )
        return block
    
    @classmethod
    def from_json(cls, json_str: str) -> "ConversationBlock":
        """从JSON字符串创建"""
        return cls.from_dict(json.loads(json_str))
    
    @classmethod
    def create_new(cls, user_id: str, block_index: int = 0) -> "ConversationBlock":
        """
        创建新块
        
        Args:
            user_id: 用户ID
            block_index: 块序号（用于生成block_id）
            
        Returns:
            ConversationBlock: 新块
        """
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        block_id = f"{user_id}_block_{block_index}_{timestamp}"
        
        return cls(
            block_id=block_id,
            user_id=user_id
        )
    
    def get_hash(self) -> str:
        """获取内容哈希（用于去重）"""
        content = self.get_conversation_text()
        return hashlib.md5(content.encode()).hexdigest()[:16]


# ============ 便捷函数 ============

def create_block_from_conversation(
    user_id: str,
    conversation: List[Dict[str, str]],
    block_index: int = 0
) -> ConversationBlock:
    """
    从对话列表创建块
    
    Args:
        user_id: 用户ID
        conversation: [{"role": "user"/"assistant", "content": "..."}]
        block_index: 块序号
        
    Returns:
        ConversationBlock: 创建的块
    """
    block = ConversationBlock.create_new(user_id, block_index)
    
    for msg in conversation:
        block.add_message(
            role=msg.get("role", "user"),
            content=msg.get("content", ""),
            metadata=msg.get("metadata", {})
        )
    
    return block


def split_conversation_to_blocks(
    user_id: str,
    conversation: List[Dict[str, str]],
    max_turns: int = 10
) -> List[ConversationBlock]:
    """
    将长对话分割成多个块
    
    Args:
        user_id: 用户ID
        conversation: 完整对话
        max_turns: 每块最大轮数
        
    Returns:
        List[ConversationBlock]: 块列表
    """
    blocks = []
    current_block_conversation = []
    current_turns = 0
    
    i = 0
    while i < len(conversation):
        msg = conversation[i]
        current_block_conversation.append(msg)
        
        # 检测一轮结束（user + assistant）
        if (msg.get("role") == "assistant" and 
            i > 0 and 
            conversation[i-1].get("role") == "user"):
            current_turns += 1
            
            # 达到最大轮数，创建新块
            if current_turns >= max_turns:
                blocks.append(create_block_from_conversation(
                    user_id, 
                    current_block_conversation, 
                    len(blocks)
                ))
                current_block_conversation = []
                current_turns = 0
        
        i += 1
    
    # 处理剩余对话
    if current_block_conversation:
        blocks.append(create_block_from_conversation(
            user_id,
            current_block_conversation,
            len(blocks)
        ))
    
    return blocks