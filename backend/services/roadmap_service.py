"""RoadmapService — 数据空间 schema 画像与推荐问题生成"""
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from models.workspace import Workspace
from tools.schema_profiler import SchemaProfiler
from core.llm_client import llm_client as default_llm_client
from core.logging import get_logger
from services.file_service import FileService
from services.workspace_service import WorkspaceService
from tools.schema_profiler import CACHE_FILENAME

logger = get_logger(__name__)

# 上传文件名的时间戳前缀：20260719_143000_orders -> orders
_TIMESTAMP_PREFIX_RE = re.compile(r"^\d{8}_\d{6}_")

# 只有高置信度的同名列边才视为可靠关联，喂给 LLM / 用于兜底推荐
RELIABLE_EDGE_CONFIDENCE = 0.8
RELIABLE_EDGE_TYPE = "same_column_name"

# 语义类别在摘要中的展示顺序
_CATEGORY_ORDER = ("id", "日期", "数值", "类别", "地理", "文本")


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
        scan_path = RoadmapService._resolve_scan_path(workspace)
        return scan_path / ".cache" / CACHE_FILENAME

    @staticmethod
    def _display_name(table_id: str) -> str:
        """去掉上传文件名的时间戳前缀，返回用户可读的表名。"""
        return _TIMESTAMP_PREFIX_RE.sub("", table_id or "")

    @staticmethod
    def _split_column_ref(ref: str) -> tuple:
        """将 '表.列' 引用拆为 (表名, 列名)。"""
        if "." in (ref or ""):
            table, column = ref.rsplit(".", 1)
            return table, column
        return ref or "", ""

    @staticmethod
    def _classify_column(col: Dict[str, Any]) -> str:
        """将列节点归类为 id / 日期 / 数值 / 类别 / 文本 / 地理 六大语义类别。"""
        sem = col.get("semantic_type")
        dtype = col.get("dtype")
        if sem in ("uuid", "id_card_cn"):
            return "id"
        if sem == "latitude_longitude":
            return "地理"
        if dtype == "datetime" or sem in ("date_iso", "datetime_iso"):
            return "日期"
        if dtype == "numeric":
            return "数值"
        if dtype == "boolean" or (dtype == "string" and col.get("cardinality", 0) <= 20):
            return "类别"
        return "文本"

    @staticmethod
    def _analyze_graph(graph: Dict[str, Any]) -> Dict[str, Any]:
        """从图谱提取表画像（按语义类别分组的列）与可靠关联边。"""
        nodes = graph.get("nodes", []) if graph else []
        edges = graph.get("edges", []) if graph else []

        tables: Dict[str, Dict[str, Any]] = {}
        for node in nodes:
            if node.get("type") != "table":
                continue
            tid = node.get("id", "")
            tables[tid] = {
                "id": tid,
                "display_name": RoadmapService._display_name(tid),
                "row_count": node.get("row_count", 0),
                "columns": {},  # 语义类别 -> [列信息]
            }

        for node in nodes:
            if node.get("type") != "column":
                continue
            tname = node.get("table", "")
            if tname not in tables:
                continue
            category = RoadmapService._classify_column(node)
            info: Dict[str, Any] = {"name": node.get("column", "")}
            if category in ("数值", "日期") and "min" in node and "max" in node:
                info["range"] = (node["min"], node["max"])
            if category == "类别" and node.get("sample_values"):
                info["samples"] = node["sample_values"]
            tables[tname]["columns"].setdefault(category, []).append(info)

        reliable_edges = [
            e for e in edges
            if e.get("type") == RELIABLE_EDGE_TYPE
            and e.get("confidence", 0) >= RELIABLE_EDGE_CONFIDENCE
        ]
        return {"tables": tables, "reliable_edges": reliable_edges}

    @staticmethod
    async def build_roadmap(
        workspace: Workspace,
        llm_client: Optional[Any] = None,
        force_refresh: bool = False,
        db: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """
        构建工作空间的数据画像与推荐问题路线图。

        Args:
            workspace: 工作空间 ORM 对象
            llm_client: 可选的 LLM 客户端，默认为全局 llm_client
            force_refresh: 为 True 时忽略缓存重新画像（缓存失效触发点使用）

        Returns:
            {"tables": [...], "table_count": N, "relationships": [...], "questions": [...]}
        """
        scan_path = RoadmapService._resolve_scan_path(workspace)

        # 对外部 workspace，确保内部隔离副本已同步，避免画像时看不到数据
        if workspace.type == "external":
            WorkspaceService.sync_external_to_copy(db, workspace, scan_path)

        cache_path = RoadmapService._cache_path(workspace)

        # 缓存命中（含 questions）时直接返回，不再调 LLM
        if not force_refresh:
            cached = RoadmapService._load_cached_roadmap(cache_path)
            if cached is not None:
                return cached

        profiler = SchemaProfiler()
        graph = profiler.build_and_cache(scan_path, cache_path)

        questions = await RoadmapService.generate_questions(
            graph, llm_client or default_llm_client
        )

        # questions 随图谱一起写入缓存，供后续请求直接命中
        try:
            payload = dict(graph)
            payload["questions"] = questions
            cache_path.write_text(
                json.dumps(payload, indent=2, ensure_ascii=False, default=str),
                encoding="utf-8",
            )
        except Exception:
            logger.warning("Failed to write roadmap questions cache %s", cache_path)

        return RoadmapService._format_roadmap(graph, questions)

    @staticmethod
    def _load_cached_roadmap(cache_path: Path) -> Optional[Dict[str, Any]]:
        """读取含 questions 的缓存画像；缓存缺失或不完整时返回 None。"""
        if not cache_path.exists():
            return None
        try:
            cached = json.loads(cache_path.read_text(encoding="utf-8"))
        except Exception:
            return None
        if not isinstance(cached, dict) or cached.get("questions") is None:
            return None
        return RoadmapService._format_roadmap(cached, cached["questions"])

    @staticmethod
    def _format_roadmap(graph: Dict[str, Any], questions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """组装 roadmap 响应：只统计 type == 'table' 的节点，并附带 display_name。"""
        table_nodes = []
        for node in graph.get("nodes", []):
            if node.get("type") != "table":
                continue
            table_node = dict(node)
            table_node["display_name"] = RoadmapService._display_name(
                node.get("id", "")
            )
            table_nodes.append(table_node)

        return {
            "tables": table_nodes,
            "table_count": len(table_nodes),
            "relationships": graph.get("edges", []),
            "questions": questions,
        }

    @staticmethod
    async def generate_questions(graph: Dict[str, Any], llm_client: Any) -> List[Dict[str, Any]]:
        """基于数据画像分层生成推荐问题，返回 [{question, tables, type}]。"""
        if not graph or not graph.get("nodes"):
            return RoadmapService.fallback_questions(graph)

        summary = RoadmapService._summarize_graph(graph)
        messages = [
            {
                "role": "system",
                "content": (
                    "你是一个数据分析师，擅长为非技术人员设计直白的数据分析问题。"
                    "只输出 JSON，不要输出其他内容。"
                ),
            },
            {
                "role": "user",
                "content": f"""基于以下数据画像，生成 4 个自然语言分析问题：

{summary}

要求：
- 输出 JSON 数组，每个元素为 {{"question": "...", "tables": ["表名"], "type": "类型"}}
- type 尽量覆盖四类：关联分析（仅当存在可靠关联时）、趋势/周期（有日期列时）、排名/分布（有数值列时）、对比/占比（有类别列时）
- question 要具体，直接使用上面的表名和列名，一句话
- tables 使用上面的表名
- 不要复杂统计术语，不要 emoji

只输出 JSON 数组本身。""",
            },
        ]

        try:
            resp = await llm_client.chat_completion(messages, temperature=0.3)
            content = resp["choices"][0]["message"]["content"]
            questions = RoadmapService._parse_questions(content)
            if questions:
                return questions[:5]
        except Exception:
            logger.exception("Failed to generate questions via LLM, falling back")

        return RoadmapService.fallback_questions(graph)

    @staticmethod
    def _parse_questions(content: str) -> List[Dict[str, Any]]:
        """解析 LLM 输出的 JSON 问题数组，容忍 Markdown 代码围栏。"""
        if not content:
            return []
        text = content.strip()
        # 去掉 ```json ... ``` 围栏
        fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
        if fence:
            text = fence.group(1).strip()
        # 截取第一个 [ 到最后一个 ]，容忍前后杂音
        start, end = text.find("["), text.rfind("]")
        if start == -1 or end == -1 or end <= start:
            return []
        try:
            items = json.loads(text[start:end + 1])
        except (json.JSONDecodeError, ValueError):
            return []
        if not isinstance(items, list):
            return []

        questions = []
        for item in items:
            if not isinstance(item, dict):
                continue
            question = str(item.get("question", "")).strip()
            if not question:
                continue
            tables = item.get("tables") or []
            if not isinstance(tables, list):
                tables = [str(tables)]
            questions.append({
                "question": question,
                "tables": [str(t) for t in tables if str(t).strip()],
                "type": str(item.get("type", "")).strip() or "概览",
            })
        return questions

    @staticmethod
    def fallback_questions(graph: Dict[str, Any]) -> List[Dict[str, Any]]:
        """当 LLM 不可用或图谱为空时，按规则从图谱分层生成兜底问题。"""
        analysis = RoadmapService._analyze_graph(graph)
        tables = analysis["tables"]

        questions: List[Dict[str, Any]] = []
        seen = set()

        def _add(question: str, table_names: List[str], qtype: str) -> None:
            table_names = [t for t in table_names if t]
            if not question or not table_names or question in seen:
                return
            seen.add(question)
            questions.append({
                "question": question,
                "tables": table_names,
                "type": qtype,
            })

        # 1. 关联分析：仅使用可靠边
        for edge in analysis["reliable_edges"][:2]:
            src_table, src_col = RoadmapService._split_column_ref(edge.get("source", ""))
            tgt_table, _ = RoadmapService._split_column_ref(edge.get("target", ""))
            src_name = RoadmapService._display_name(src_table)
            tgt_name = RoadmapService._display_name(tgt_table)
            if not src_name or not tgt_name or not src_col:
                continue
            _add(
                f"{src_name} 和 {tgt_name} 可以通过 {src_col} 关联，"
                f"两张表结合起来能发现什么规律？",
                [src_name, tgt_name],
                "关联分析",
            )

        # 2. 趋势/周期：有日期列的表
        for t in tables.values():
            date_cols = t["columns"].get("日期") or []
            if not t["display_name"] or not date_cols:
                continue
            numeric_cols = t["columns"].get("数值") or []
            if numeric_cols:
                q = (f"{t['display_name']} 中 {numeric_cols[0]['name']} "
                     f"随 {date_cols[0]['name']} 的变化趋势如何？")
            else:
                q = (f"{t['display_name']} 的记录 "
                     f"随 {date_cols[0]['name']} 的分布趋势如何？")
            _add(q, [t["display_name"]], "趋势/周期")
            if len([x for x in questions if x["type"] == "趋势/周期"]) >= 2:
                break

        # 3. 排名/分布：有数值列的表
        for t in tables.values():
            numeric_cols = t["columns"].get("数值") or []
            if not t["display_name"] or not numeric_cols:
                continue
            _add(
                f"{t['display_name']} 中 {numeric_cols[0]['name']} 的排名和分布情况如何？",
                [t["display_name"]],
                "排名/分布",
            )
            if len([x for x in questions if x["type"] == "排名/分布"]) >= 2:
                break

        # 4. 对比/占比：有类别列的表
        for t in tables.values():
            cat_cols = t["columns"].get("类别") or []
            if not t["display_name"] or not cat_cols:
                continue
            _add(
                f"{t['display_name']} 中 {cat_cols[0]['name']} 各类别的对比和占比如何？",
                [t["display_name"]],
                "对比/占比",
            )
            if len([x for x in questions if x["type"] == "对比/占比"]) >= 2:
                break

        # 5. 通用兜底：表概览，保证任何非空图谱都有可读问题
        if not questions:
            for t in list(tables.values())[:3]:
                _add(
                    f"{t['display_name']} 里有哪些值得关注的趋势或分布？",
                    [t["display_name"]],
                    "概览",
                )

        return questions[:5]

    @staticmethod
    async def build_roadmap_in_background(workspace_id: int) -> None:
        """后台任务：为指定工作空间重建数据画像（创建独立 session，强制刷新缓存）。"""
        from models.base import SessionLocal
        db = SessionLocal()
        try:
            ws = db.query(Workspace).filter_by(id=workspace_id).first()
            if ws:
                await RoadmapService.build_roadmap(ws, force_refresh=True, db=db)
        finally:
            db.close()

    @staticmethod
    def _summarize_graph(graph: Dict[str, Any]) -> str:
        """将图谱信息转换为适合 LLM 理解的文本摘要（含语义分类、范围与示例值）。"""
        analysis = RoadmapService._analyze_graph(graph)

        lines = ["表格："]
        for t in analysis["tables"].values():
            lines.append(f"- {t['display_name']}（约 {t['row_count']} 行）")
            for category in _CATEGORY_ORDER:
                cols = t["columns"].get(category)
                if not cols:
                    continue
                parts = []
                for c in cols[:8]:
                    desc = c["name"]
                    if "range" in c:
                        desc += f"（范围 {c['range'][0]} ~ {c['range'][1]}）"
                    if "samples" in c:
                        desc += f"（如 {'、'.join(c['samples'][:3])}）"
                    parts.append(desc)
                label = f"{category}列" if category != "id" else "id列"
                lines.append(f"  {label}：{'、'.join(parts)}")

        lines.append("\n可靠关联：")
        reliable = analysis["reliable_edges"]
        if reliable:
            for edge in reliable[:10]:
                src_table, src_col = RoadmapService._split_column_ref(edge.get("source", ""))
                tgt_table, _ = RoadmapService._split_column_ref(edge.get("target", ""))
                lines.append(
                    f"- {RoadmapService._display_name(src_table)} 与 "
                    f"{RoadmapService._display_name(tgt_table)} 可通过 {src_col} 关联"
                    f"（置信度 {edge.get('confidence', 0):.2f}）"
                )
        else:
            lines.append("- 暂无可靠关联")
        return "\n".join(lines)
