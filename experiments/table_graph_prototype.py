#!/usr/bin/env python3
"""
table_graph_prototype.py — 多表格关联发现原型（优化版）

v2 优化点：
  1. 鲁棒性：编码自动嗅探、分隔符嗅探、大表行数限制、datetime/boolean 类型识别
  2. 算法：MinHash+LSH 降维、倒排索引列名匹配、外键剪枝
  3. 业务：TF-IDF 列名语义相似度、语义类型打标、复合键探测

用法:
  python experiments/table_graph_prototype.py --dir csv-data
  python experiments/table_graph_prototype.py --dir csv-data --output report.json --max-rows 100000
"""

import argparse
import csv
import json
import sys
from pathlib import Path
from collections import defaultdict
from typing import Any, Dict, List, Optional, Set, Tuple

import pandas as pd
import numpy as np
import chardet

from minhash_lsh import MinHash, LSH
from semantic_typer import SemanticTyper
from column_embedding import ColumnEmbedder

# ── 全局常量 ──
DEFAULT_MAX_ROWS = 200_000      # 单表最大读取行数，防止 OOM
DEFAULT_SAMPLE_SIZE = 5_000   # 列统计采样数
DEFAULT_CHUNK_SIZE = 10_000   # 分块读取块大小
MINHASH_PERM = 128
LSH_BANDS = 16

semantic_typer = SemanticTyper()
minhash_engine = MinHash(num_perm=MINHASH_PERM, seed=37)
lsh_engine = LSH(num_perm=MINHASH_PERM, num_bands=LSH_BANDS)


# ═══════════════════════════════════════════════════════════════
#  1. 鲁棒性：加载与编码容错
# ═══════════════════════════════════════════════════════════════

def sniff_encoding(filepath: Path) -> str:
    """使用 chardet 嗅探文件编码。"""
    try:
        with open(filepath, "rb") as f:
            raw = f.read(200_000)
            result = chardet.detect(raw)
            enc = result.get("encoding")
            if enc:
                return enc
    except Exception:
        pass
    return "utf-8"


def sniff_delimiter(filepath: Path, encoding: str) -> str:
    """使用 csv.Sniffer 嗅探分隔符。"""
    try:
        with open(filepath, "r", encoding=encoding, errors="replace") as f:
            sample = f.read(8192)
            dialect = csv.Sniffer().sniff(sample)
            return dialect.delimiter
    except Exception:
        return ","


def read_csv_robust(filepath: Path, max_rows: int = DEFAULT_MAX_ROWS) -> Optional[pd.DataFrame]:
    """鲁棒的 CSV 读取：自动编码、分隔符嗅探、行数限制。"""
    encoding = sniff_encoding(filepath)
    delimiter = sniff_delimiter(filepath, encoding)

    # 优先尝试嗅探到的编码和分隔符
    attempts = [
        {"encoding": encoding, "sep": delimiter},
        {"encoding": "utf-8", "sep": ","},
        {"encoding": "utf-8", "sep": ";"},
        {"encoding": "utf-8", "sep": "\t"},
        {"encoding": "gbk", "sep": ","},
        {"encoding": "gb2312", "sep": ","},
        {"encoding": "latin1", "sep": ","},
        {"encoding": "iso-8859-1", "sep": ","},
    ]

    for cfg in attempts:
        try:
            df = pd.read_csv(
                filepath,
                dtype=str,
                keep_default_na=True,
                nrows=max_rows,
                **cfg,
            )
            return df
        except Exception:
            continue

    print(f"[WARN] 无法解析 {filepath.name}，已跳过", file=sys.stderr)
    return None


def read_excel_robust(filepath: Path, max_rows: int = DEFAULT_MAX_ROWS) -> Optional[pd.DataFrame]:
    """鲁棒的 Excel 读取，限制行数。"""
    try:
        df = pd.read_excel(filepath, dtype=str, keep_default_na=True, nrows=max_rows)
        return df
    except Exception as e:
        print(f"[WARN] 无法解析 {filepath.name}: {e}", file=sys.stderr)
        return None


def load_tables(dir_path: Path, max_rows: int = DEFAULT_MAX_ROWS) -> Dict[str, pd.DataFrame]:
    """加载目录下所有 CSV / Excel 文件。"""
    tables = {}
    for p in sorted(dir_path.iterdir()):
        if p.suffix.lower() == ".csv":
            df = read_csv_robust(p, max_rows)
            if df is not None:
                tables[p.stem] = df
        elif p.suffix.lower() in (".xlsx", ".xls"):
            df = read_excel_robust(p, max_rows)
            if df is not None:
                tables[p.stem] = df
    return tables


