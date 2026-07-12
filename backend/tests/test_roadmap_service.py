"""RoadmapService 测试"""
from pathlib import Path
import pytest

from services.roadmap_service import RoadmapService
from services.workspace_service import WorkspaceService
from services.file_service import FileService
from config import settings
from models.user import User


class FakeLLM:
    """同步/异步兼容的 Fake LLM，用于单元测试"""

    def __init__(self, content="- 语文和数学成绩的相关性如何？\n- 谁的总分最高？"):
        self.content = content

    async def chat_completion(self, messages, **kwargs):
        return {
            "choices": [{
                "message": {
                    "content": self.content
                }
            }]
        }


@pytest.fixture
def upload_root(tmp_path, monkeypatch):
    """将上传根目录重定向到临时目录，避免污染真实 uploads。"""
    monkeypatch.setattr(settings, "UPLOAD_DIR", tmp_path)
    return tmp_path


@pytest.mark.asyncio
async def test_build_roadmap_generates_questions(db_session, upload_root):
    user = User(username="r1", hashed_password="x", role="admin")
    db_session.add(user)
    db_session.commit()

    user_dir = FileService._get_user_dir(user.id)
    (user_dir / "语文成绩.csv").write_text("学生姓名,成绩\n张三,90\n李四,85\n")
    (user_dir / "数学成绩.csv").write_text("学生姓名,成绩\n张三,95\n李四,80\n")

    ws = WorkspaceService.get_or_create_internal(db_session, user)

    roadmap = await RoadmapService.build_roadmap(ws, llm_client=FakeLLM())

    assert "tables" in roadmap
    assert "relationships" in roadmap
    assert "questions" in roadmap
    assert len(roadmap["questions"]) > 0

    # 缓存应写入内部 .cache 目录，不在扫描源目录
    expected_cache = user_dir / ".cache" / "schema_graph.json"
    assert expected_cache.exists()


@pytest.mark.asyncio
async def test_build_roadmap_external_scans_internal_copy(db_session, upload_root):
    """external workspace 应先同步到内部隔离副本，再基于副本做画像，而非直接扫描 source_path。"""
    user = User(username="r_ext", hashed_password="x", role="admin")
    db_session.add(user)
    db_session.commit()

    src = upload_root / "external_src"
    src.mkdir()
    (src / "data.csv").write_text("学生姓名,成绩\n张三,90\n")
    # 非允许后缀的文件不应被复制到副本，也不应出现在画像里
    (src / "ignored.txt").write_text("secret")

    ws = WorkspaceService.mount(db_session, user, str(src), "外部空间")

    copy_dir = WorkspaceService.get_internal_copy_dir(user.id, ws.id)
    roadmap = await RoadmapService.build_roadmap(ws, llm_client=FakeLLM())

    table_names = {n["id"] for n in roadmap["tables"] if n["type"] == "table"}
    assert "data" in table_names
    assert "ignored" not in table_names
    # 数据已同步到内部副本
    assert (copy_dir / "data.csv").exists()

    # 缓存写入内部隔离副本的 .cache 目录，不在源目录
    expected_cache = copy_dir / ".cache" / "schema_graph.json"
    assert expected_cache.exists()


@pytest.mark.asyncio
async def test_build_roadmap_cache_not_in_source_dir(db_session, upload_root):
    """schema 缓存不得写入被扫描的源目录（尤其是外部挂载）。"""
    user = User(username="r_cache", hashed_password="x", role="admin")
    db_session.add(user)
    db_session.commit()

    src = upload_root / "external_src"
    src.mkdir()
    (src / "data.csv").write_text("product_name,sales_amount\nApple,100\n")

    ws = WorkspaceService.mount(db_session, user, str(src), "缓存隔离")

    copy_dir = WorkspaceService.get_internal_copy_dir(user.id, ws.id)
    (copy_dir / "data.csv").write_text("product_name,sales_amount\nApple,100\n")

    await RoadmapService.build_roadmap(ws, llm_client=FakeLLM())

    assert not (src / "schema_graph.json").exists()


