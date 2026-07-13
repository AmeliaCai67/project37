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
