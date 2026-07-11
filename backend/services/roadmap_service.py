"""RoadmapService — 数据空间 schema 画像与推荐问题生成"""
from pathlib import Path
from typing import Any, Dict, List, Optional

from models.workspace import Workspace
from tools.schema_profiler import SchemaProfiler
from core.llm_client import llm_client as default_llm_client
from core.logging import get_logger
from services.file_service import FileService
from services.workspace_service import WorkspaceService

logger = get_logger(__name__)


class RoadmapService:
    @staticmethod
    def _resolve_scan_path(workspace: Workspace) -> Path:
        """解析工作空间应扫描的数据目录路径。"""
        if workspace.type == "internal":
            # internal workspace：扫描用户上传根目录，跳过 37-output 与 .cache
            return FileService._get_user_dir(workspace.owner_id)
        # external workspace：扫描内部隔离副本目录，尊重 copy isolation
        return WorkspaceService.get_internal_copy_dir(
            workspace.owner_id, workspace.id
        )

    @staticmethod
    def _cache_path(workspace: Workspace) -> Path:
        """计算 schema 图谱缓存路径（内部缓存，不污染源目录）。"""
        user_dir = FileService._get_user_dir(workspace.owner_id)
        return user_dir / ".cache" / f"{workspace.id}_schema_graph.json"

    @staticmethod
    async def build_roadmap(
        workspace: Workspace,
        llm_client: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """
        构建工作空间的数据画像与推荐问题路线图。

        Args:
            workspace: 工作空间 ORM 对象
            llm_client: 可选的 LLM 客户端，默认为全局 llm_client

        Returns:
            {"tables": [...], "relationships": [...], "questions": [...]}
        """
        scan_path = RoadmapService._resolve_scan_path(workspace)
        cache_path = RoadmapService._cache_path(workspace)

        profiler = SchemaProfiler()
        graph = profiler.build_and_cache(scan_path, cache_path)

        questions = await RoadmapService.generate_questions(
            graph, llm_client or default_llm_client
        )

        return {
            "tables": graph.get("nodes", []),
            "relationships": graph.get("edges", []),
            "questions": questions,
        }

    @staticmethod
    async def generate_questions(graph: Dict[str, Any], llm_client: Any) -> List[str]:
        """基于数据关系图谱生成自然语言分析问题。"""
        if not graph or not graph.get("edges"):
            return RoadmapService.fallback_questions(graph)

        summary = RoadmapService._summarize_graph(graph)
        messages = [
            {
                "role": "system",
                "content": "你是一个数据分析师，擅长把数据关系翻译成非技术人员能听懂的问题。",
            },
            {
                "role": "user",
                "content": f"""基于以下数据关系，生成 3-5 个自然语言分析问题：

{summary}

要求：
- 问题要具体，直接对应表格和字段
- 优先推荐有明确关联关系的问题
- 不要复杂统计术语
- 每个问题一句话
- 不要 emoji

请只输出问题列表，每行一个，以 "- " 开头。""",
            },
        ]

        try:
            resp = await llm_client.chat_completion(messages, temperature=0.3)
            content = resp["choices"][0]["message"]["content"]
            questions = [
                line.strip("- ").strip()
                for line in content.split("\n")
                if line.strip().startswith("-")
            ]
            if questions:
                return questions[:5]
        except Exception:
            logger.exception("Failed to generate questions via LLM, falling back")

        return RoadmapService.fallback_questions(graph)

    @staticmethod
    def fallback_questions(graph: Dict[str, Any]) -> List[str]:
        """当 LLM 不可用或图谱为空时的推荐问题兜底策略。"""
        questions = []
        edges = graph.get("edges", []) if graph else []
        for edge in edges[:3]:
            src = edge.get("source", "")
            tgt = edge.get("target", "")
            col = edge.get("source_column", "")
            questions.append(
                f"{src} 和 {tgt} 可以通过 {col} 关联，你想分析它们之间的关系吗？"
            )

        nodes = graph.get("nodes", []) if graph else []
        for node in nodes[:2]:
            name = node.get("name", "")
            questions.append(f"{name} 里有哪些值得关注的趋势或分布？")

        return questions[:5]

    @staticmethod
    def _summarize_graph(graph: Dict[str, Any]) -> str:
        """将图谱信息转换为适合 LLM 理解的文本摘要。"""
        lines = ["表格："]
        for node in graph.get("nodes", []):
            if node.get("type") == "table":
                lines.append(
                    f"- {node.get('name')}，列：{', '.join(node.get('columns', []))}"
                )
        lines.append("\n关系：")
        for edge in graph.get("edges", [])[:10]:
            lines.append(
                f"- {edge.get('source')}.{edge.get('source_column')} → "
                f"{edge.get('target')}.{edge.get('target_column')} "
                f"(置信度 {edge.get('confidence', 0):.2f})"
            )
        return "\n".join(lines)
