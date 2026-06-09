"""
LLM 引擎模块 - 重构版
适配 SillyTavern 原生 JSON 格式，支持 Output Regex 和极简 Preset 拼接
"""

import json
import re
import logging
from typing import Optional, List, Dict, Any, Tuple
from pathlib import Path
from dataclasses import dataclass, field

# 使用 openai 官方库的异步客户端
from openai import AsyncOpenAI

import config

logger = logging.getLogger(__name__)


# ============ 数据模型 ============

@dataclass
class WorldBookEntry:
    """SillyTavern 格式的世界书条目"""
    uid: str                          # 条目ID (entries 的 key)
    keys: List[str]                   # 触发关键词列表
    content: str                      # 世界书内容
    constant: bool = False            # 是否常驻
    comment: str = ""                 # 备注/标题
    order: int = 0                    # 排序权重
    
    @classmethod
    def from_dict(cls, uid: str, data: Dict) -> "WorldBookEntry":
        """从 SillyTavern JSON 解析"""
        return cls(
            uid=uid,
            keys=data.get("key", []),
            content=data.get("content", ""),
            constant=data.get("constant", False),
            comment=data.get("comment", ""),
            order=int(uid) if uid.isdigit() else 0
        )


@dataclass
class RegexRule:
    """正则替换规则"""
    name: str
    pattern: str
    replacement: str
    enabled: bool = True
    
    def apply(self, text: str) -> str:
        """应用正则替换"""
        if not self.enabled:
            return text
        try:
            return re.sub(self.pattern, self.replacement, text, flags=re.DOTALL)
        except re.error as e:
            logger.error(f"❌ 正则规则 '{self.name}' 错误: {str(e)}")
            return text


# ============ 世界书加载器 ============

