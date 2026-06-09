"""
Flarum AI Agent 全局配置文件
包含所有大写常量配置项，支持从 .env 文件加载
"""

import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv()

# ==========================================
# 大模型 API 配置 (LLM Configuration)
# ==========================================

# OpenAI 格式兼容的 API 密钥
# 支持：OpenAI / 智谱 AI / 通义千问 / 本地 vLLM 等
LLM_API_KEY: str = os.getenv("LLM_API_KEY", "your-api-key-here")

# 大模型 API 基础地址
# 示例: "https://api.openai.com/v1" 或 "http://localhost:8000/v1"
LLM_BASE_URL: str = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")

# 使用的模型名称
LLM_MODEL: str = os.getenv("LLM_MODEL", "gpt-3.5-turbo")

# 系统人设 Prompt (AI 的人格设定)
SYSTEM_PROMPT: str = os.getenv(
    "SYSTEM_PROMPT", 
    "You are a warm and helpful AI assistant for a Flarum community."
)


# ==========================================
# Flarum 论坛配置 (Flarum Configuration)
# ==========================================

# Flarum 论坛基础网址
# 示例: "https://your-forum.com"
FLARUM_BASE_URL: str = os.getenv("FLARUM_BASE_URL", "https://your-forum.com")

# Flarum API Token (用于自动发帖回复)
# 在 Flarum 后台生成: Admin > API Tokens
FLARUM_API_TOKEN: str = os.getenv("FLARUM_API_TOKEN", "your-flarum-token-here")


# ==========================================
# 应用配置 (Application Settings)
# ==========================================

# 项目根目录
BASE_DIR: Path = Path(__file__).parent

# 数据目录路径
DATA_DIR: Path = BASE_DIR / "data"

# 世界书 JSON 文件路径（公开版不内置世界书，请按需自行创建）
WORLD_BOOK_PATH: Path = DATA_DIR / os.getenv("WORLD_BOOK_FILE", "worldbook.json")

# ChromaDB 存储路径
CHROMA_DB_PATH: Path = DATA_DIR / "chroma_db"

# 日志级别
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

# Webhook 监听端口
WEBHOOK_PORT: int = int(os.getenv("WEBHOOK_PORT", "8000"))

# Admin UI 端口
ADMIN_UI_PORT: int = int(os.getenv("ADMIN_UI_PORT", "8501"))


# ==========================================
# 业务逻辑配置 (Business Logic)
# ==========================================

# 同一用户回复冷却时间（秒）- 防止恶意刷 API
REPLY_COOLDOWN_SECONDS: int = int(os.getenv("REPLY_COOLDOWN_SECONDS", "60"))

# 记忆价值阈值（0-1）- 低于此值的记忆不存入 ChromaDB
MEMORY_VALUE_THRESHOLD: float = float(os.getenv("MEMORY_VALUE_THRESHOLD", "0.3"))

# 最大上下文记忆条数
MAX_MEMORY_CONTEXT: int = int(os.getenv("MAX_MEMORY_CONTEXT", "5"))


# ==========================================
# 机器人配置 (Bot Identity)
# ==========================================

# 机器人用户名列表（用于致命拦截，防止自循环）
BOT_USERNAMES: list = os.getenv("BOT_USERNAMES", "AI Assistant,FlarumBot").split(",")

# 机器人 User ID 列表
BOT_USER_IDS: list = os.getenv("BOT_USER_IDS", "1,999").split(",")


# ==========================================
# 三层记忆系统配置 (Layered Memory)
# ==========================================

# 记忆存储目录
MEMORY_STORAGE_DIR: Path = DATA_DIR / "memory"

# 每块最大对话轮数
MEMORY_BLOCK_SIZE: int = int(os.getenv("MEMORY_BLOCK_SIZE", "10"))

# 摘要触发阈值（多少块触发一次总结）
SUMMARY_TRIGGER_THRESHOLD: int = int(os.getenv("SUMMARY_TRIGGER_THRESHOLD", "2"))

# 最大上下文消息数
MAX_CONTEXT_MESSAGES: int = int(os.getenv("MAX_CONTEXT_MESSAGES", "5"))

# 最大摘要数量（防止Prompt过长）
MAX_SUMMARIES_IN_PROMPT: int = int(os.getenv("MAX_SUMMARIES_IN_PROMPT", "3"))


# ==========================================
# 好感度系统配置 (Affection System)
# ==========================================

# 好感度存储目录
AFFECTION_STORAGE_DIR: Path = DATA_DIR / "affection"

# 每日首次互动奖励
DAILY_BONUS_POINTS: int = int(os.getenv("DAILY_BONUS_POINTS", "5"))

# 连续互动奖励
CONSECUTIVE_BONUS_POINTS: int = int(os.getenv("CONSECUTIVE_BONUS_POINTS", "10"))

# 情感支持额外奖励
EMOTIONAL_SUPPORT_BONUS: int = int(os.getenv("EMOTIONAL_SUPPORT_BONUS", "5"))


# ==========================================
# Embedding 配置
# ==========================================

# 默认Embedding模型 (bge/qwen)
DEFAULT_EMBEDDING_MODEL: str = os.getenv("DEFAULT_EMBEDDING_MODEL", "qwen")

# BGE-M3 模型路径（本地模式）
BGE_MODEL_PATH: Optional[str] = os.getenv("BGE_MODEL_PATH")

# Qwen Embedding API Key
DASHSCOPE_API_KEY: Optional[str] = os.getenv("DASHSCOPE_API_KEY")


# ==========================================
# Provider 配置 (多模型故障转移)
# ==========================================

# Provider 配置列表（JSON格式）
# 示例: [{"name": "deepseek", "type": "deepseek", "api_key": "...", "model": "...", "is_primary": true}]
PROVIDER_CONFIGS: list = []

# 加载 provider 配置（如果环境变量中有）
_provider_configs_env = os.getenv("PROVIDER_CONFIGS")
if _provider_configs_env:
    try:
        import json
        PROVIDER_CONFIGS = json.loads(_provider_configs_env)
    except:
        pass

# 默认Provider配置（备用）
DEFAULT_PROVIDER_TYPE: str = os.getenv("DEFAULT_PROVIDER_TYPE", "openai")


# 确保数据目录存在
DATA_DIR.mkdir(parents=True, exist_ok=True)
MEMORY_STORAGE_DIR.mkdir(parents=True, exist_ok=True)
AFFECTION_STORAGE_DIR.mkdir(parents=True, exist_ok=True)
