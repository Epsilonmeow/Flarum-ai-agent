"""
Flarum API 客户端
用于与 Flarum 论坛进行交互，包括发帖、获取讨论等操作
"""

import logging
from typing import Optional, Dict, Any
import httpx

import config

logger = logging.getLogger(__name__)


class FlarumClient:
    """
    Flarum API 异步客户端
    
    封装了 Flarum REST API 的常用操作，支持：
    - 发布帖子回复
    - 获取讨论信息
    - 错误重试和日志记录
    """
    
    def __init__(self):
        self.base_url = config.FLARUM_BASE_URL.rstrip('/')
        self.api_token = config.FLARUM_API_TOKEN
        self.headers = {
            "Authorization": f"Token {self.api_token}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        self.client: Optional[httpx.AsyncClient] = None
        logger.info(f"🔌 FlarumClient 初始化: {self.base_url}")
    
    async def __aenter__(self):
        """异步上下文管理器入口"""
        self.client = httpx.AsyncClient(
            headers=self.headers,
            timeout=30.0,
            follow_redirects=True
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器退出"""
        if self.client:
            await self.client.aclose()
    
    async def _request(
        self,
        method: str,
        endpoint: str,
        json_data: Optional[Dict] = None,
        params: Optional[Dict] = None
    ) -> Optional[Dict[str, Any]]:
        """
        发送 HTTP 请求的通用方法
        
        Args:
            method: HTTP 方法 (GET, POST, etc.)
            endpoint: API 端点路径（不含 base_url）
            json_data: JSON 请求体
            params: URL 查询参数
            
        Returns:
            Dict: 响应JSON数据，失败返回 None
        """
        if not self.client:
            raise RuntimeError("Client 未初始化，请使用 async with 或手动调用 _init_client")
        
        url = f"{self.base_url}{endpoint}"
        
        try:
            response = await self.client.request(
                method=method,
                url=url,
                json=json_data,
                params=params
            )
            response.raise_for_status()
            return response.json()
            
        except httpx.HTTPStatusError as e:
            logger.error(f"❌ HTTP 错误 {e.response.status_code}: {e.response.text}")
            return None
            
        except httpx.RequestError as e:
            logger.error(f"❌ 请求失败: {str(e)}")
            return None
            
        except Exception as e:
            logger.exception(f"❌ 未知错误: {str(e)}")
            return None


async def post_reply(discussion_id: str, content: str) -> bool:
    """
    发布帖子回复到指定讨论串
    
    使用 Flarum API: POST /api/posts
    
    Args:
        discussion_id: 讨论串 ID
        content: 回复内容（支持 Flarum 富文本格式）
        
    Returns:
        bool: 发布成功返回 True，失败返回 False
        
    Example:
        >>> success = await post_reply("123", "你好，这是回复内容")
        >>> print(f"发布成功: {success}")
    """
    # 参数校验
    if not discussion_id:
        logger.error("❌ discussion_id 不能为空")
        return False
    
    if not content or not content.strip():
        logger.error("❌ 回复内容不能为空")
        return False
    
    # 检查配置
    if not config.FLARUM_API_TOKEN or config.FLARUM_API_TOKEN == "your-flarum-token-here":
        logger.error("❌ FLARUM_API_TOKEN 未配置，请在 .env 中设置")
        return False
    
    if not config.FLARUM_BASE_URL or config.FLARUM_BASE_URL == "https://your-forum.com":
        logger.error("❌ FLARUM_BASE_URL 未配置，请在 .env 中设置")
        return False
    
    # 构建请求体
    payload = {
        "data": {
            "type": "posts",
            "attributes": {
                "content": content
            },
            "relationships": {
                "discussion": {
                    "data": {
                        "type": "discussions",
                        "id": str(discussion_id)
                    }
                }
            }
        }
    }
    
    logger.info(f"📤 正在发布回复到讨论串 {discussion_id}...")
    logger.debug(f"请求内容: {content[:100]}...")
    
    try:
        async with FlarumClient() as client:
            result = await client._request("POST", "/api/posts", json_data=payload)
            
            if result:
                post_id = result.get("data", {}).get("id", "unknown")
                logger.info(f"✅ 回复发布成功，帖子ID: {post_id}")
                return True
            else:
                logger.error("❌ 回复发布失败: API 返回空结果")
                return False
                
    except Exception as e:
        logger.exception(f"❌ 发布回复时发生异常: {str(e)}")
        return False


async def get_discussion(discussion_id: str) -> Optional[Dict[str, Any]]:
    """
    获取讨论串详情
    
    使用 Flarum API: GET /api/discussions/{id}
    
    Args:
        discussion_id: 讨论串 ID
        
    Returns:
        Dict: 讨论串详情，失败返回 None
    """
    if not discussion_id:
        logger.error("❌ discussion_id 不能为空")
        return None
    
    try:
        async with FlarumClient() as client:
            result = await client._request(
                "GET", 
                f"/api/discussions/{discussion_id}"
            )
            
            if result:
                logger.info(f"✅ 获取讨论串 {discussion_id} 成功")
                return result
            else:
                logger.error(f"❌ 获取讨论串 {discussion_id} 失败")
                return None
                
    except Exception as e:
        logger.exception(f"❌ 获取讨论串时发生异常: {str(e)}")
        return None


async def get_current_user() -> Optional[Dict[str, Any]]:
    """
    获取当前登录用户信息（用于验证 Token 是否有效）
    
    使用 Flarum API: GET /api/users/1 (当前用户)
    
    Returns:
        Dict: 用户信息，失败返回 None
    """
    try:
        async with FlarumClient() as client:
            # 尝试获取当前用户信息
            result = await client._request("GET", "/api/users/1")
            
            if result:
                username = result.get("data", {}).get("attributes", {}).get("username", "unknown")
                logger.info(f"✅ API Token 验证成功，当前用户: {username}")
                return result
            else:
                logger.error("❌ API Token 验证失败")
                return None
                
    except Exception as e:
        logger.exception(f"❌ 验证 Token 时发生异常: {str(e)}")
        return None


# 便捷函数：同步包装（用于非异步环境）
def post_reply_sync(discussion_id: str, content: str) -> bool:
    """
    同步版本的 post_reply（用于同步代码中调用）
    
    Args:
        discussion_id: 讨论串 ID
        content: 回复内容
        
    Returns:
        bool: 发布成功返回 True
    """
    import asyncio
    return asyncio.run(post_reply(discussion_id, content))