class WorldBookLoader:
    """
    SillyTavern 格式世界书加载器
    
    支持:
    - 原生 SillyTavern entries 格式
    - 热重载 (文件修改自动刷新)
    - 常驻词条 (constant: true) 与触发词条分离
    """
    
    _instance = None
    _entries: Dict[str, WorldBookEntry] = {}
    _constant_entries: List[WorldBookEntry] = []
    _trigger_entries: List[WorldBookEntry] = []
    _last_modified: float = 0
    
    def __new__(cls):
        """单例模式"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def load(self) -> Tuple[List[WorldBookEntry], List[WorldBookEntry]]:
        """
        加载世界书并分离常驻/触发词条
        
        Returns:
            (constant_entries, trigger_entries): 常驻词条列表和触发词条列表
        """
        try:
            worldbook_path = config.WORLD_BOOK_PATH
            
            if not worldbook_path.exists():
                logger.warning(f"⚠️ 世界书文件不存在: {worldbook_path}")
                return [], []
            
            # 检查文件是否更新
            current_mtime = worldbook_path.stat().st_mtime
            if self._entries and current_mtime <= self._last_modified:
                return self._constant_entries, self._trigger_entries
            
            # 重新加载
            with open(worldbook_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 解析 SillyTavern 格式
            entries_data = data.get("entries", {})
            if not entries_data:
                logger.warning("⚠️ 世界书 entries 为空")
                return [], []
            
            # 清空缓存
            self._entries = {}
            self._constant_entries = []
            self._trigger_entries = []
            
            # 解析所有条目
            for uid, entry_data in entries_data.items():
                entry = WorldBookEntry.from_dict(uid, entry_data)
                self._entries[uid] = entry
                
                if entry.constant:
                    self._constant_entries.append(entry)
                    logger.debug(f"📌 常驻词条: [{uid}] {entry.comment}")
                else:
                    self._trigger_entries.append(entry)
                    logger.debug(f"🎯 触发词条: [{uid}] {entry.comment}")
            
            # 按 order 排序
            self._constant_entries.sort(key=lambda x: x.order)
            self._trigger_entries.sort(key=lambda x: x.order)
            
            self._last_modified = current_mtime
            
            logger.info(
                f"📚 世界书加载成功: "
                f"{len(self._constant_entries)} 常驻, "
                f"{len(self._trigger_entries)} 触发"
            )
            
            return self._constant_entries, self._trigger_entries
            
        except json.JSONDecodeError as e:
            logger.error(f"❌ 世界书 JSON 格式错误: {str(e)}")
            return [], []
        except Exception as e:
            logger.exception(f"❌ 加载世界书失败: {str(e)}")
            return [], []
    
    def reload(self):
        """强制重新加载"""
        self._entries = {}
        return self.load()
    
    def get_entry_by_uid(self, uid: str) -> Optional[WorldBookEntry]:
        """根据 UID 获取条目"""
        return self._entries.get(uid)


# ============ 世界书匹配引擎 ============

class WorldBookMatcher:
    """世界书匹配引擎"""
    
    def __init__(self):
        self.loader = WorldBookLoader()
    
    def match(self, user_text: str) -> Tuple[str, List[str]]:
        """
        匹配用户输入与触发词条
        
        Args:
            user_text: 用户输入文本
            
        Returns:
            (matched_content, matched_uids): 匹配到的内容和条目ID列表
        """
        if not user_text:
            return "", []
        
        # 加载词条
        constant_entries, trigger_entries = self.loader.load()
        
        # 收集匹配结果
        matched_contents = []
        matched_uids = []
        
        # 1. 首先处理常驻词条 (constant: true)
        for entry in constant_entries:
            matched_contents.append(f"<!-- {entry.comment or entry.uid} -->\n{entry.content}")
            matched_uids.append(entry.uid)
            logger.debug(f"📌 常驻词条注入: [{entry.uid}]")
        
        # 2. 然后处理触发词条 (constant: false)
        for entry in trigger_entries:
            if self._match_entry(entry, user_text):
                matched_contents.append(f"<!-- {entry.comment or entry.uid} -->\n{entry.content}")
                matched_uids.append(entry.uid)
                logger.info(f"✅ 触发词条命中: [{entry.uid}] {entry.comment or '无标题'}")
        
        # 合并内容
        if matched_contents:
            final_content = "\n\n".join(matched_contents)
            return final_content, matched_uids
        
        return "", []
    
    def _match_entry(self, entry: WorldBookEntry, user_text: str) -> bool:
        """
        检查词条是否匹配用户输入
        
        规则:
        - 遍历 entry.keys 中的每个关键词
        - 使用正则表达式，忽略大小写匹配
        - 任一关键词命中即返回 True
        """
        for key in entry.keys:
            if not key:
                continue
            
            try:
                # 将关键词作为正则表达式，忽略大小写
                if re.search(key, user_text, re.IGNORECASE | re.UNICODE):
                    logger.debug(f"🎯 关键词命中: '{key}' -> entry [{entry.uid}]")
                    return True
            except re.error as e:
                logger.warning(f"⚠️ 关键词正则错误 [{entry.uid}]: {key} - {str(e)}")
                continue
        
        return False


# ============ Output Regex 系统 ============

class OutputRegexManager:
    """
    输出正则替换管理器
    
    支持:
    - 剔除 CoT 思维链 (think 标签)
    - Markdown 格式适配
    - 其他文本后处理
    """
    
    DEFAULT_RULES = [
        RegexRule(
            name="remove_think_tags",
            pattern=r"<think>.*?</think>",
            replacement="",
            enabled=True
        ),
        RegexRule(
            name="normalize_asterisk_action",
            pattern=r"\*(.+?)\*",
            replacement=r"(\1)",
            enabled=False  # 默认关闭，需要时手动开启
        ),
        RegexRule(
            name="remove_multiple_newlines",
            pattern=r"\n{3,}",
            replacement="\n\n",
            enabled=True
        ),
        RegexRule(
            name="strip_leading_trailing_whitespace",
            pattern=r"^\s+|\s+$",
            replacement="",
            enabled=True
        ),
    ]
    
    def __init__(self):
        self.rules = self.DEFAULT_RULES.copy()
    
    def apply(self, text: str) -> str:
        """
        应用所有启用的正则规则
        
        Args:
            text: 原始文本
            
        Returns:
            处理后的文本
        """
        if not text:
            return text
        
        original_length = len(text)
        
        for rule in self.rules:
            if rule.enabled:
                text = rule.apply(text)
        
        final_length = len(text)
        if original_length != final_length:
            logger.debug(f"🔄 Output Regex: {original_length} -> {final_length} chars")
        
        return text.strip()
    
    def add_rule(self, rule: RegexRule):
        """添加自定义规则"""
        self.rules.append(rule)
    
    def enable_rule(self, name: str):
        """启用指定规则"""
        for rule in self.rules:
            if rule.name == name:
                rule.enabled = True
                logger.info(f"✅ 启用正则规则: {name}")
                return True
        return False
    
    def disable_rule(self, name: str):
        """禁用指定规则"""
        for rule in self.rules:
            if rule.name == name:
                rule.enabled = False
                logger.info(f"⏸️ 禁用正则规则: {name}")
                return True
        return False


# 全局实例
_output_regex_manager = OutputRegexManager()


def apply_output_regex(reply_text: str) -> str:
    """
    应用输出正则替换
    
    主要用途:
    - 剔除 DeepSeek-R1 等模型的 <think>...</think> 思维链
    - 格式化 Markdown 适配论坛
    - 清理多余空白
    
    Args:
        reply_text: AI 生成的原始回复
        
    Returns:
        处理后的回复文本
        
    Example:
        >>> text = "<think>我需要安慰用户</think>你好，别担心"
        >>> apply_output_regex(text)
        '你好，别担心'
    """
    return _output_regex_manager.apply(reply_text)


# ============ Preset 拼接系统 ============

class PromptBuilder:
    """
    极简 Preset 构建器
    
    严格拼接顺序:
    1. [系统人设 SYSTEM_PROMPT]
    2. [注入的世界书内容] (常驻 + 触发)
    3. [最高指令]
    4. [用户输入]
    """
    
    # 最高指令模板
    SUPREME_COMMAND = (
        "\n\n[最高指令]\n"
        "请严格遵守上述设定，禁止 OOC（角色扮演）。\n"
        "回复应当自然、温暖、符合人设，避免机械感。"
    )
    
    def __init__(self):
        self.system_prompt = config.SYSTEM_PROMPT
        self.worldbook_matcher = WorldBookMatcher()
    
    def build(self, user_text: str) -> Tuple[str, str, List[str]]:
        """
        构建完整 Prompt
        
        Args:
            user_text: 用户输入
            
        Returns:
            (system_prompt, user_prompt, matched_uids): 
            - system_prompt: 完整的系统提示词（含世界书）
            - user_prompt: 处理后的用户输入
            - matched_uids: 命中的世界书条目ID
            
        最终给 LLM 的格式:
        {
            "role": "system",
            "content": system_prompt
        },
        {
            "role": "user", 
            "content": user_prompt
        }
        """
        # 1. 匹配世界书
        worldbook_content, matched_uids = self.worldbook_matcher.match(user_text)
        
        # 2. 构建系统提示词
        parts = [self.system_prompt]
        
        if worldbook_content:
            parts.append("\n\n[世界书设定]")
            parts.append(worldbook_content)
        
        parts.append(self.SUPREME_COMMAND)
        
        final_system_prompt = "\n".join(parts)
        
        # 3. 用户提示词直接使用输入（可在这里添加额外包装）
        final_user_prompt = user_text
        
        logger.debug(f"📐 Prompt 构建完成: {len(final_system_prompt)} chars")
        
        return final_system_prompt, final_user_prompt, matched_uids


# ============ LLM 调用引擎 ============

class LLMEngine:
    """
    大模型调用引擎
    """
    
    def __init__(self):
        self.client: Optional[AsyncOpenAI] = None
        self.prompt_builder = PromptBuilder()
        self._initialized = False
        
        logger.info("🧠 LLMEngine 初始化")
    
    async def _init_client(self):
        """初始化异步客户端"""
        if self._initialized:
            return
        
        if not config.LLM_API_KEY or config.LLM_API_KEY == "your-api-key-here":
            raise ValueError("LLM_API_KEY 未配置")
        
        self.client = AsyncOpenAI(
            api_key=config.LLM_API_KEY,
            base_url=config.LLM_BASE_URL
        )
        self._initialized = True
        logger.info(f"✅ LLM 客户端就绪: {config.LLM_BASE_URL}")
    
    async def generate(
        self,
        user_text: str,
        temperature: float = 0.7,
        max_tokens: int = 500
    ) -> Dict[str, Any]:
        """
        调用大模型生成回复（完整流程）
        
        流程:
        1. 构建 Prompt（Preset 拼接）
        2. 调用 LLM API
        3. 应用 Output Regex
        4. 返回结果
        
        Args:
            user_text: 用户输入
            temperature: 创造性参数
            max_tokens: 最大生成字数
            
        Returns:
            Dict: {
                "reply": 处理后的回复文本,
                "raw_reply": 原始回复文本,
                "matched_worldbook_uids": 命中的世界书条目ID列表,
                "model": 使用的模型
            }
        """
        await self._init_client()
        
        # 1. 构建 Prompt
        system_prompt, user_prompt, matched_uids = self.prompt_builder.build(user_text)
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        logger.info(f"🤖 调用 LLM: model={config.LLM_MODEL}, matched_worldbooks={matched_uids}")
        
        try:
            # 2. 调用 LLM
            response = await self.client.chat.completions.create(
                model=config.LLM_MODEL,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=False
            )
            
            raw_reply = response.choices[0].message.content
            
            # 3. 应用 Output Regex（剔除 think 标签等）
            processed_reply = apply_output_regex(raw_reply)
            
            logger.info(f"✅ LLM 生成成功: {len(processed_reply)} chars")
            
            return {
                "reply": processed_reply,
                "raw_reply": raw_reply,
                "matched_worldbook_uids": matched_uids,
                "model": config.LLM_MODEL
            }
            
        except Exception as e:
            logger.exception(f"❌ LLM 调用失败: {str(e)}")
            raise


# 全局引擎实例
_llm_engine: Optional[LLMEngine] = None


async def generate_reply(user_text: str) -> str:
    """
    【生成回复】主入口函数
    
    Args:
        user_text: 用户原始输入文本
        
    Returns:
        str: AI 生成的回复（已应用 Output Regex）
        
    Example:
        >>> reply = await generate_reply("我失恋了")
        >>> print(reply)
        "抱抱你，分手确实很难受..."
    """
    global _llm_engine
    
    if _llm_engine is None:
        _llm_engine = LLMEngine()
    
    try:
        result = await _llm_engine.generate(user_text)
        return result["reply"]
        
    except Exception as e:
        logger.exception(f"❌ 生成回复失败: {str(e)}")
        # 返回兜底回复
        return "抱歉，我现在有点懵，能再说一遍吗？🐱"


# ============ 便捷函数 ============

def get_worldbook_entries() -> Dict[str, WorldBookEntry]:
    """
    获取所有世界书条目（用于 admin_ui）
    
    Returns:
        Dict: {uid: WorldBookEntry}
    """
    loader = WorldBookLoader()
    loader.load()  # 确保已加载
    return loader._entries.copy()


def reload_worldbook():
    """强制重载世界书"""
    loader = WorldBookLoader()
    return loader.reload()


def test_worldbook_matching(test_text: str) -> Dict[str, Any]:
    """
    测试世界书匹配（用于调试）
    
    Args:
        test_text: 测试文本
        
    Returns:
        Dict: 匹配结果详情
    """
    matcher = WorldBookMatcher()
    content, uids = matcher.match(test_text)
    
    return {
        "input": test_text,
        "matched_uids": uids,
        "matched_content_preview": content[:500] if content else None,
        "constant_count": len([e for e in WorldBookLoader()._constant_entries]),
        "trigger_count": len([e for e in WorldBookLoader()._trigger_entries])
    }


# 如果直接运行此文件，执行测试
if __name__ == "__main__":
    import asyncio
    
    # 测试世界书匹配
    test_cases = [
        "我挂科了，怎么办啊",
        "和男朋友分手了，好难过",
        "最近压力很大，失眠严重",
        "室友每天晚上打游戏很吵",
        "找不到实习，好迷茫"
    ]
    
    print("=" * 50)
    print("世界书匹配测试")
    print("=" * 50)
    
    for text in test_cases:
        result = test_worldbook_matching(text)
        print(f"\n📝 输入: {text}")
        print(f"✅ 命中词条: {result['matched_uids']}")
        if result['matched_content_preview']:
            print(f"📄 内容预览: {result['matched_content_preview'][:200]}...")
        else:
            print("❌ 无匹配")
    
    print("\n" + "=" * 50)
    
    # 测试 Output Regex
    print("\n🔄 Output Regex 测试")
    print("=" * 50)
    
    test_replies = [
        "<think>我要安慰用户</think>你好，别担心",
        "这是正常回复",
        "<think>\n多行思考\n内容\n</think>最终回答",
    ]
    
    for reply in test_replies:
        processed = apply_output_regex(reply)
        print(f"\n原始: {repr(reply)}")
        print(f"处理后: {repr(processed)}")