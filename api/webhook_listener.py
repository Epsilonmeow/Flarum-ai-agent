"""
Flarum Webhook 监听器 - 完整业务流实现
接收论坛事件并通过 BackgroundTasks 异步处理，避免 Webhook 超时
支持 Flarum 伪装成 Slack 格式的 JSON payload
"""

import re
import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Request, HTTPException
from pydantic import BaseModel

import config
from core.memory_manager import evaluate_memory_value
from core.cooldown_manager import check_reply_cooldown, update_cooldown
from core.llm_engine_v2 import generate_reply_v2
from utils.flarum_client import post_reply

logger = logging.getLogger(__name__)

# 创建路由
router = APIRouter()

# ============ 配置项 ============

# 机器人标识（用于致命拦截，防止自循环）
# 从 config 读取，支持 .env 配置
BOT_USERNAMES = config.BOT_USERNAMES
BOT_USER_IDS = config.BOT_USER_IDS


# ============ 数据模型 ============

class SlackWebhookPayload(BaseModel):
    """
    Flarum 伪装成 Slack 格式的 Webhook Payload
    
    实际格式示例：
    {
        "text": "New post by 用户名: 帖子内容... https://your-forum.com/d/123",
        "username": "Flarum",
        "icon_url": "..."
    }
    """
    text: str
    username: Optional[str] = "Flarum"
    icon_url: Optional[str] = None
    channel: Optional[str] = None


class WebhookResponse(BaseModel):
    """标准 Webhook 响应"""
    status: str
    message: Optional[str] = None


# ============ 辅助函数：提取 discussion_id ============

def extract_discussion_id(payload: Dict[str, Any], payload_str: str) -> Optional[str]:
    """
    从 payload 中提取 discussion_id
    
    支持多种格式：
    1. 直接从 text 字段提取（兼容转义和非转义斜杠）
    2. 从 attachments 中的 title_link 或 fallback 提取
    3. 失败时打印完整 payload 供调试
    
    Args:
        payload: 解析后的 JSON 字典
        payload_str: 原始 JSON 字符串（用于调试）
        
    Returns:
        str: 提取到的 discussion_id，失败返回 None
    """
    discussion_id = None
    text_content = payload.get("text", "")
    
    # 方法 1: 直接从 text 字段提取（兼容 \/d\/ 和 /d/）
    # 正则解释: [/\\] 匹配 / 或 \/
    match = re.search(r'[/\\]d[/\\](\d+)', text_content)
    if match:
        discussion_id = match.group(1)
        logger.info(f"✅ 从 text 提取到 discussion_id: {discussion_id}")
        return discussion_id
    
    # 方法 2: 从 attachments 中提取
    attachments = payload.get("attachments", [])
    if attachments and isinstance(attachments, list):
        logger.info(f"🔍 尝试从 attachments 提取，共 {len(attachments)} 个")
        
        for idx, attachment in enumerate(attachments):
            if not isinstance(attachment, dict):
                continue
                
            # 尝试 title_link
            title_link = attachment.get("title_link", "")
            if title_link:
                match = re.search(r'[/\\]d[/\\](\d+)', title_link)
                if match:
                    discussion_id = match.group(1)
                    logger.info(f"✅ 从 attachments[{idx}].title_link 提取到 discussion_id: {discussion_id}")
                    return discussion_id
            
            # 尝试 fallback
            fallback = attachment.get("fallback", "")
            if fallback:
                match = re.search(r'[/\\]d[/\\](\d+)', fallback)
                if match:
                    discussion_id = match.group(1)
                    logger.info(f"✅ 从 attachments[{idx}].fallback 提取到 discussion_id: {discussion_id}")
                    return discussion_id
            
            # 尝试 text
            attach_text = attachment.get("text", "")
            if attach_text:
                match = re.search(r'[/\\]d[/\\](\d+)', attach_text)
                if match:
                    discussion_id = match.group(1)
                    logger.info(f"✅ 从 attachments[{idx}].text 提取到 discussion_id: {discussion_id}")
                    return discussion_id
    
    # 方法 3: 尝试从整个 payload_str 原始字符串提取（处理极端情况）
    match = re.search(r'[/\\]d[/\\](\d+)', payload_str)
    if match:
        discussion_id = match.group(1)
        logger.info(f"✅ 从原始 payload_str 提取到 discussion_id: {discussion_id}")
        return discussion_id
    
    # 所有方法都失败，打印完整 payload 供调试
    logger.error(f"❌ 提取 discussion_id 失败，完整 payload: {payload_str}")
    return None


# ============ 核心业务函数 ============

