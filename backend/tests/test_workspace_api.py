"""Workspace API 测试"""
import pytest
from fastapi.testclient import TestClient

from main import app
from api.deps import get_current_user
from models.base import get_db
from models.user import User


@pytest.fixture
def auth_headers(db_session):
    """创建测试用户并设置认证/数据库依赖覆盖"""
    user = User(username="ws_tester", hashed_password="x", role="admin")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    # 使用简单对象替代 ORM 实例，避免跨会话延迟加载问题
    class CurrentUser:
        id = user.id
        username = user.username
        role = user.role

    def override_get_current_user():
        return CurrentUser()

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_current_user] = override_get_current_user
    app.dependency_overrides[get_db] = override_get_db

    yield {"Authorization": "Bearer test-token"}

    app.dependency_overrides.clear()


@pytest.fixture
def client(auth_headers):
    """创建测试客户端，使用内存数据库和固定用户"""
    with TestClient(app) as c:
        yield c


def test_list_workspaces(client: TestClient, auth_headers):
    r = client.get("/api/workspaces/list", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()["data"]
    assert len(data) >= 1
    assert data[0]["type"] == "internal"


def test_mount_and_unmount(client: TestClient, auth_headers, tmp_path):
    src = tmp_path / "data"
    src.mkdir()
    (src / "a.csv").write_text("x,y\n1,2\n")

    r = client.post("/api/workspaces/mount", headers=auth_headers, json={
        "local_path": str(src),
        "name": "期末数据"
    })
    assert r.status_code == 200, r.text
    ws_id = r.json()["data"]["id"]

    r = client.post(f"/api/workspaces/{ws_id}/unmount", headers=auth_headers)
    assert r.status_code == 200


def test_update_output_path(client: TestClient, auth_headers, tmp_path):
    output = tmp_path / "out"

    # 先确保存在内部工作空间
    r = client.get("/api/workspaces/list", headers=auth_headers)
    ws_id = r.json()["data"][0]["id"]

    r = client.put(
        f"/api/workspaces/{ws_id}/output-path",
        headers=auth_headers,
        json={"output_path": str(output)}
    )
    assert r.status_code == 200
    assert r.json()["data"]["output_path"] == str(output)
