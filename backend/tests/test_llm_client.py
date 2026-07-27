"""LLMClient 服务商预设与备选模型测试"""
import httpx
import pytest

from core.llm_client import LLMClient, PROVIDER_PRESETS

pytestmark = pytest.mark.asyncio


@pytest.fixture()
def client():
    return LLMClient()


def test_base_url_presets(client, monkeypatch):
    """每个预设 provider 都解析到对应的 OpenAI 兼容 base_url"""
    from config import settings

    monkeypatch.setattr(settings, "LLM_BASE_URL", "")
    expected = {
        "deepseek": "https://api.deepseek.com/v1",
        "kimi": "https://api.moonshot.cn/v1",
        "qwen": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "zhipu": "https://open.bigmodel.cn/api/paas/v4",
        "minimax": "https://api.minimax.chat/v1",
        "openai": "https://api.openai.com/v1",
    }
    assert expected == PROVIDER_PRESETS
    for provider, url in expected.items():
        client.provider = provider
        assert client._get_base_url() == url


def test_base_url_override_wins(client, monkeypatch):
    """显式设置 LLM_BASE_URL 时优先于预设"""
    from config import settings

    monkeypatch.setattr(settings, "LLM_BASE_URL", "https://my-proxy.example.com/v1")
    client.provider = "kimi"
    assert client._get_base_url() == "https://my-proxy.example.com/v1"


def test_unknown_provider_falls_back_to_deepseek(client, monkeypatch):
    """未认识的 provider（custom 等）无 base_url 时回退 deepseek"""
    from config import settings

    monkeypatch.setattr(settings, "LLM_BASE_URL", "")
    client.provider = "custom"
    assert client._get_base_url() == PROVIDER_PRESETS["deepseek"]


def _http_error():
    return httpx.ConnectError("connection refused")


def _setup_fallback(client):
    client.fallback_provider = "kimi"
    client.fallback_api_key = "sk-fallback"
    client.fallback_base_url = ""
    client.fallback_model = "kimi-k2-0905-preview"


async def test_no_fallback_by_default(client):
    """默认未配置备选，尝试列表只有主配置"""
    assert client._attempts() == [(client.base_url, client.api_key, client.model)]


async def test_fallback_in_attempts(client):
    """配置备选后尝试列表包含备选（base_url 走预设）"""
    _setup_fallback(client)
    attempts = client._attempts()
    assert len(attempts) == 2
    assert attempts[1] == ("https://api.moonshot.cn/v1", "sk-fallback", "kimi-k2-0905-preview")


async def test_chat_completion_switches_to_fallback(client, monkeypatch):
    """主模型失败时自动切到备选模型"""
    _setup_fallback(client)
    calls = []

    async def fake_post(base_url, api_key, model, messages, stream, tools, temperature, max_tokens):
        calls.append(model)
        if len(calls) == 1:
            raise _http_error()
        return {"choices": [{"message": {"content": "ok"}}]}

    monkeypatch.setattr(client, "_post_chat", fake_post)
    result = await client.chat_completion([{"role": "user", "content": "hi"}])
    assert result["choices"][0]["message"]["content"] == "ok"
    assert calls == [client.model, "kimi-k2-0905-preview"]


async def test_chat_completion_raises_without_fallback(client, monkeypatch):
    """无备选时主模型失败直接抛出"""
    async def fake_post(*args, **kwargs):
        raise _http_error()

    monkeypatch.setattr(client, "_post_chat", fake_post)
    with pytest.raises(httpx.HTTPError):
        await client.chat_completion([{"role": "user", "content": "hi"}])


async def test_stream_switches_to_fallback_before_first_chunk(client, monkeypatch):
    """流式：首个 chunk 前失败自动切换备选"""
    _setup_fallback(client)
    calls = []

    async def fake_stream(base_url, api_key, model, messages, temperature, max_tokens):
        calls.append(model)
        if len(calls) == 1:
            raise _http_error()
        yield "你"
        yield "好"

    monkeypatch.setattr(client, "_stream_once", fake_stream)
    chunks = [c async for c in client.chat_completion_stream([{"role": "user", "content": "hi"}])]
    assert chunks == ["你", "好"]
    assert calls == [client.model, "kimi-k2-0905-preview"]


async def test_stream_no_switch_after_first_chunk(client, monkeypatch):
    """流式：已开始输出后失败直接抛出，不切备选（避免内容重复）"""
    _setup_fallback(client)

    async def fake_stream(*args, **kwargs):
        yield "部分"
        raise _http_error()

    monkeypatch.setattr(client, "_stream_once", fake_stream)
    with pytest.raises(httpx.HTTPError):
        async for _ in client.chat_completion_stream([{"role": "user", "content": "hi"}]):
            pass
