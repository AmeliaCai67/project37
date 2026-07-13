from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_auto_login_creates_default_user():
    response = client.post("/api/auth/auto")
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"

    # 第二次调用应返回同一用户的新 token
    response2 = client.post("/api/auth/auto")
    assert response2.status_code == 200