async def process_and_reply(discussion_id: str, user_text: str, user_id: str):
    """
    后台任务：处理用户帖子并回复
    
    完整流程：
    1. 冷却检查
    2. 记忆价值评估
    3. 调用 LLM 生成回复（已包含世界书匹配）
    4. 发布回复到论坛
    5. 存储记忆
    
    Args:
        discussion_id: 讨论串 ID
        user_text: 用户帖子纯文本
        user_id: 用户 ID（用于冷却和记忆）
    """
    try:
        logger.info(f"🔄 开始处理讨论串 {discussion_id}")
        
        # ===== 步骤 1: 回复冷却检查 =====
        if not check_reply_cooldown(user_id):
            logger.info(f"⏱️ 用户 {user_id} 处于冷却期，跳过回复")
            return
        
        # ===== 步骤 2: 记忆价值评估 =====
        memory_value = evaluate_memory_value(user_text)
        if memory_value < config.MEMORY_VALUE_THRESHOLD:
            logger.info(f"🗑️ 帖子价值评分 {memory_value:.2f} 低于阈值，不存入记忆")
            should_save_memory = False
        else:
            logger.info(f"💎 帖子价值评分 {memory_value:.2f}，符合存储标准")
            should_save_memory = True
        
        # ===== 步骤 3: 调用 LLM 生成回复 =====
        # LLMEngineV2 内部包含 Provider 故障转移、三层记忆、好感度与世界书匹配
        logger.info(f"🧠 正在生成回复...")
        reply_content = await generate_reply_v2(
            user_id=user_id,
            user_message=user_text,
            save_memory=should_save_memory
        )
        
        if not reply_content:
            logger.error("❌ LLM 未生成有效回复")
            return
        
        logger.info(f"🤖 AI 回复: {reply_content[:100]}...")
        
        # ===== 步骤 4: 发布回复到论坛 =====
        post_success = await post_reply(discussion_id, reply_content)
        
        if post_success:
            logger.info(f"✅ 回复已成功发布到讨论串 {discussion_id}")
            # 更新冷却时间
            update_cooldown(user_id, user_text)
        else:
            logger.error(f"❌ 发布回复到讨论串 {discussion_id} 失败")
            return
        
        # ===== 步骤 5: 记忆状态记录 =====
        # V2 引擎已根据 save_memory 参数完成三层记忆写入，这里只记录决策结果
        if should_save_memory:
            logger.info(f"💾 已允许 V2 记忆系统存储本次交互: user={user_id}")
        else:
            logger.info(f"�️ 本次交互未写入 V2 记忆系统: user={user_id}")
        
        logger.info(f"✅ 处理完成: discussion_id={discussion_id}")
        
    except Exception as e:
        logger.exception(f"❌ process_and_reply 发生错误: {str(e)}")


# ============ Webhook 接收端点 ============

@router.post("/webhook")
async def receive_webhook(
    request: Request,
    background_tasks: BackgroundTasks
):
    """
    接收 Flarum Webhook（Slack 格式）
    
    【致命拦截】：检查发帖人是否是机器人自己，防止自循环
    【异步防超时】：提取成功后，将处理任务加入 BackgroundTasks
    
    Returns:
        {"status": "processing"} - 立即返回，Flarum 不再重试
        {"status": "ignored"} - 忽略此请求
        {"status": "error"} - 处理失败
    """
    try:
        # 读取原始 payload
        body = await request.body()
        payload_str = body.decode('utf-8')
        
        logger.info(f"📨 收到 Webhook: {payload_str[:500]}...")
        
        # 解析 JSON
        try:
            payload = json.loads(payload_str)
        except json.JSONDecodeError as e:
            logger.error(f"❌ JSON 解析失败: {str(e)}")
            return {"status": "error", "message": "Invalid JSON"}
        
        # ============ 【致命拦截】检查是否是机器人自己发的 ============
        
        # 从 text 字段提取发帖人信息
        # 格式通常为: "New post by 用户名: ..."
        text_content = payload.get("text", "")
        
        # 检查用户名（多种可能的格式）
        # 格式 1: "New post by 树洞喵: ..."
        # 格式 2: "{\"username\": \"树洞喵\", ..."
        
        poster_name = None
        poster_id = None
        
        # 尝试从 text 提取发帖人
        name_match = re.search(r'(?:New (?:post|discussion) by|来自)\s*([^:]+):', text_content, re.IGNORECASE)
        if name_match:
            poster_name = name_match.group(1).strip()
        
        # 尝试从额外的 JSON 字段提取（如果 Flarum 扩展提供了）
        if not poster_name and "username" in payload:
            poster_name = payload.get("username")
        
        # 致命拦截：如果发帖人是机器人自己
        if poster_name and any(bot_name in poster_name for bot_name in BOT_USERNAMES):
            logger.warning(f"🚫 【致命拦截】检测到机器人自己发帖: {poster_name}，忽略此请求防止自循环")
            return {"status": "ignored", "reason": "Self-loop prevented"}
        
        # 尝试提取 user_id（如果 payload 中有）
        if "user_id" in payload:
            poster_id = str(payload.get("user_id"))
            if poster_id in BOT_USER_IDS:
                logger.warning(f"🚫 【致命拦截】检测到机器人 user_id: {poster_id}，忽略此请求")
                return {"status": "ignored", "reason": "Self-loop prevented by user_id"}
        
        # ============ 提取 discussion_id ============
        
        discussion_id = extract_discussion_id(payload, payload_str)
        
        if not discussion_id:
            return {"status": "error", "message": "Cannot extract discussion_id"}
        
        # ============ 提取用户纯文本内容 ============
        
        # 去掉 URL 后的内容
        # 格式: "New post by 用户名: 内容 https://..."
        user_text = text_content
        
        # 去掉前缀（如果有）
        if name_match:
            # 去掉 "New post by 用户名: "
            user_text = re.sub(r'^[^:]+:\s*', '', user_text)
        
        # 去掉 URL（兼容转义的 URL）
        user_text = re.sub(r'https?://\\S+|https?://\S+', '', user_text).strip()
        
        # 清理 HTML 标签（如果有）
        user_text = re.sub(r'<[^>]+>', '', user_text)
        
        # 清理转义的斜杠（JSON 转义）
        user_text = user_text.replace('\\/', '/')
        
        if not user_text:
            logger.warning("⚠️ 提取到空的用户文本，尝试使用原始 text")
            user_text = text_content  # 回退到原始内容
        
        logger.info(f"📝 用户文本: {user_text[:100]}...")
        
        # 使用 discussion_id 作为 user_id 的占位符（实际应该从 payload 提取）
        # Flarum 的 Slack webhook 可能没有直接的 user_id，我们可以用发帖人名称的哈希
        extracted_user_id = poster_name or f"user_{discussion_id}"
        
        # ============ 【异步防超时】加入后台任务 ============
        
        background_tasks.add_task(
            process_and_reply,
            discussion_id=discussion_id,
            user_text=user_text,
            user_id=extracted_user_id
        )
        
        logger.info(f"✅ 已将讨论串 {discussion_id} 的处理加入后台任务")
        
        # 立即返回，让 Flarum 知道我们收到了
        return {
            "status": "processing",
            "discussion_id": discussion_id,
            "message": "Request received, processing in background"
        }
        
    except Exception as e:
        logger.exception(f"❌ Webhook 处理异常: {str(e)}")
        # 即使出错也返回 200，防止 Flarum 重试
        return {"status": "error", "message": str(e)}


