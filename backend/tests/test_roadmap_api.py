"""Roadmap API 测试：force 参数透传"""
import pytest
from fastapi.testclient import TestClient

from main import app
from api.deps import get_current_user
from models.base import get_db
from models.user import User


@pytest.fixture
def auth_client(db_session):
    user = User(username="rm_api", hashed_password="x", role="admin")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    class CurrentUser:
        id = user.id
        username = user.username
        role = user.role

    app.dependency_overrides[get_current_user] = lambda: CurrentUser()

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    yield TestClient(app)

    app.dependency_overrides.clear()


def _mock_build_roadmap(monkeypatch, calls):
    async def fake_build(ws, llm_client=None, force_refresh=False, db=None):
        calls.append(force_refresh)
        return {"tables": [], "table_count": 0, "relationships": [], "questions": []}

    monkeypatch.setattr(
        "services.roadmap_service.RoadmapService.build_roadmap", fake_build
    )
    # api.roadmap 直接引用了 RoadmapService 类，patch 类方法即可生效


def test_roadmap_default_uses_cache(auth_client, db_session, monkeypatch):
    """不带 force 参数 → force_refresh=False（走缓存）"""
    from services.workspace_service import WorkspaceService

    ws = WorkspaceService.get_or_create_internal(
        db_session, db_session.query(User).filter_by(username="rm_api").first()
    )
    calls = []
    _mock_build_roadmap(monkeypatch, calls)

    resp = auth_client.get(
        f"/api/workspaces/{ws.id}/roadmap", headers={"Authorization": "Bearer t"}
    )
    assert resp.status_code == 200
    assert calls == [False]


def test_roadmap_force_refreshes(auth_client, db_session, monkeypatch):
    """force=true → force_refresh=True（「重新分析数据关系」）"""
    from services.workspace_service import WorkspaceService

    ws = WorkspaceService.get_or_create_internal(
        db_session, db_session.query(User).filter_by(username="rm_api").first()
    )
    calls = []
    _mock_build_roadmap(monkeypatch, calls)

    resp = auth_client.get(
        f"/api/workspaces/{ws.id}/roadmap?force=true",
        headers={"Authorization": "Bearer t"},
    )
    assert resp.status_code == 200
    assert calls == [True]