# ═══════════════════════════════════════════════════════════════
#  2. 鲁棒性：增强型列统计
# ═══════════════════════════════════════════════════════════════

def detect_datetime(series: pd.Series) -> bool:
    """试探该列是否为日期时间类型。"""
    s = series.dropna().astype(str).head(200)
    if len(s) == 0:
        return False
    try:
        dt = pd.to_datetime(s, errors="coerce")
        return dt.notna().sum() / len(s) > 0.75
    except Exception:
        return False


def detect_boolean(series: pd.Series) -> bool:
    """试探该列是否为布尔类型。"""
    bool_vals = {"true", "false", "1", "0", "yes", "no", "t", "f", "y", "n", "on", "off"}
    s = series.dropna().astype(str).str.lower().head(200)
    if len(s) == 0:
        return False
    return s.isin(bool_vals).sum() / len(s) > 0.9


def column_stats(
    df: pd.DataFrame,
    col: str,
    sample_size: int = DEFAULT_SAMPLE_SIZE,
) -> Dict[str, Any]:
    """计算单列统计指纹（增强版）。"""
    s = df[col]
    total = len(s)

    # 采样
    if total > sample_size:
        s_sample = s.sample(sample_size, random_state=37)
    else:
        s_sample = s

    uniques = s_sample.dropna().unique()
    cardinality = len(uniques)
    null_ratio = s.isna().sum() / total if total else 0.0

    # ── 类型识别 ──
    dtype = "string"
    numeric = pd.to_numeric(s_sample, errors="coerce")
    is_numeric = numeric.notna().sum() / max(len(s_sample), 1) > 0.8

    if is_numeric:
        dtype = "numeric"
    elif detect_datetime(s_sample):
        dtype = "datetime"
    elif detect_boolean(s_sample):
        dtype = "boolean"

    stats = {
        "dtype": dtype,
        "cardinality": cardinality,
        "null_ratio": round(null_ratio, 4),
        "total_rows": total,
        "sample_uniques": set(uniques[: min(200, cardinality)]),
    }

    if dtype == "numeric":
        stats["mean"] = float(numeric.mean())
        stats["std"] = float(numeric.std())
        stats["min"] = float(numeric.min())
        stats["max"] = float(numeric.max())
    elif dtype == "datetime":
        dt = pd.to_datetime(s_sample, errors="coerce")
        stats["min"] = str(dt.min())
        stats["max"] = str(dt.max())
        stats["count"] = int(dt.notna().sum())
    elif dtype == "boolean":
        bool_map = {"true": True, "1": True, "yes": True, "t": True, "y": True, "on": True}
        mapped = s_sample.dropna().astype(str).str.lower().map(bool_map)
        mapped = mapped.infer_objects(copy=False).fillna(False)
        stats["true_ratio"] = float(mapped.mean())
    else:
        lengths = s_sample.dropna().astype(str).str.len()
        stats["avg_len"] = float(lengths.mean()) if len(lengths) else 0.0
        stats["max_len"] = int(lengths.max()) if len(lengths) else 0

    # ── 语义类型打标 ──
    sample_for_semantic = uniques[: min(100, cardinality)]
    sem_type = semantic_typer.infer(sample_for_semantic.tolist(), col)
    if sem_type:
        stats["semantic_type"] = sem_type

    return stats


def build_column_index(tables: Dict[str, pd.DataFrame]) -> Dict[str, Dict[str, Any]]:
    """为每个表-列构建统计指纹索引。"""
    index = {}
    for table_name, df in tables.items():
        for col in df.columns:
            cid = f"{table_name}.{col}"
            index[cid] = {
                "table": table_name,
                "column": col,
                "stats": column_stats(df, col),
            }
    return index


# ═══════════════════════════════════════════════════════════════
#  3. 算法优化：倒排索引 + MinHash/LSH
# ═══════════════════════════════════════════════════════════════

def jaccard(a: set, b: set) -> float:
    if not a and not b:
        return 1.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