def test_fallback_questions_uses_edges_and_nodes():
    graph = {
        "nodes": [
            {"name": "语文成绩"},
            {"name": "数学成绩"},
        ],
        "edges": [
            {
                "source": "语文成绩.学生姓名",
                "target": "数学成绩.学生姓名",
                "source_column": "学生姓名",
                "target_column": "学生姓名",
                "confidence": 1.0,
            }
        ],
    }
    questions = RoadmapService.fallback_questions(graph)
    assert len(questions) > 0
    assert "语文成绩" in questions[0]
    assert "数学成绩" in questions[0]


def test_fallback_questions_empty_graph():
    questions = RoadmapService.fallback_questions({"nodes": [], "edges": []})
    assert questions == []


@pytest.mark.asyncio
async def test_generate_questions_falls_back_on_llm_failure():
    class FailingLLM:
        async def chat_completion(self, messages, **kwargs):
            raise RuntimeError("LLM failed")

    graph = {
        "nodes": [{"name": "语文成绩"}],
        "edges": [],
    }
    questions = await RoadmapService.generate_questions(graph, llm_client=FailingLLM())
    assert len(questions) > 0
    assert "语文成绩" in questions[0]


@pytest.mark.asyncio
async def test_generate_questions_parses_dash_list():
    graph = {
        "nodes": [{"name": "语文成绩"}, {"name": "数学成绩"}],
        "edges": [
            {
                "source": "语文成绩.学生姓名",
                "target": "数学成绩.学生姓名",
                "source_column": "学生姓名",
                "target_column": "学生姓名",
                "confidence": 1.0,
            }
        ],
    }
    questions = await RoadmapService.generate_questions(graph, llm_client=FakeLLM())
    assert len(questions) == 2
    assert "语文" in questions[0]
    assert "总分" in questions[1]


def test_build_roadmap_resolves_internal_workspace_path(db_session, upload_root):
    user = User(username="r2", hashed_password="x", role="admin")
    db_session.add(user)
    db_session.commit()

    ws = WorkspaceService.get_or_create_internal(db_session, user)
    # internal workspace: 扫描用户上传根目录
    path = RoadmapService._resolve_scan_path(ws)
    assert path == FileService._get_user_dir(user.id)


def test_build_roadmap_resolves_external_workspace_path(db_session, upload_root):
    user = User(username="r3", hashed_password="x", role="admin")
    db_session.add(user)
    db_session.commit()

    src = upload_root / "ext"
    src.mkdir()
    ws = WorkspaceService.mount(db_session, user, str(src), "ext")

    path = RoadmapService._resolve_scan_path(ws)
    assert path == WorkspaceService.get_internal_copy_dir(user.id, ws.id)


def test_load_tables_skips_37_output_directory(tmp_path):
    """profiler 扫描工作空间时应跳过 37-output 产物目录"""
    from tools.schema_profiler import load_tables

    (tmp_path / "data.csv").write_text("a,b\n1,2\n")
    artifact_dir = tmp_path / "37-output"
    artifact_dir.mkdir()
    (artifact_dir / "artifact.csv").write_text("x,y\n3,4\n")

    tables = load_tables(tmp_path)
    assert "data" in tables
    assert "artifact" not in tables
    assert len(tables) == 1


def test_load_tables_skips_cache_directory(tmp_path):
    """profiler 扫描工作空间时应跳过 .cache 内部缓存目录"""
    from tools.schema_profiler import load_tables

    (tmp_path / "data.csv").write_text("a,b\n1,2\n")
    cache_dir = tmp_path / ".cache"
    cache_dir.mkdir()
    (cache_dir / "schema_graph.json").write_text('{"meta": {}}')

    tables = load_tables(tmp_path)
    assert "data" in tables
    assert len(tables) == 1
