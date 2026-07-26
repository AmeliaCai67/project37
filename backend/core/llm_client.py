import httpx
from typing import AsyncGenerator, List, Dict, Optional
import json

from config import settings
from core.logging import get_logger

logger = get_logger(__name__)


class LLMClient:
    """LLM API 客户端 - 支持 DeepSeek / MiniMax / OpenAI"""
    
    def __init__(self):
        self.provider = settings.LLM_PROVIDER
        self.api_key = settings.LLM_API_KEY
        self.base_url = self._get_base_url()
        self.model = settings.LLM_MODEL
        self.max_tokens = settings.LLM_MAX_TOKENS
        self.temperature = settings.LLM_TEMPERATURE
        
    def _get_base_url(self) -> str:
        if settings.LLM_BASE_URL:
            return settings.LLM_BASE_URL
        
        urls = {
            "deepseek": "https://api.deepseek.com/v1",
            "minimax": "https://api.minimax.chat/v1",
            "openai": "https://api.openai.com/v1",
        }
        return urls.get(self.provider, urls["deepseek"])
    
    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        stream: bool = False,
        tools: Optional[List[dict]] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> Dict:
        """
        非流式对话
        
        Args:
            messages: [{"role": "user", "content": "..."}, ...]
            stream: 是否流式返回
            tools: 工具调用定义
            temperature: 可选，覆盖实例默认温度
            max_tokens: 可选，覆盖实例默认最大 token 数
        """
        url = f"{self.base_url}/chat/completions"
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        
        # MiniMax 使用不同的认证头
        if self.provider == "minimax":
            headers["Authorization"] = f"Bearer {self.api_key}"
        
        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens if max_tokens is not None else self.max_tokens,
            "temperature": temperature if temperature is not None else self.temperature,
            "stream": stream,
        }
        
        if tools:
            payload["tools"] = tools
        
        async with httpx.AsyncClient(timeout=120.0) as client:
            try:
                response = await client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPError as e:
                error_detail = str(e)
                if hasattr(e, 'response') and e.response is not None:
                    try:
                        error_detail += f" | Response: {e.response.text}"
                    except Exception:
                        pass
                logger.error(f"LLM API error: {error_detail}")
                raise
    
    async def chat_completion_stream(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> AsyncGenerator[str, None]:
        """流式对话，返回 SSE 格式的字符串

        Args:
            messages: [{"role": "user", "content": "..."}, ...]
            temperature: 可选，覆盖实例默认温度
            max_tokens: 可选，覆盖实例默认最大 token 数
        """
        url = f"{self.base_url}/chat/completions"
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        
        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens if max_tokens is not None else self.max_tokens,
            "temperature": temperature if temperature is not None else self.temperature,
            "stream": True,
        }
        
        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream("POST", url, headers=headers, json=payload) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data = line[6:]
                        if data == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data)
                            delta = chunk["choices"][0].get("delta", {})
                            if "content" in delta:
                                yield delta["content"]
                        except (json.JSONDecodeError, KeyError):
                            continue
    
    def reload(self):
        """从当前 settings 与环境变量重新加载配置。"""
        import os

        self.provider = os.environ.get("LLM_PROVIDER", settings.LLM_PROVIDER)
        self.api_key = os.environ.get("LLM_API_KEY", settings.LLM_API_KEY)
        self.base_url = os.environ.get("LLM_BASE_URL") or self._get_base_url()
        self.model = os.environ.get("LLM_MODEL", settings.LLM_MODEL)
        self.max_tokens = int(os.environ.get("LLM_MAX_TOKENS", settings.LLM_MAX_TOKENS))
        self.temperature = float(os.environ.get("LLM_TEMPERATURE", settings.LLM_TEMPERATURE))

    def build_messages(
        self,
        user_message: str,
        system_prompt: Optional[str] = None,
        history: Optional[List[Dict[str, str]]] = None,
        context: Optional[str] = None,
    ) -> List[Dict[str, str]]:
        """构建消息列表"""
        messages = []
        
        # 系统提示
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        # 上下文（RAG 检索结果等）
        if context:
            messages.append({
                "role": "system", 
                "content": f"基于以下参考信息回答用户问题：\n\n{context}"
            })
        
        # 历史对话
        if history:
            messages.extend(history)
        
        # 用户当前消息
        messages.append({"role": "user", "content": user_message})
        
        return messages


# 全局客户端实例
llm_client = LLMClient()