def build_inverted_index(tables: Dict[str, pd.DataFrame]) -> Dict[str, List[str]]:
    """列名 → [table_name, ...] 的倒排索引。"""
    idx: Dict[str, List[str]] = defaultdict(list)
    for tname, df in tables.items():
        for col in df.columns:
            idx[col].append(tname)
    return dict(idx)


def detect_column_name_similarity(
    tables: Dict[str, pd.DataFrame],
    col_index: Dict[str, Dict[str, Any]],
    embedder: ColumnEmbedder,
) -> List[Dict]:
    """策略 1：倒排索引 + TF-IDF 语义相似度。"""
    edges = []
    inv = build_inverted_index(tables)

    # 3.1 字面同名列（倒排索引瞬间找出）
    for col, tlist in inv.items():
        if len(tlist) < 2:
            continue
        for i in range(len(tlist)):
            for j in range(i + 1, len(tlist)):
                t1, t2 = tlist[i], tlist[j]
                edges.append(
                    {
                        "source": f"{t1}.{col}",
                        "target": f"{t2}.{col}",
                        "type": "same_column_name",
                        "confidence": 1.0,
                        "detail": f"同名列 '{col}'",
                    }
                )
        # 表级别边
        edges.append(
            {
                "source": tlist[0],
                "target": tlist[1],
                "type": "column_name_overlap",
                "confidence": round(len(tlist) / len(tables), 3),
                "detail": f"共同列: ['{col}']",
                "common_columns": [col],
            }
        )

    # 3.2 语义相似列名（TF-IDF 余弦相似度）
    # 建立 column_name -> [cid, ...] 映射
    colname_to_cids: Dict[str, List[str]] = defaultdict(list)
    for cid, info in col_index.items():
        colname_to_cids[info["column"]].append(cid)

    checked = set()
    for c1, info1 in col_index.items():
        sims = embedder.batch_similarity(info1["column"])
        for col2_name, score in sims.items():
            if score < 0.5:
                continue
            if info1["column"] == col2_name:
                continue  # 字面同名已在上面处理
            for c2 in colname_to_cids.get(col2_name, []):
                info2 = col_index[c2]
                if info1["table"] == info2["table"]:
                    continue
                pair = tuple(sorted([c1, c2]))
                if pair in checked:
                    continue
                checked.add(pair)
                edges.append(
                    {
                        "source": c1,
                        "target": c2,
                        "type": "semantic_column_name",
                        "confidence": round(score, 3),
                        "detail": (
                            f"列名语义相似 '{info1['column']}' ↔ "
                            f"'{info2['column']}' (余弦相似度 {score:.2f})"
                        ),
                    }
                )

    return edges


def build_minhash_signatures(col_index: Dict[str, Dict[str, Any]]) -> Dict[str, List[int]]:
    """为所有列生成 MinHash 签名。"""
    sigs = {}
    for cid, info in col_index.items():
        vals = info["stats"]["sample_uniques"]
        sigs[cid] = minhash_engine.compute(vals)
    return sigs


def detect_content_overlap_lsh(
    tables: Dict[str, pd.DataFrame],
    col_index: Dict[str, Dict[str, Any]],
) -> List[Dict]:
    """策略 2：MinHash+LSH 优化数据内容重叠检测。"""
    edges = []
    sigs = build_minhash_signatures(col_index)
    candidates = lsh_engine.candidate_pairs(sigs)

    for c1, c2 in candidates:
        info1, info2 = col_index[c1], col_index[c2]
        # 跳过同表
        if info1["table"] == info2["table"]:
            continue
        s1, s2 = info1["stats"], info2["stats"]
        # 类型必须一致
        if s1["dtype"] != s2["dtype"]:
            continue

        overlap = jaccard(s1["sample_uniques"], s2["sample_uniques"])
        if overlap >= 0.3:
            edges.append(
                {
                    "source": c1,
                    "target": c2,
                    "type": "content_overlap",
                    "confidence": round(overlap, 3),
                    "detail": f"取值集合 Jaccard 相似度 {overlap:.2%}",
                }
            )

    return edges


