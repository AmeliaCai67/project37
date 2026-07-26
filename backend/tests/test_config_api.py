from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def _auto_login() -> str:
    r = client.post("/api/auth/auto")
    assert r.status_code == 200
    return r.json()["access_token"]


def test_config_status_public():
    r = client.get("/api/config/status")
    assert r.status_code == 200
    assert "has_api_key" in r.json()


def test_update_config_requires_auth():
    r = client.post("/api/config", json={"llm_api_key": "sk-test"})
    assert r.status_code in (401, 403)


def test_update_config_with_admin():
    token = _auto_login()
    r = client.post(
        "/api/config",
        json={"llm_api_key": "sk-test", "llm_provider": "deepseek", "llm_model": "deepseek-chat"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert r.json()["success"] is True

    r2 = client.get("/api/config/status")
    assert r2.json()["has_api_key"] is True


def test_update_config_hot_reloads_settings_and_llm_client():
    """POST /api/config 后必须立即生效（无需重启）：
    settings 与 llm_client 的内存值都要更新为新 Key。"""
    from config import settings
    from core.llm_client import llm_client

    original_settings_key = settings.LLM_API_KEY
    original_client_key = llm_client.api_key
    token = _auto_login()
    new_key = "sk-hot-reload-test-unique"
    try:
        r = client.post(
            "/api/config",
            json={"llm_api_key": new_key, "llm_provider": "deepseek", "llm_model": "deepseek-chat"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200

        # 热更新断言：内存中的 settings 与 llm_client 必须立即拿到新 Key
        assert settings.LLM_API_KEY == new_key
        assert llm_client.api_key == new_key
    finally:
        # 恢复原值，避免污染同进程的其他测试
        settings.LLM_API_KEY = original_settings_key
        llm_client.api_key = original_client_key