@router.post("/webhook/raw")
async def receive_webhook_raw(
    request: Request,
    background_tasks: BackgroundTasks
):
    """
    备用端点：接收原始 Flarum JSON 格式（非 Slack 格式）
    如果 Flarum 扩展支持发送原始事件数据
    """
    try:
        data = await request.json()
        
        logger.info(f"📨 收到原始 Webhook: {data}")
        
        # 提取数据
        user_id = str(data.get("user_id", ""))
        discussion_id = str(data.get("discussion_id", ""))
        content = data.get("content", "")
        username = data.get("username", "")
        
        # 【致命拦截】
        if username and any(bot in username for bot in BOT_USERNAMES):
            return {"status": "ignored", "reason": "Self-loop prevented"}
        
        if not discussion_id or not content:
            return {"status": "error", "message": "Missing required fields"}
        
        # 加入后台任务
        background_tasks.add_task(
            process_and_reply,
            discussion_id=discussion_id,
            user_text=content,
            user_id=user_id or username
        )
        
        return {"status": "processing"}
        
    except Exception as e:
        logger.exception(f"❌ 原始 Webhook 处理异常: {str(e)}")
        return {"status": "error", "message": str(e)}


# ============ 调试端点 ============

@router.post("/webhook/test")
async def test_webhook(
    discussion_id: str,
    user_text: str,
    background_tasks: BackgroundTasks
):
    """
    测试端点：手动触发回复流程
    
    用于开发和调试，不经过致命拦截检查
    """
    logger.info(f"🧪 测试 Webhook: discussion_id={discussion_id}, text={user_text[:50]}...")
    
    background_tasks.add_task(
        process_and_reply,
        discussion_id=discussion_id,
        user_text=user_text,
        user_id="test_user"
    )
    
    return {
        "status": "processing",
        "message": "Test request received, processing in background"
    }


# ============ 调试端点：测试 ID 提取 ============

@router.post("/webhook/test-extract")
async def test_extract_id(request: Request):
    """
    测试端点：测试 discussion_id 提取逻辑
    
    用于调试 Flarum 发送的实际 payload 格式
    """
    try:
        body = await request.body()
        payload_str = body.decode('utf-8')
        
        logger.info(f"🧪 测试提取，payload: {payload_str[:500]}...")
        
        try:
            payload = json.loads(payload_str)
        except json.JSONDecodeError as e:
            return {
                "status": "error",
                "message": f"JSON parse error: {str(e)}",
                "raw": payload_str[:1000]
            }
        
        # 尝试提取
        discussion_id = extract_discussion_id(payload, payload_str)
        
        return {
            "status": "success" if discussion_id else "failed",
            "extracted_id": discussion_id,
            "payload_preview": {
                "text": payload.get("text", "")[:200],
                "attachments_count": len(payload.get("attachments", [])),
                "attachment_fields": [
                    {
                        "title_link": a.get("title_link", "")[:100] if isinstance(a, dict) else None,
                        "fallback": a.get("fallback", "")[:100] if isinstance(a, dict) else None
                    }
                    for a in payload.get("attachments", [])
                ]
            }
        }
        
    except Exception as e:
        logger.exception(f"❌ 测试提取失败: {str(e)}")
        return {"status": "error", "message": str(e)}