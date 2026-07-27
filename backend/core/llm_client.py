import httpx
from typing import AsyncGenerator, List, Dict, Optional
import json

from config import settings
from core.logging import get_logger

logger = get_logger(__name__)


# OpenAI 兼容服务商预设（均可通过 LLM_BASE_URL 覆盖）
PROVIDER_PRESETS = {
    "deepseek": "https://api.deepseek.com/v1",
    "kimi": "https://api.moonshot.cn/v1",
    "qwen": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "zhipu": "https://open.bigmodel.cn/api/paas/v4",
    "minimax": "https://api.minimax.chat/v1",
    "openai": "https://api.openai.com/v1",
}


class LLMClient:
    """LLM API 客户端 - 支持任意 OpenAI 兼容服务商（DeepSeek/Kimi/Qwen/智谱/MiniMax/OpenAI 等）"""
    
    def __init__(self):
        self.provider = settings.LLM_PROVIDER
        self.api_key = settings.LLM_API_KEY
        self.base_url = self._get_base_url()
        self.model = settings.LLM_MODEL
        self.max_tokens = settings.LLM_MAX_TOKENS
        self.temperature = settings.LLM_TEMPERATURE
        # 备选模型（选填）
        self.fallback_provider = settings.LLM_FALLBACK_PROVIDER
        self.fallback_api_key = settings.LLM_FALLBACK_API_KEY
        self.fallback_base_url = settings.LLM_FALLBACK_BASE_URL
        self.fallback_model = settings.LLM_FALLBACK_MODEL
        
    def _get_base_url(self) -> str:
        if settings.LLM_BASE_URL:
            return settings.LLM_BASE_URL
        
        return PROVIDER_PRESETS.get(self.provider, PROVIDER_PRESETS["deepseek"])
    
    def _attempts(self) -> List[tuple]:
        """(base_url, api_key, model) 尝试列表：主配置 + 可选备选。"""
        attempts = [(self.base_url, self.api_key, self.model)]
        if self.fallback_model and self.fallback_api_key:
            base_url = self.fallback_base_url or PROVIDER_PRESETS.get(
                self.fallback_provider, PROVIDER_PRESETS["deepseek"]
            )
            attempts.append((base_url, self.fallback_api_key, self.fallback_model))
        return attempts

    async def _post_chat(
        self,
        base_url: str,
        api_key: str,
        model: str,
        messages: List[Dict[str, str]],
        stream: bool,
        tools: Optional[List[dict]],
        temperature: Optional[float],
        max_tokens: Optional[int],
    ) -> Dict:
        """单次非流式请求。"""
        url = f"{base_url}/chat/completions"

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": model,
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
                logger.error(f"LLM API error (model={model}): {error_detail}")
                raise

    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        stream: bool = False,
        tools: Optional[List[dict]] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> Dict:
        """
        非流式对话；配置了备选模型时，主模型失败自动切换一次。

        Args:
            messages: [{"role": "user", "content": "..."}, ...]
            stream: 是否流式返回
            tools: 工具调用定义
            temperature: 可选，覆盖实例默认温度
            max_tokens: 可选，覆盖实例默认最大 token 数
        """
        attempts = self._attempts()
        last_error: Optional[Exception] = None
        for i, (base_url, api_key, model) in enumerate(attempts):
            try:
                return await self._post_chat(
                    base_url, api_key, model, messages, stream, tools, temperature, max_tokens
                )
            except httpx.HTTPError as e:
                last_error = e
                if i + 1 < len(attempts):
                    logger.warning(f"主模型 {model} 失败，切换到备选模型 {attempts[i + 1][2]}")
        raise last_error
    
    async def _stream_once(
        self,
        base_url: str,
        api_key: str,
        model: str,
        messages: List[Dict[str, str]],
        temperature: Optional[float],
        max_tokens: Optional[int],
    ) -> AsyncGenerator[str, None]:
        """单次流式请求。"""
        url = f"{base_url}/chat/completions"

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": model,
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

    async def chat_completion_stream(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> AsyncGenerator[str, None]:
        """流式对话，返回 SSE 格式的字符串；配置了备选模型时，主模型在产出首个
        chunk 前失败会自动切换一次（已开始输出后失败则直接抛出，避免内容重复）。

        Args:
            messages: [{"role": "user", "content": "..."}, ...]
            temperature: 可选，覆盖实例默认温度
            max_tokens: 可选，覆盖实例默认最大 token 数
        """
        attempts = self._attempts()
        for i, (base_url, api_key, model) in enumerate(attempts):
            yielded = False
            try:
                async for chunk in self._stream_once(
                    base_url, api_key, model, messages, temperature, max_tokens
                ):
                    yielded = True
                    yield chunk
                return
            except httpx.HTTPError as e:
                if yielded or i + 1 >= len(attempts):
                    raise
                logger.warning(f"主模型 {model} 流式请求失败，切换到备选模型 {attempts[i + 1][2]}: {e}")
    
    def reload(self):
        """从当前 settings 与环境变量重新加载配置。"""
        import os

        self.provider = os.environ.get("LLM_PROVIDER", settings.LLM_PROVIDER)
        self.api_key = os.environ.get("LLM_API_KEY", settings.LLM_API_KEY)
        self.base_url = os.environ.get("LLM_BASE_URL") or self._get_base_url()
        self.model = os.environ.get("LLM_MODEL", settings.LLM_MODEL)
        self.max_tokens = int(os.environ.get("LLM_MAX_TOKENS", settings.LLM_MAX_TOKENS))
        self.temperature = float(os.environ.get("LLM_TEMPERATURE", settings.LLM_TEMPERATURE))
        self.fallback_provider = os.environ.get("LLM_FALLBACK_PROVIDER", settings.LLM_FALLBACK_PROVIDER)
        self.fallback_api_key = os.environ.get("LLM_FALLBACK_API_KEY", settings.LLM_FALLBACK_API_KEY)
        self.fallback_base_url = os.environ.get("LLM_FALLBACK_BASE_URL", settings.LLM_FALLBACK_BASE_URL)
        self.fallback_model = os.environ.get("LLM_FALLBACK_MODEL", settings.LLM_FALLBACK_MODEL)

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