def detect_foreign_key_candidates_lsh(
    tables: Dict[str, pd.DataFrame],
    col_index: Dict[str, Dict[str, Any]],
    embedder: ColumnEmbedder,
) -> List[Dict]:
    """策略 3：MinHash+LSH + 剪枝策略优化外键检测。"""
    edges = []
    sigs = build_minhash_signatures(col_index)
    candidates = lsh_engine.candidate_pairs(sigs)

    for c1, c2 in candidates:
        info1, info2 = col_index[c1], col_index[c2]
        if info1["table"] == info2["table"]:
            continue

        s1, s2 = info1["stats"], info2["stats"]
        if s1["dtype"] != s2["dtype"]:
            continue

        # ── 剪枝 1：基数关系 ──
        # 被引用方（target）基数应 >= 引用方（source）
        if s2["cardinality"] < s1["cardinality"]:
            continue

        # ── 剪枝 2：语义类型一致性 ──
        sem1 = s1.get("semantic_type")
        sem2 = s2.get("semantic_type")
        if sem1 and sem2 and sem1 != sem2:
            continue

        # ── 剪枝 3：列名语义相似度过滤 ──
        name_sim = embedder.similarity(info1["column"], info2["column"])
        # 如果列名完全不相关（相似度 < 0.1），且语义类型也不一致，则跳过
        if name_sim < 0.1 and not (sem1 and sem1 == sem2):
            pass  # 仍保留，因为值重叠高也可能有意义

        # ── 精确包含率计算 ──
        t1, col1 = info1["table"], info1["column"]
        t2, col2 = info2["table"], info2["column"]

        # 对于大表，采样计算
        df1 = tables[t1][col1].dropna().astype(str)
        df2 = tables[t2][col2].dropna().astype(str)
        if len(df1) == 0 or len(df2) == 0:
            continue

        # 采样加速
        sample_n1 = min(len(df1), 20_000)
        sample_n2 = min(len(df2), 20_000)
        sample1 = set(df1.sample(sample_n1, random_state=37).unique()) if len(df1) > sample_n1 else set(df1.unique())
        sample2 = set(df2.sample(sample_n2, random_state=37).unique()) if len(df2) > sample_n2 else set(df2.unique())

        contained = sum(1 for v in sample1 if v in sample2)
        ratio = contained / len(sample1) if sample1 else 0.0

        if ratio >= 0.85:
            confidence = min(1.0, ratio * (1 - s1["null_ratio"]))
            edges.append(
                {
                    "source": c1,
                    "target": c2,
                    "type": "foreign_key_candidate",
                    "confidence": round(confidence, 3),
                    "detail": (
                        f"{ratio:.1%} 的 {c1} 值出现在 {c2} 中; "
                        f"基数 {s1['cardinality']} -> {s2['cardinality']}"
                    ),
                    "metrics": {
                        "containment_ratio": round(ratio, 4),
                        "cardinality_source": s1["cardinality"],
                        "cardinality_target": s2["cardinality"],
                    },
                }
            )

    return edges


