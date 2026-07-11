"""RoadmapService 测试"""
from pathlib import Path
import pytest
import pytest_asyncio

from services.roadmap_service import RoadmapService
from services.workspace_service import WorkspaceService
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


@pytest.mark.asyncio
async def test_build_roadmap_generates_questions(db_session, tmp_path):
    user = User(username="r1", hashed_password="x", role="admin")
    db_session.add(user)
    db_session.commit()

    src = tmp_path / "data"
    src.mkdir()
    (src / "语文成绩.csv").write_text("学生姓名,成绩\n张三,90\n李四,85\n")
    (src / "数学成绩.csv").write_text("学生姓名,成绩\n张三,95\n李四,80\n")

    ws = WorkspaceService.mount(db_session, user, str(src), "成绩")

    roadmap = await RoadmapService.build_roadmap(db_session, ws, llm_client=FakeLLM())

    assert "tables" in roadmap
    assert "relationships" in roadmap
    assert "questions" in roadmap
    assert len(roadmap["questions"]) > 0


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


def test_build_roadmap_resolves_internal_workspace_path(db_session, tmp_path):
    user = User(username="r2", hashed_password="x", role="admin")
    db_session.add(user)
    db_session.commit()

    ws = WorkspaceService.get_or_create_internal(db_session, user)
    # internal workspace: output_path is .../37-output, source_path is None
    # RoadmapService should resolve to parent of output_path
    path = RoadmapService._resolve_workspace_path(ws)
    assert path.name != "37-output"
    assert path == Path(ws.output_path).parent


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
