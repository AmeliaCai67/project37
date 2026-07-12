"""Chat + Workspace 集成测试"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch
from pathlib import Path

from main import app
from api.deps import get_current_user
from models.base import get_db
from models.user import User
from services.agent_service import AgentService
from services.roadmap_service import RoadmapService
from config import settings


@pytest.fixture(autouse=True)
def isolated_upload_dir(tmp_path, monkeypatch):
    """将上传根目录重定向到临时目录，避免测试间污染真实 uploads。"""
    upload_root = tmp_path / "uploads"
    upload_root.mkdir()
    monkeypatch.setattr(settings, "UPLOAD_DIR", upload_root)
    yield upload_root


@pytest.fixture
def auth_headers(db_session):
    """创建测试用户并设置认证/数据库依赖覆盖"""
    user = User(username="chat_ws_tester", hashed_password="x", role="admin")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

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


def _mock_llm_answer(answer: str):
    """返回一个会立即给出 Answer 的 LLM mock（适用于工作目录为空、幻觉 guard 不触发场景）"""
    return AsyncMock(return_value={
        "choices": [{
            "message": {"content": f"Thought: 直接回答\nAnswer: {answer}"}
        }],
        "usage": {"total_tokens": 10}
    })


def _mock_llm_answer_after_stat(answer: str):
    """先执行 stat 工具再给出 Answer，避免在有文件的工作空间触发幻觉 guard"""
    return AsyncMock(side_effect=[
        {
            "choices": [{
                "message": {"content": "Thought: 先查看文件\nAction: stat\nAction Input: {\"path\": \"a.csv\"}"}
            }],
            "usage": {"total_tokens": 10}
        },
        {
            "choices": [{
                "message": {"content": f"Thought: 基于文件回答\nAnswer: {answer}"}
            }],
            "usage": {"total_tokens": 10}
        },
    ])


def test_chat_with_external_workspace_uses_workspace_dirs(client: TestClient, auth_headers, tmp_path):
    """外部 workspace：Agent 应使用内部 copy 目录作为 working_dir，workspace output_path 作为 output_dir"""
    src = tmp_path / "data"
    src.mkdir()
    (src / "a.csv").write_text("x,y\n1,2\n")

    r = client.post("/api/workspaces/mount", headers=auth_headers, json={
        "local_path": str(src),
        "name": "test"
    })
    assert r.status_code == 200
    ws_id = r.json()["data"]["id"]
    ws_output_path = r.json()["data"]["output_path"]

    captured = {}
    original_init = AgentService.__init__

    def patched_init(self, *args, **kwargs):
        captured["working_dir"] = kwargs.get("working_dir") or (args[0] if args else None)
        captured["output_dir"] = kwargs.get("output_dir")
        return original_init(self, *args, **kwargs)

    with patch.object(AgentService, "__init__", patched_init):
        with patch("services.agent_service.llm_client.chat_completion", _mock_llm_answer_after_stat("hello from workspace")):
            r = client.post("/api/chat/send", headers=auth_headers, json={
                "message": "hi",
                "workspace_id": ws_id
            })

    assert r.status_code == 200
    assert r.json()["data"]["response"] == "hello from workspace"
    assert captured["working_dir"] is not None
    assert str(captured["working_dir"]).endswith(f"mounts/{ws_id}")
    assert str(captured["output_dir"]).startswith(ws_output_path)


def test_chat_without_workspace_uses_internal_workspace_dirs(client: TestClient, auth_headers):
    """未传 workspace_id：应使用默认 internal workspace 的 output_path，working_dir 为用户上传目录"""
    captured = {}
    original_init = AgentService.__init__

    def patched_init(self, *args, **kwargs):
        captured["working_dir"] = kwargs.get("working_dir") or (args[0] if args else None)
        captured["output_dir"] = kwargs.get("output_dir")
        return original_init(self, *args, **kwargs)

    with patch.object(AgentService, "__init__", patched_init):
        with patch("services.agent_service.llm_client.chat_completion", _mock_llm_answer("hello from internal")):
            r = client.post("/api/chat/send", headers=auth_headers, json={
                "message": "hi"
            })

    assert r.status_code == 200
    assert r.json()["data"]["response"] == "hello from internal"
    expected_user_dir = settings.UPLOAD_DIR / "user_1"
    assert Path(captured["working_dir"]) == expected_user_dir
    assert str(captured["output_dir"]).startswith(str(expected_user_dir / "37-output"))


def test_chat_with_invalid_workspace_returns_400(client: TestClient, auth_headers):
    """传入不存在的 workspace_id 应返回 400"""
    with patch("services.agent_service.llm_client.chat_completion", _mock_llm_answer("should not reach")):
        r = client.post("/api/chat/send", headers=auth_headers, json={
            "message": "hi",
            "workspace_id": 99999
        })
    assert r.status_code == 400


def test_upload_file_associates_with_workspace(client: TestClient, auth_headers):
    """文件上传时应关联到指定 workspace"""
    from services.file_service import FileService

    # 先创建 internal workspace
    r = client.get("/api/workspaces/list", headers=auth_headers)
    ws_id = r.json()["data"][0]["id"]

    file_content = b"x,y\n1,2\n"
    with patch.object(FileService, "extract_content_in_background", return_value=None):
        with patch.object(RoadmapService, "build_roadmap_in_background", return_value=None):
            r = client.post(
                "/api/files/upload",
                headers=auth_headers,
                data={"workspace_id": ws_id},
                files={"file": ("test.csv", file_content, "text/csv")}
            )
    assert r.status_code == 200
    file_data = r.json()["data"]
    assert file_data["workspace_id"] == ws_id


def test_upload_file_without_workspace_uses_internal(client: TestClient, auth_headers):
    """未指定 workspace 时上传文件应关联到默认 internal workspace"""
    from services.file_service import FileService

    file_content = b"x,y\n1,2\n"
    with patch.object(FileService, "extract_content_in_background", return_value=None):
        with patch.object(RoadmapService, "build_roadmap_in_background", return_value=None):
            r = client.post(
                "/api/files/upload",
                headers=auth_headers,
                files={"file": ("test.csv", file_content, "text/csv")}
            )
    assert r.status_code == 200
    file_data = r.json()["data"]
    # internal workspace 在 list_workspaces 时创建，文件应关联到它
    r = client.get("/api/workspaces/list", headers=auth_headers)
    internal_ws_id = r.json()["data"][0]["id"]
    assert file_data["workspace_id"] == internal_ws_id


def test_list_files_filters_by_workspace(client: TestClient, auth_headers):
    """/api/files/list 应根据 workspace_id 过滤文件"""
    from services.file_service import FileService

    r = client.get("/api/workspaces/list", headers=auth_headers)
    internal_ws_id = r.json()["data"][0]["id"]

    file_content = b"x,y\n1,2\n"
    with patch.object(FileService, "extract_content_in_background", return_value=None):
        with patch.object(RoadmapService, "build_roadmap_in_background", return_value=None):
            r = client.post(
                "/api/files/upload",
                headers=auth_headers,
                files={"file": ("internal.csv", file_content, "text/csv")}
            )
    assert r.status_code == 200

    # 不带 workspace_id 应返回所有文件
    r = client.get("/api/files/list", headers=auth_headers)
    assert r.status_code == 200
    all_files = r.json()["data"]
    assert len(all_files) >= 1

    # 带 internal workspace_id 应返回刚才上传的文件
    r = client.get("/api/files/list", headers=auth_headers, params={"workspace_id": internal_ws_id})
    assert r.status_code == 200
    filtered = r.json()["data"]
    assert len(filtered) >= 1
    assert all(f["workspace_id"] == internal_ws_id for f in filtered)

    # 带一个不存在的 workspace_id 应返回空列表
    r = client.get("/api/files/list", headers=auth_headers, params={"workspace_id": 99999})
    assert r.status_code == 200
    assert r.json()["data"] == []


def test_chat_stream_with_workspace(client: TestClient, auth_headers, tmp_path):
    """流式聊天接口同样应接受 workspace_id 并正常返回 SSE"""
    src = tmp_path / "data"
    src.mkdir()
    (src / "a.csv").write_text("x,y\n1,2\n")

    r = client.post("/api/workspaces/mount", headers=auth_headers, json={
        "local_path": str(src),
        "name": "stream_test"
    })
    assert r.status_code == 200
    ws_id = r.json()["data"]["id"]

    with patch("services.agent_service.llm_client.chat_completion", _mock_llm_answer_after_stat("stream answer")):
        with client.stream(
            "POST",
            "/api/chat/send/stream",
            headers=auth_headers,
            json={"message": "hi", "workspace_id": ws_id}
        ) as response:
            assert response.status_code == 200
            events = []
            for line in response.iter_lines():
                if line:
                    events.append(line if isinstance(line, str) else line.decode("utf-8"))
            assert any("stream answer" in e for e in events)
            assert events[-1] == "data: [DONE]"


def test_chat_response_includes_saved_path_and_records_artifacts(client: TestClient, auth_headers):
    """非流式聊天应返回 saved_path 并在输出目录创建时记录 OutputArtifact"""
    from services.output_artifact_service import OutputArtifactService
    from models.output_artifact import OutputArtifact
    from models.base import get_db

    # 确保 internal workspace 存在
    r = client.get("/api/workspaces/list", headers=auth_headers)
    ws_id = r.json()["data"][0]["id"]

    with patch("services.agent_service.llm_client.chat_completion", _mock_llm_answer("analysis result")):
        r = client.post("/api/chat/send", headers=auth_headers, json={
            "message": "analyze",
            "workspace_id": ws_id
        })

    assert r.status_code == 200
    data = r.json()["data"]
    assert data["response"] == "analysis result"
    assert data.get("saved_path") is not None
    assert "37-output" in data["saved_path"]

    # 验证 OutputArtifact 表被创建（无真实文件时 artifacts 为空列表）
    assert isinstance(data.get("artifacts"), list)