def detect_composite_keys(
    tables: Dict[str, pd.DataFrame],
    col_index: Dict[str, Dict[str, Any]],
    single_edges: List[Dict],
    embedder: ColumnEmbedder,
) -> List[Dict]:
    """策略 4：复合键探测。

    思路：找到同一对表之间，存在多个高相似度（但未达绝对外键阈值）的单列关联，
    尝试将它们组合后计算联合基数的包含率。
    """
    edges = []
    # 收集表对 -> [列对]
    table_pairs: Dict[Tuple[str, str], List[Tuple[str, str, float]]] = defaultdict(list)

    for e in single_edges:
        if e["type"] not in ("content_overlap", "foreign_key_candidate"):
            continue
        c1, c2 = e["source"], e["target"]
        info1, info2 = col_index.get(c1), col_index.get(c2)
        if not info1 or not info2:
            continue
        t1, t2 = info1["table"], info2["table"]
        if t1 == t2:
            continue
        pair = tuple(sorted([t1, t2]))
        conf = e.get("confidence", 0.0)
        # 只保留置信度在 0.3~0.95 之间的（可能是复合键的一部分）
        if 0.3 <= conf < 0.95:
            table_pairs[pair].append((c1, c2, conf))

    for (t1, t2), col_pairs in table_pairs.items():
        if len(col_pairs) < 2:
            continue

        # 按源列分组，避免同一源列重复组合
        source_cols = defaultdict(list)
        for c1, c2, conf in col_pairs:
            info1 = col_index[c1]
            key = info1["column"]  # 用原始列名做 key
            source_cols[key].append((c1, c2, conf))

        # 尝试所有 2 列组合（控制复杂度）
        all_items = []
        for items in source_cols.values():
            all_items.extend(items)

        if len(all_items) < 2:
            continue

        # 只取 Top-6 进行组合，防止爆炸
        all_items = sorted(all_items, key=lambda x: -x[2])[:6]

        for i in range(len(all_items)):
            for j in range(i + 1, len(all_items)):
                c1a, c2a, _ = all_items[i]
                c1b, c2b, _ = all_items[j]

                # 确保来自不同源列
                if col_index[c1a]["column"] == col_index[c1b]["column"]:
                    continue

                try:
                    # 计算联合包含率
                    df1 = tables[t1]
                    df2 = tables[t2]

                    # 构建联合值（采样）
                    s1a = df1[col_index[c1a]["column"]].astype(str)
                    s1b = df1[col_index[c1b]["column"]].astype(str)
                    s2a = df2[col_index[c2a]["column"]].astype(str)
                    s2b = df2[col_index[c2b]["column"]].astype(str)

                    # 组合字符串 "val_a|val_b"
                    if len(s1a) > 20_000:
                        idx1 = s1a.sample(20_000, random_state=37).index
                    else:
                        idx1 = s1a.index
                    if len(s2a) > 20_000:
                        idx2 = s2a.sample(20_000, random_state=37).index
                    else:
                        idx2 = s2a.index

                    combo1 = set((s1a.loc[idx1] + "|" + s1b.loc[idx1]).dropna())
                    combo2 = set((s2a.loc[idx2] + "|" + s2b.loc[idx2]).dropna())

                    if not combo1 or not combo2:
                        continue

                    contained = sum(1 for v in combo1 if v in combo2)
                    ratio = contained / len(combo1)

                    if ratio >= 0.8:
                        edges.append(
                            {
                                "source": f"{t1}({col_index[c1a]['column']},{col_index[c1b]['column']})",
                                "target": f"{t2}({col_index[c2a]['column']},{col_index[c2b]['column']})",
                                "type": "composite_key_candidate",
                                "confidence": round(ratio, 3),
                                "detail": (
                                    f"复合键包含率 {ratio:.1%}: "
                                    f"{t1}.{col_index[c1a]['column']}+{col_index[c1b]['column']} -> "
                                    f"{t2}.{col_index[c2a]['column']}+{col_index[c2b]['column']}"
                                ),
                            }
                        )
                except Exception:
                    continue

    return edges


def detect_distribution_similarity(
    tables: Dict[str, pd.DataFrame],
    col_index: Dict[str, Dict[str, Any]],
) -> List[Dict]:
    """策略 5：统计分布相似 — 数值列比较均值/标准差/范围。"""
    edges = []
    cids = list(col_index.keys())
    for i in range(len(cids)):
        for j in range(i + 1, len(cids)):
            c1, c2 = cids[i], cids[j]
            info1, info2 = col_index[c1], col_index[c2]
            if info1["table"] == info2["table"]:
                continue

            s1, s2 = info1["stats"], info2["stats"]
            if s1["dtype"] != "numeric" or s2["dtype"] != "numeric":
                continue

            r1 = s1["max"] - s1["min"]
            r2 = s2["max"] - s2["min"]
            if r1 <= 0 or r2 <= 0:
                continue

            inter_min = max(s1["min"], s2["min"])
            inter_max = min(s1["max"], s2["max"])
            inter = max(0, inter_max - inter_min)
            union = max(s1["max"], s2["max"]) - min(s1["min"], s2["min"])
            range_overlap = inter / union if union else 0.0

            pooled_std = max(1e-6, np.sqrt((s1["std"] ** 2 + s2["std"] ** 2) / 2))
            mean_dist = abs(s1["mean"] - s2["mean"]) / pooled_std
            mean_sim = max(0, 1 - mean_dist / 3)

            confidence = 0.5 * range_overlap + 0.5 * mean_sim
            if confidence >= 0.5:
                edges.append(
                    {
                        "source": c1,
                        "target": c2,
                        "type": "distribution_similar",
                        "confidence": round(confidence, 3),
                        "detail": (
                            f"范围重叠 {range_overlap:.1%}, "
                            f"均值距离 {mean_dist:.2f}σ"
                        ),
                        "metrics": {
                            "range_overlap": round(range_overlap, 4),
                            "mean_distance_sigma": round(mean_dist, 4),
                        },
                    }
                )
    return edges


# ═══════════════════════════════════════════════════════════════
#  4. Graph 组装与输出
# ═══════════════════════════════════════════════════════════════

