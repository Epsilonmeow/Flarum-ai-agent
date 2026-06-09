"""
Mock Provider - 用于离线沙盒测试

特点：
- 不访问网络、不消耗 API Key
- 遵循 BaseProvider 接口，可直接接入 ProviderManager
- 返回可预测的回复，方便回归测试
- 支持模拟失败，用于测试故障转移
"""

import hashlib
import time
from typing import Optional, List, Dict, Any

from .base import BaseProvider, GenerationResult, GenerationConfig, FinishReason, ProviderError


class MockProvider(BaseProvider):
    """离线沙盒测试 Provider"""

    provider_type = "mock"
    supported_models = ["mock-sandbox"]
    supports_vision = False
    supports_tools = False
    supports_thinking = False

    def __init__(
        self,
        api_key: str = "mock-api-key",
        base_url: Optional[str] = None,
        model: str = "mock-sandbox",
        should_fail: bool = False,
        latency_ms: float = 5.0,
        **kwargs
    ):
        super().__init__(api_key=api_key, base_url=base_url, **kwargs)
        self.model = model
        self.should_fail = should_fail
        self.latency_ms = latency_ms

    async def is_available(self) -> bool:
        """Mock Provider 始终本地可用，除非显式配置为失败"""
        return not self.should_fail

    async def generate(
        self,
        messages: List[Dict[str, Any]],
        config: Optional[GenerationConfig] = None,
        **kwargs
    ) -> GenerationResult:
        """生成可预测的沙盒回复"""
        if self.should_fail:
            raise ProviderError("MockProvider 被配置为模拟失败")

        start = time.time()
        config = config or GenerationConfig()

        user_content = self._get_last_user_message(messages)
        content = self._build_response(user_content)

        if config.max_output_tokens:
            # 粗略限制输出长度；中文环境下仅作为测试保护，不做真实 token 计算
            content = content[: max(20, config.max_output_tokens * 2)]

        latency_ms = (time.time() - start) * 1000 + self.latency_ms
        input_tokens = sum(len(str(m.get("content", ""))) for m in messages) // 2
        output_tokens = len(content) // 2

        return GenerationResult(
            content=content,
            raw_content=content,
            model_used=self.model,
            tokens_used=input_tokens + output_tokens,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            finish_reason=FinishReason.STOP,
            latency_ms=latency_ms
        )

    async def generate_embedding(self, text: str, **kwargs) -> Optional[List[float]]:
        """生成确定性的伪 embedding，便于离线测试"""
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        return [round((b / 255.0) * 2 - 1, 6) for b in digest[:16]]

    def _get_last_user_message(self, messages: List[Dict[str, Any]]) -> str:
        """获取最后一条 user 消息"""
        for msg in reversed(messages):
            if msg.get("role") == "user":
                return str(msg.get("content", ""))
        return ""

    def _build_response(self, user_content: str) -> str:
        """根据输入构造稳定回复"""
        if "请对以下对话进行总结" in user_content or "【对话内容】" in user_content:
            return (
                "【对话摘要】这是沙盒 MockProvider 生成的离线摘要，用于验证增量总结流程。\n"
                "【用户状态】\n"
                "- 主要情绪: 沙盒测试\n"
                "- 关注话题: 主流程、记忆、好感度\n"
                "- 可能需求: 验证系统是否稳定运行\n"
                "【重要信息】\n"
                "- 本摘要不会调用真实模型，也不会写入正式记忆目录。"
            )

        emotional_keywords = ["压力", "难过", "焦虑", "睡不着", "撑不住", "崩溃", "无助"]
        thanks_keywords = ["谢谢", "感谢", "陪伴"]

        if any(word in user_content for word in emotional_keywords):
            return (
                f"我听见你说：“{user_content[:60]}”。这是沙盒回复：如果你最近压力很大，"
                "可以先试着把最难受的部分拆小一点，也记得及时找可信任的人或专业支持陪你一起面对。"
            )

        if any(word in user_content for word in thanks_keywords):
            return (
                f"收到你的话：“{user_content[:60]}”。这是沙盒回复：不用客气呀，"
                "能陪你说说话本身就是很重要的事情。"
            )

        if "记得" in user_content or "刚才" in user_content:
            return (
                "这是沙盒回复：我会根据沙盒记忆中的近期上下文来回答，"
                "但这些内容只会写入 data/sandbox，不会影响正式记忆。"
            )

        return (
            f"这是沙盒 MockProvider 回复：我收到了“{user_content[:60]}”。"
            "当前测试不会调用真实 LLM，也不会向 Flarum 发帖。"
        )
