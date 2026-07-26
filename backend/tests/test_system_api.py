"""系统接口测试：原生目录选择器 pick-directory"""
import pytest
from fastapi.testclient import TestClient

from main import app
from api.deps import get_current_user
from models.base import get_db
from models.user import User


@pytest.fixture
def auth_client(db_session):
    """认证用户 + 依赖覆盖的测试客户端"""
    user = User(username="sys_tester", hashed_password="x", role="admin")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    class CurrentUser:
        id = user.id
        username = user.username
        role = user.role

    app.dependency_overrides[get_current_user] = lambda: CurrentUser()
    app.dependency_overrides[get_db] = lambda: iter([db_session])

    yield TestClient(app)

    app.dependency_overrides.clear()


def test_pick_directory_success(auth_client, monkeypatch):
    """用户选中目录 → 返回路径"""
    monkeypatch.setattr(
        "api.system._run_picker", lambda *a, **kw: ("ok", "/Users/test/data")
    )
    resp = auth_client.post(
        "/api/system/pick-directory", headers={"Authorization": "Bearer t"}
    )
    assert resp.status_code == 200
    assert resp.json() == {"path": "/Users/test/data"}


def test_pick_directory_cancelled(auth_client, monkeypatch):
    """用户取消 → path 为 None"""
    monkeypatch.setattr("api.system._run_picker", lambda *a, **kw: ("ok", None))
    resp = auth_client.post(
        "/api/system/pick-directory", headers={"Authorization": "Bearer t"}
    )
    assert resp.status_code == 200
    assert resp.json() == {"path": None}


def test_pick_directory_unavailable(auth_client, monkeypatch):
    """tkinter 不可用 → 503，前端回退手动输入"""
    monkeypatch.setattr(
        "api.system._run_picker", lambda *a, **kw: ("err", "no display")
    )
    resp = auth_client.post(
        "/api/system/pick-directory", headers={"Authorization": "Bearer t"}
    )
    assert resp.status_code == 503
    assert "手动输入" in resp.json()["detail"]


def test_pick_directory_requires_auth(db_session):
    """未认证 → 401"""
    app.dependency_overrides[get_db] = lambda: iter([db_session])
    try:
        resp = TestClient(app).post("/api/system/pick-directory")
        assert resp.status_code == 401
    finally:
        app.dependency_overrides.clear()