def build_graph(
    tables: Dict[str, pd.DataFrame],
    col_index: Dict[str, Dict[str, Any]],
    edges: List[Dict],
) -> Dict[str, Any]:
    """组装最终的 Graph 描述。"""
    nodes = []
    for tname, df in tables.items():
        nodes.append(
            {
                "id": tname,
                "type": "table",
                "columns": list(df.columns),
                "row_count": len(df),
            }
        )

    for cid, info in col_index.items():
        s = info["stats"]
        node = {
            "id": cid,
            "type": "column",
            "table": info["table"],
            "column": info["column"],
            "dtype": s["dtype"],
            "cardinality": s["cardinality"],
        }
        if "semantic_type" in s:
            node["semantic_type"] = s["semantic_type"]
        nodes.append(node)

    # 去重边（保留最高置信度）
    edge_map = {}
    for e in edges:
        key = (e["source"], e["target"], e["type"])
        rev = (e["target"], e["source"], e["type"])
        if rev in edge_map:
            if e["confidence"] > edge_map[rev]["confidence"]:
                edge_map[rev] = e
        elif key not in edge_map or e["confidence"] > edge_map[key]["confidence"]:
            edge_map[key] = e

    unique_edges = sorted(
        edge_map.values(), key=lambda x: (-x["confidence"], x["source"], x["target"])
    )

    type_counts = defaultdict(int)
    for e in unique_edges:
        type_counts[e["type"]] += 1

    return {
        "meta": {
            "tables": len(tables),
            "columns": len(col_index),
            "associations": len(unique_edges),
        },
        "nodes": nodes,
        "edges": unique_edges,
        "summary": {
            "association_types": dict(type_counts),
            "top_confidence": round(unique_edges[0]["confidence"], 3) if unique_edges else 0,
        },
    }


# ═══════════════════════════════════════════════════════════════
#  5. 主入口
# ═══════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="多表格关联发现原型（优化版）")
    parser.add_argument("--dir", type=Path, default=Path("csv-data"), help="数据目录")
    parser.add_argument("--output", type=Path, default=None, help="输出 JSON 文件路径")
    parser.add_argument("--pretty", action="store_true", default=True, help="美化输出")
    parser.add_argument(
        "--max-rows",
        type=int,
        default=DEFAULT_MAX_ROWS,
        help=f"单表最大读取行数（默认 {DEFAULT_MAX_ROWS}）",
    )
    args = parser.parse_args()

    if not args.dir.exists():
        print(f"[ERROR] 目录不存在: {args.dir}", file=sys.stderr)
        sys.exit(1)

    tables = load_tables(args.dir, max_rows=args.max_rows)
    if not tables:
        print(f"[WARN] 目录中未找到可解析的 CSV/Excel 文件: {args.dir}", file=sys.stderr)
        sys.exit(0)

    print(f"[INFO] 加载 {len(tables)} 张表 ...")
    col_index = build_column_index(tables)
    print(f"[INFO] 共 {len(col_index)} 列，构建语义嵌入 ...")

    # 初始化列名嵌入器
    all_col_names = [info["column"] for info in col_index.values()]
    embedder = ColumnEmbedder()
    embedder.fit(all_col_names)

    edges = []

    print("[INFO] 检测列名相似度（倒排索引 + TF-IDF 语义） ...")
    edges += detect_column_name_similarity(tables, col_index, embedder)

    print("[INFO] 检测数据内容重叠（MinHash + LSH） ...")
    edges += detect_content_overlap_lsh(tables, col_index)

    print("[INFO] 检测疑似外键（MinHash + LSH + 剪枝） ...")
    edges += detect_foreign_key_candidates_lsh(tables, col_index, embedder)

    print("[INFO] 检测统计分布相似 ...")
    edges += detect_distribution_similarity(tables, col_index)

    print("[INFO] 探测复合键 ...")
    edges += detect_composite_keys(tables, col_index, edges, embedder)

    graph = build_graph(tables, col_index, edges)

    indent = 2 if args.pretty else None
    out_json = json.dumps(graph, indent=indent, ensure_ascii=False, default=str)

    if args.output:
        args.output.write_text(out_json, encoding="utf-8")
        print(f"[INFO] 报告已保存至: {args.output}")
    else:
        print(out_json)


if __name__ == "__main__":
    main()
