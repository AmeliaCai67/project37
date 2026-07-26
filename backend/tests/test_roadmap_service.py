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


def _table_node(table_id, columns=None, row_count=100):
    """构造符合 schema_profiler 真实产出的表节点"""
    return {
        "id": table_id,
        "type": "table",
        "columns": columns or [],
        "row_count": row_count,
    }


def test_fallback_questions_uses_edges_and_nodes():
    graph = {
        "nodes": [
            _table_node("语文成绩"),
            _table_node("数学成绩"),
        ],
        "edges": [
            {
                "source": "语文成绩.学生姓名",
                "target": "数学成绩.学生姓名",
                "type": "same_column_name",
                "confidence": 1.0,
            }
        ],
    }
    questions = RoadmapService.fallback_questions(graph)
    assert len(questions) > 0
    assert "语文成绩" in questions[0]["question"]
    assert "数学成绩" in questions[0]["question"]
    assert questions[0]["type"] == "关联分析"


def test_fallback_questions_empty_graph():
    questions = RoadmapService.fallback_questions({"nodes": [], "edges": []})
    assert questions == []


@pytest.mark.asyncio
async def test_generate_questions_falls_back_on_llm_failure():
    class FailingLLM:
        async def chat_completion(self, messages, **kwargs):
            raise RuntimeError("LLM failed")

    graph = {
        "nodes": [_table_node("语文成绩")],
        "edges": [],
    }
    questions = await RoadmapService.generate_questions(graph, llm_client=FailingLLM())
    assert len(questions) > 0
    assert "语文成绩" in questions[0]["question"]


@pytest.mark.asyncio
async def test_generate_questions_parses_llm_json():
    """LLM 返回 JSON 数组（可带 Markdown 围栏）时应被解析为问题 dict"""
    llm = FakeLLM(
        '```json\n[{"question": "语文和数学成绩的相关性如何？", "tables": ["语文成绩", "数学成绩"], "type": "关联分析"},'
        '{"question": "谁的总分最高？", "tables": ["语文成绩"], "type": "排名/分布"}]\n```'
    )
    graph = {
        "nodes": [_table_node("语文成绩"), _table_node("数学成绩")],
        "edges": [
            {
                "source": "语文成绩.学生姓名",
                "target": "数学成绩.学生姓名",
                "type": "same_column_name",
                "confidence": 1.0,
            }
        ],
    }
    questions = await RoadmapService.generate_questions(graph, llm_client=llm)
    assert len(questions) == 2
    assert "语文" in questions[0]["question"]
    assert "总分" in questions[1]["question"]


@pytest.mark.asyncio
async def test_generate_questions_layered_fallback_types():
    """LLM 不可用时，兜底问题应按图谱分层：关联/趋势/排名/对比至少覆盖 3 类，无空表名"""
    class FailingLLM:
        async def chat_completion(self, messages, **kwargs):
            raise RuntimeError("LLM failed")

    graph = {
        "nodes": [
            _table_node("orders", row_count=1000),
            _table_node("items", row_count=3000),
            {"id": "orders.order_id", "type": "column", "table": "orders", "column": "order_id", "dtype": "string", "cardinality": 1000, "semantic_type": "uuid"},
            {"id": "orders.created_at", "type": "column", "table": "orders", "column": "created_at", "dtype": "datetime", "cardinality": 900, "semantic_type": "datetime_iso"},
            {"id": "orders.price", "type": "column", "table": "orders", "column": "price", "dtype": "numeric", "cardinality": 500, "semantic_type": None},
            {"id": "orders.state", "type": "column", "table": "orders", "column": "state", "dtype": "string", "cardinality": 5, "semantic_type": None},
            {"id": "items.order_id", "type": "column", "table": "items", "column": "order_id", "dtype": "string", "cardinality": 1000, "semantic_type": "uuid"},
        ],
        "edges": [
            {
                "source": "orders.order_id",
                "target": "items.order_id",
                "type": "same_column_name",
                "confidence": 0.95,
            },
            # 噪声边：低置信度 / 非同名列类型，不应产生关联问题
            {"source": "orders.price", "target": "items.order_id", "type": "distribution_similar", "confidence": 0.5},
        ],
    }
    questions = await RoadmapService.generate_questions(graph, llm_client=FailingLLM())
    types = {q["type"] for q in questions}
    assert len(types) >= 3
    assert "关联分析" in types
    assert "趋势/周期" in types
    for q in questions:
        assert q["question"].strip()
        assert all(t.strip() for t in q["tables"])
    # 无重复问题
    assert len({q["question"] for q in questions}) == len(questions)


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
