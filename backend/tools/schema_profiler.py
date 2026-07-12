"""
Schema Profiler — 多表格关联分析与元数据图谱构建

整合 experiments/ 原型脚本核心算法，生产化封装：
  - 鲁棒 CSV/Excel 读取（编码/分隔符嗅探、大表采样）
  - MinHash + LSH 加速列内容相似度
  - TF-IDF 列名语义相似度
  - 语义类型打标
  - 5 种关联检测策略（同名列、内容重叠、外键候选、分布相似、复合键）
  - Graph 组装与本地 JSON 缓存

约束：
  - 纯后端逻辑，无前端耦合
  - 文件大小阈值保护，严禁无限制加载
  - 生成的图谱作为内部缓存，不暴露独立下载 API
"""

import csv
import json
import random
import sys
from pathlib import Path
from collections import defaultdict
from typing import Any, Dict, List, Optional, Set, Tuple

import pandas as pd
import numpy as np
import chardet

# ═══════════════════════════════════════════════════════════════
#  0. 配置常量（文件体积阈值与采样策略）
# ═══════════════════════════════════════════════════════════════

DEFAULT_MAX_ROWS = 200_000          # 单表默认最大读取行数
DEFAULT_SAMPLE_SIZE = 5_000         # 列统计采样数
MINHASH_PERM = 128
LSH_BANDS = 16

# 文件大小阈值策略（字节 -> 最大读取行数）
FILE_SIZE_THRESHOLDS: List[Tuple[int, int]] = [
    (10 * 1024 * 1024, 200_000),   # <= 10MB: 最多 20 万行
    (50 * 1024 * 1024, 50_000),    # <= 50MB: 最多 5 万行
    (100 * 1024 * 1024, 20_000),   # <= 100MB: 最多 2 万行
    (500 * 1024 * 1024, 20_000),   # <= 500MB: 最多 2 万行
]
DEFAULT_LARGE_FILE_ROWS = 10_000    # 超过最大阈值时，读 1 万行

CACHE_FILENAME = "schema_graph.json"

# 列名黑名单：pandas 自动生成的无意义列，读取时直接过滤
COLUMN_BLACKLIST = {
    "unnamed: 0", "unnamed: 1", "unnamed: 2", "unnamed: 3",
    "index", "level_0", "level_1", "level_2",
}


def _filter_blacklist_columns(df: pd.DataFrame) -> pd.DataFrame:
    """过滤掉 pandas 自动生成的无意义列（如 Unnamed: 0、index 等）。"""
    if df.empty:
        return df
    to_drop = [c for c in df.columns if str(c).strip().lower() in COLUMN_BLACKLIST]
    if to_drop:
        df = df.drop(columns=to_drop)
    return df


# ═══════════════════════════════════════════════════════════════
#  1. 鲁棒性加载与编码容错
# ═══════════════════════════════════════════════════════════════

def _get_max_rows_by_size(file_size_bytes: int) -> int:
    """根据文件体积返回安全读取行数上限。"""
    for threshold, max_rows in FILE_SIZE_THRESHOLDS:
        if file_size_bytes <= threshold:
            return max_rows
    return DEFAULT_LARGE_FILE_ROWS


def _sniff_encoding(filepath: Path) -> str:
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


def _sniff_delimiter(filepath: Path, encoding: str) -> str:
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
    encoding = _sniff_encoding(filepath)
    delimiter = _sniff_delimiter(filepath, encoding)

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
            return _filter_blacklist_columns(df)
        except Exception:
            continue

    return None


def read_excel_robust(filepath: Path, max_rows: int = DEFAULT_MAX_ROWS) -> Optional[pd.DataFrame]:
    """鲁棒的 Excel 读取，限制行数。"""
    try:
        df = pd.read_excel(filepath, dtype=str, keep_default_na=True, nrows=max_rows)
        return _filter_blacklist_columns(df)
    except Exception:
        return None


def load_tables(dir_path: Path) -> Dict[str, pd.DataFrame]:
    """加载目录下所有 CSV / Excel 文件，自动根据文件大小决定采样行数。

    跳过 ``37-output`` 产物目录与 ``.cache`` 缓存目录，避免把内部文件当作源数据画像。
    """
    tables: Dict[str, pd.DataFrame] = {}
    if not dir_path.exists():
        return tables

    for p in sorted(dir_path.iterdir()):
        if p.name in ("37-output", ".cache"):
            continue
        if not p.is_file():
            continue

        file_size = p.stat().st_size
        max_rows = _get_max_rows_by_size(file_size)

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
#  2. MinHash + LSH
# ═══════════════════════════════════════════════════════════════

class MinHash:
    """MinHash 签名生成器。"""

    def __init__(self, num_perm: int = MINHASH_PERM, seed: int = 37):
        self.num_perm = num_perm
        self.seed = seed
        random.seed(seed)
        self.p = 2147483647
        self.perms = [
            (random.randint(1, self.p - 1), random.randint(0, self.p - 1))
            for _ in range(num_perm)
        ]

    def compute(self, values: Set[str]) -> List[int]:
        if not values:
            return [self.p] * self.num_perm
        sig = [self.p] * self.num_perm
        for val in values:
            base = (hash(val) & 0x7FFFFFFF) % self.p
            for i, (a, b) in enumerate(self.perms):
                h = ((a * base + b) % self.p) & 0x7FFFFFFF
                if h < sig[i]:
                    sig[i] = h
        return sig


class LSH:
    """基于 MinHash 签名的局部敏感哈希分桶器。"""

    def __init__(self, num_perm: int = MINHASH_PERM, num_bands: int = LSH_BANDS):
        self.num_perm = num_perm
        self.num_bands = num_bands
        self.rows_per_band = num_perm // num_bands

    def _band_key(self, signature: List[int], band_idx: int) -> str:
        import hashlib
        start = band_idx * self.rows_per_band
        end = start + self.rows_per_band
        return hashlib.md5(str(signature[start:end]).encode()).hexdigest()[:16]

    def candidate_pairs(self, sig_map: Dict[str, List[int]]) -> Set[Tuple[str, str]]:
        buckets: Dict[str, List[str]] = {}
        for col_id, sig in sig_map.items():
            for band_idx in range(self.num_bands):
                key = f"b{band_idx}:{self._band_key(sig, band_idx)}"
                buckets.setdefault(key, []).append(col_id)

        pairs: Set[Tuple[str, str]] = set()
        for members in buckets.values():
            if len(members) < 2:
                continue
            members = sorted(members)
            for i in range(len(members)):
                for j in range(i + 1, len(members)):
                    a, b = members[i], members[j]
                    pairs.add((a, b) if a < b else (b, a))
        return pairs


# ═══════════════════════════════════════════════════════════════
#  3. 语义类型打标
# ═══════════════════════════════════════════════════════════════

class SemanticTyper:
    """轻量级语义类型识别器。"""

    PATTERNS = {
        "email": __import__("re").compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"),
        "ip_address": __import__("re").compile(r"^(\d{1,3}\.){3}\d{1,3}$"),
        "phone_number": __import__("re").compile(r"^(\+?\d{1,3}[-.\s]?)?\(?\d{2,4}\)?[-.\s]?\d{3,4}[-.\s]?\d{3,4}$"),
        "url": __import__("re").compile(r"^https?://[^\s/$.?#].[^\s]*$", __import__("re").IGNORECASE),
        "uuid": __import__("re").compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", __import__("re").IGNORECASE),
        "id_card_cn": __import__("re").compile(r"^\d{17}[\dXx]$"),
        "latitude_longitude": __import__("re").compile(r"^-?\d{1,3}\.\d+[,\s]+-?\d{1,3}\.\d+$"),
        "date_iso": __import__("re").compile(r"^\d{4}-\d{2}-\d{2}$"),
        "datetime_iso": __import__("re").compile(r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}"),
        "hex_color": __import__("re").compile(r"^#([0-9a-fA-F]{3}){1,2}$"),
        "mac_address": __import__("re").compile(r"^([0-9a-fA-F]{2}[:-]){5}[0-9a-fA-F]{2}$"),
    }

    COLUMN_KEYWORDS = {
        "email": ["email", "e_mail", "mail", "邮箱"],
        "phone_number": ["phone", "tel", "mobile", "电话", "手机"],
        "ip_address": ["ip", "ip_addr", "ip_address"],
        "url": ["url", "link", "website", "网址", "链接"],
        "uuid": ["uuid", "guid", "id"],
        "id_card_cn": ["idcard", "身份证", "id_no", "id_number"],
        "latitude_longitude": ["lat", "lng", "lon", "latitude", "longitude", "经纬度", "坐标"],
        "date_iso": ["date", "日期", "day"],
        "datetime_iso": ["datetime", "timestamp", "时间戳", "时间"],
        "hex_color": ["color", "颜色", "bg", "background"],
        "mac_address": ["mac", "mac_address"],
    }

    def infer_from_values(self, sample_values: list) -> Optional[str]:
        if not sample_values:
            return None
        scores = {}
        n = len(sample_values)
        for type_name, pattern in self.PATTERNS.items():
            matched = sum(1 for v in sample_values if pattern.match(str(v)))
            if matched > 0:
                scores[type_name] = matched / n
        if not scores:
            return None
        best = max(scores, key=scores.get)
        return best if scores[best] >= 0.7 else None

    def infer_from_column_name(self, col_name: str) -> Optional[str]:
        col_lower = col_name.lower()
        for sem_type, keywords in self.COLUMN_KEYWORDS.items():
            for kw in keywords:
                if kw in col_lower:
                    return sem_type
        return None

    def infer(self, sample_values: list, col_name: str) -> Optional[str]:
        val_type = self.infer_from_values(sample_values)
        if val_type:
            return val_type
        return self.infer_from_column_name(col_name)


# ═══════════════════════════════════════════════════════════════
#  4. 列名语义嵌入
# ═══════════════════════════════════════════════════════════════

class ColumnEmbedder:
    """基于字符级 TF-IDF 的列名语义嵌入器。"""

    def __init__(self, ngram_range=(2, 4), min_df=1):
        from sklearn.feature_extraction.text import TfidfVectorizer
        self.vectorizer = TfidfVectorizer(
            analyzer="char",
            ngram_range=ngram_range,
            lowercase=True,
            min_df=min_df,
        )
        self.names: List[str] = []
        self.vectors = None
        self._name_to_idx: Dict[str, int] = {}

    def fit(self, column_names: List[str]):
        self.names = list(dict.fromkeys(column_names))
        self._name_to_idx = {n: i for i, n in enumerate(self.names)}
        if len(self.names) <= 1:
            self.vectors = np.zeros((len(self.names), 1))
            return
        self.vectors = self.vectorizer.fit_transform(self.names).toarray()
        self.vectors = np.nan_to_num(self.vectors, nan=0.0, posinf=0.0, neginf=0.0)
        # 进一步裁剪极端值以避免 sklearn matmul overflow
        self.vectors = np.clip(self.vectors, -1e6, 1e6)

    def similarity(self, name_a: str, name_b: str) -> float:
        if not hasattr(self.vectorizer, "vocabulary_") or self.vectors is None:
            return 0.0
        try:
            from sklearn.metrics.pairwise import cosine_similarity
            va = self.vectorizer.transform([name_a]).toarray()
            vb = self.vectorizer.transform([name_b]).toarray()
            if np.linalg.norm(va) == 0 or np.linalg.norm(vb) == 0:
                return 0.0
            with np.errstate(invalid="ignore", divide="ignore"):
                return float(cosine_similarity(va, vb)[0, 0])
        except Exception:
            return 0.0

    def batch_similarity(self, query_name: str) -> Dict[str, float]:
        if self.vectors is None or len(self.vectors) == 0:
            return {}
        try:
            from sklearn.metrics.pairwise import cosine_similarity
            vq = self.vectorizer.transform([query_name]).toarray()
            if np.linalg.norm(vq) == 0:
                return {}
            with np.errstate(invalid="ignore", divide="ignore"):
                sims = cosine_similarity(vq, self.vectors)[0]
            return {n: float(s) for n, s in zip(self.names, sims)}
        except Exception:
            return {}


# ═══════════════════════════════════════════════════════════════
#  5. 增强型列统计与索引构建
# ═══════════════════════════════════════════════════════════════

def _detect_datetime(series: pd.Series) -> bool:
    s = series.dropna().astype(str).head(200)
    if len(s) == 0:
        return False
    try:
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            dt = pd.to_datetime(s, errors="coerce")
        return dt.notna().sum() / len(s) > 0.75
    except Exception:
        return False


def _detect_boolean(series: pd.Series) -> bool:
    bool_vals = {"true", "false", "1", "0", "yes", "no", "t", "f", "y", "n", "on", "off"}
    s = series.dropna().astype(str).str.lower().head(200)
    if len(s) == 0:
        return False
    return s.isin(bool_vals).sum() / len(s) > 0.9


def column_stats(
    df: pd.DataFrame,
    col: str,
    sample_size: int = DEFAULT_SAMPLE_SIZE,
    semantic_typer: Optional[SemanticTyper] = None,
) -> Dict[str, Any]:
    """计算单列统计指纹（增强版）。"""
    s = df[col]
    total = len(s)

    if total > sample_size:
        s_sample = s.sample(sample_size, random_state=37)
    else:
        s_sample = s

    uniques = s_sample.dropna().unique()
    cardinality = len(uniques)
    null_ratio = s.isna().sum() / total if total else 0.0

    dtype = "string"
    numeric = pd.to_numeric(s_sample, errors="coerce")
    is_numeric = numeric.notna().sum() / max(len(s_sample), 1) > 0.8

    if is_numeric:
        dtype = "numeric"
    elif _detect_datetime(s_sample):
        dtype = "datetime"
    elif _detect_boolean(s_sample):
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
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            dt = pd.to_datetime(s_sample, errors="coerce")
        stats["min"] = str(dt.min())
        stats["max"] = str(dt.max())
        stats["count"] = int(dt.notna().sum())
    elif dtype == "boolean":
        bool_vals = {"true", "1", "yes", "t", "y", "on"}
        mapped = s_sample.dropna().astype(str).str.lower().isin(bool_vals)
        stats["true_ratio"] = float(mapped.mean())
    else:
        lengths = s_sample.dropna().astype(str).str.len()
        stats["avg_len"] = float(lengths.mean()) if len(lengths) else 0.0
        stats["max_len"] = int(lengths.max()) if len(lengths) else 0

    if semantic_typer:
        sample_for_semantic = uniques[: min(100, cardinality)]
        sem_type = semantic_typer.infer(sample_for_semantic.tolist(), col)
        if sem_type:
            stats["semantic_type"] = sem_type

    return stats


def build_column_index(
    tables: Dict[str, pd.DataFrame],
    semantic_typer: Optional[SemanticTyper] = None,
) -> Dict[str, Dict[str, Any]]:
    """为每个表-列构建统计指纹索引。"""
    index = {}
    for table_name, df in tables.items():
        for col in df.columns:
            cid = f"{table_name}.{col}"
            index[cid] = {
                "table": table_name,
                "column": col,
                "stats": column_stats(df, col, semantic_typer=semantic_typer),
            }
    return index


# ═══════════════════════════════════════════════════════════════
#  6. 关联检测策略
# ═══════════════════════════════════════════════════════════════

def _jaccard(a: set, b: set) -> float:
    if not a and not b:
        return 1.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


def _mirror_table_pairs(tables: Dict[str, pd.DataFrame], threshold: float = 0.8) -> Set[Tuple[str, str]]:
    """
    识别镜像表对（列名重合度 >= threshold 的表对）。
    镜像表通常产生大量无意义的内容重叠边（如 train/test 分割）。
    """
    pairs: Set[Tuple[str, str]] = set()
    tnames = list(tables.keys())
    for i in range(len(tnames)):
        for j in range(i + 1, len(tnames)):
            t1, t2 = tnames[i], tnames[j]
            cols1 = set(tables[t1].columns)
            cols2 = set(tables[t2].columns)
            if not cols1 or not cols2:
                continue
            overlap = len(cols1 & cols2) / len(cols1 | cols2)
            if overlap >= threshold:
                pairs.add((t1, t2) if t1 < t2 else (t2, t1))
    return pairs


def detect_column_name_similarity(
    tables: Dict[str, pd.DataFrame],
    col_index: Dict[str, Dict[str, Any]],
    embedder: ColumnEmbedder,
) -> List[Dict]:
    """策略 1：倒排索引 + TF-IDF 语义相似度。"""
    edges = []
    inv: Dict[str, List[str]] = defaultdict(list)
    for tname, df in tables.items():
        for col in df.columns:
            inv[col].append(tname)

    # 字面同名列
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
        # 表级别边（仅取前两张表避免重复）
        if len(tlist) >= 2:
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

    # 语义相似列名
    colname_to_cids: Dict[str, List[str]] = defaultdict(list)
    for cid, info in col_index.items():
        colname_to_cids[info["column"]].append(cid)

    checked = set()
    for c1, info1 in col_index.items():
        sims = embedder.batch_similarity(info1["column"])
        for col2_name, score in sims.items():
            if score < 0.5 or info1["column"] == col2_name:
                continue
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


def detect_content_overlap_lsh(
    tables: Dict[str, pd.DataFrame],
    col_index: Dict[str, Dict[str, Any]],
    minhash: MinHash,
    lsh: LSH,
    mirror_pairs: Optional[Set[Tuple[str, str]]] = None,
) -> List[Dict]:
    """策略 2：MinHash+LSH 优化数据内容重叠检测。"""
    edges = []
    mirror_pairs = mirror_pairs or set()
    sigs = {}
    for cid, info in col_index.items():
        vals = info["stats"]["sample_uniques"]
        sigs[cid] = minhash.compute(vals)

    candidates = lsh.candidate_pairs(sigs)
    for c1, c2 in candidates:
        info1, info2 = col_index[c1], col_index[c2]
        if info1["table"] == info2["table"]:
            continue
        s1, s2 = info1["stats"], info2["stats"]
        if s1["dtype"] != s2["dtype"]:
            continue

        # 低基数过滤器：两列 cardinality 都 < 5 时，跳过内容重叠策略
        # 低基数枚举值（如 0/1/2）只能靠列名语义匹配，不能靠内容重叠度
        if s1["cardinality"] < 5 and s2["cardinality"] < 5:
            continue

        overlap = _jaccard(s1["sample_uniques"], s2["sample_uniques"])
        if overlap >= 0.3:
            confidence = overlap
            # 镜像表折扣：同构表（如 train/test）之间的内容重叠边可信度大幅降低
            pair = tuple(sorted([info1["table"], info2["table"]]))
            if pair in mirror_pairs:
                confidence *= 0.3
            edges.append(
                {
                    "source": c1,
                    "target": c2,
                    "type": "content_overlap",
                    "confidence": round(confidence, 3),
                    "detail": f"取值集合 Jaccard 相似度 {overlap:.2%}",
                }
            )

    return edges


def detect_foreign_key_candidates_lsh(
    tables: Dict[str, pd.DataFrame],
    col_index: Dict[str, Dict[str, Any]],
    embedder: ColumnEmbedder,
    minhash: MinHash,
    lsh: LSH,
    mirror_pairs: Optional[Set[Tuple[str, str]]] = None,
) -> List[Dict]:
    """策略 3：MinHash+LSH + 剪枝策略优化外键检测。"""
    edges = []
    mirror_pairs = mirror_pairs or set()
    sigs = {}
    for cid, info in col_index.items():
        vals = info["stats"]["sample_uniques"]
        sigs[cid] = minhash.compute(vals)

    candidates = lsh.candidate_pairs(sigs)
    for c1, c2 in candidates:
        info1, info2 = col_index[c1], col_index[c2]
        if info1["table"] == info2["table"]:
            continue

        s1, s2 = info1["stats"], info2["stats"]
        if s1["dtype"] != s2["dtype"]:
            continue

        # 低基数过滤器：两列 cardinality 都 < 5 时，跳过外键候选策略
        # 低基数枚举值（如 0/1/2）只能靠列名语义匹配，不能靠内容重叠度
        if s1["cardinality"] < 5 and s2["cardinality"] < 5:
            continue

        # 剪枝 1：基数关系（被引用方 >= 引用方）
        if s2["cardinality"] < s1["cardinality"]:
            continue

        # 剪枝 2：语义类型一致性
        sem1 = s1.get("semantic_type")
        sem2 = s2.get("semantic_type")
        if sem1 and sem2 and sem1 != sem2:
            continue

        # ── 剪枝 3：列名语义相似度过滤 ──
        name_sim = embedder.similarity(info1["column"], info2["column"])
        # 如果列名完全不相关（相似度 < 0.1），且语义类型也不一致，则跳过
        if name_sim < 0.1 and not (sem1 and sem1 == sem2):
            pass  # 仍保留，因为值重叠高也可能有意义

        # 精确包含率计算（采样加速）
        t1, col1 = info1["table"], info1["column"]
        t2, col2 = info2["table"], info2["column"]
        df1 = tables[t1][col1].dropna().astype(str)
        df2 = tables[t2][col2].dropna().astype(str)
        if len(df1) == 0 or len(df2) == 0:
            continue

        sample_n1 = min(len(df1), 20_000)
        sample_n2 = min(len(df2), 20_000)
        sample1 = set(df1.sample(sample_n1, random_state=37).unique()) if len(df1) > sample_n1 else set(df1.unique())
        sample2 = set(df2.sample(sample_n2, random_state=37).unique()) if len(df2) > sample_n2 else set(df2.unique())

        contained = sum(1 for v in sample1 if v in sample2)
        ratio = contained / len(sample1) if sample1 else 0.0

        if ratio >= 0.85:
            confidence = min(1.0, ratio * (1 - s1["null_ratio"]))

            # 包含率合理性检查：
            # 当 source cardinality 远小于 target cardinality（< 10%）且包含率接近 100%，
            # 但列名语义完全不相关时，极可能是小样本巧合产生的假阳性，需要大幅打折。
            cardinality_ratio = s1["cardinality"] / max(s2["cardinality"], 1)
            if ratio >= 0.99 and cardinality_ratio < 0.1 and name_sim < 0.3:
                confidence *= 0.3

            # 镜像表折扣：同构表（如 train/test）之间的外键边可信度大幅降低
            pair = tuple(sorted([t1, t2]))
            if pair in mirror_pairs:
                confidence *= 0.3

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


def detect_distribution_similarity(
    col_index: Dict[str, Dict[str, Any]],
) -> List[Dict]:
    """策略 4：统计分布相似 — 数值列比较均值/标准差/范围。"""
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
                        "detail": f"范围重叠 {range_overlap:.1%}, 均值距离 {mean_dist:.2f}σ",
                        "metrics": {
                            "range_overlap": round(range_overlap, 4),
                            "mean_distance_sigma": round(mean_dist, 4),
                        },
                    }
                )
    return edges


def detect_composite_keys(
    tables: Dict[str, pd.DataFrame],
    col_index: Dict[str, Dict[str, Any]],
    single_edges: List[Dict],
) -> List[Dict]:
    """策略 5：复合键探测。"""
    edges = []
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
        if 0.3 <= conf < 0.95:
            table_pairs[pair].append((c1, c2, conf))

    for (t1, t2), col_pairs in table_pairs.items():
        if len(col_pairs) < 2:
            continue

        source_cols = defaultdict(list)
        for c1, c2, conf in col_pairs:
            info1 = col_index[c1]
            key = info1["column"]
            source_cols[key].append((c1, c2, conf))

        all_items = []
        for items in source_cols.values():
            all_items.extend(items)

        if len(all_items) < 2:
            continue

        all_items = sorted(all_items, key=lambda x: -x[2])[:6]

        for i in range(len(all_items)):
            for j in range(i + 1, len(all_items)):
                c1a, c2a, _ = all_items[i]
                c1b, c2b, _ = all_items[j]

                if col_index[c1a]["column"] == col_index[c1b]["column"]:
                    continue

                try:
                    df1 = tables[t1]
                    df2 = tables[t2]

                    s1a = df1[col_index[c1a]["column"]].astype(str)
                    s1b = df1[col_index[c1b]["column"]].astype(str)
                    s2a = df2[col_index[c2a]["column"]].astype(str)
                    s2b = df2[col_index[c2b]["column"]].astype(str)

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


# ═══════════════════════════════════════════════════════════════
#  7. Graph 组装与缓存
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
#  8. 对外接口：SchemaProfiler
# ═══════════════════════════════════════════════════════════════

class SchemaProfiler:
    """Schema Profiler 主类：封装图谱构建与轻量化缓存逻辑。"""

    def __init__(
        self,
        minhash_perm: int = MINHASH_PERM,
        lsh_bands: int = LSH_BANDS,
        sample_size: int = DEFAULT_SAMPLE_SIZE,
    ):
        self.minhash = MinHash(num_perm=minhash_perm, seed=37)
        self.lsh = LSH(num_perm=minhash_perm, num_bands=lsh_bands)
        self.semantic_typer = SemanticTyper()
        self.sample_size = sample_size

    def build(self, dir_path: Path) -> Dict[str, Any]:
        """
        构建指定目录下所有表格的关联图谱。

        Args:
            dir_path: 包含 CSV/XLSX 文件的目录

        Returns:
            Graph JSON dict，结构为 {meta, nodes, edges, summary}
        """
        tables = load_tables(dir_path)
        if not tables:
            return {
                "meta": {"tables": 0, "columns": 0, "associations": 0},
                "nodes": [],
                "edges": [],
                "summary": {"association_types": {}, "top_confidence": 0},
            }

        col_index = build_column_index(tables, semantic_typer=self.semantic_typer)
        all_col_names = [info["column"] for info in col_index.values()]
        embedder = ColumnEmbedder()
        embedder.fit(all_col_names)

        # 识别镜像表对（列名重合度 >= 80%），用于后续去重
        mirror_pairs = _mirror_table_pairs(tables)

        edges = []
        edges += detect_column_name_similarity(tables, col_index, embedder)
        edges += detect_content_overlap_lsh(tables, col_index, self.minhash, self.lsh, mirror_pairs)
        edges += detect_foreign_key_candidates_lsh(tables, col_index, embedder, self.minhash, self.lsh, mirror_pairs)
        edges += detect_distribution_similarity(col_index)
        edges += detect_composite_keys(tables, col_index, edges)

        graph = build_graph(tables, col_index, edges)
        return graph

    def build_and_cache(self, dir_path: Path, cache_path: Optional[Path] = None) -> Dict[str, Any]:
        """
        构建图谱并缓存到本地 JSON 文件。

        Args:
            dir_path: 数据文件目录
            cache_path: 缓存文件路径，默认 dir_path/.cache/schema_graph.json

        Returns:
            Graph JSON dict
        """
        graph = self.build(dir_path)
        if cache_path is None:
            cache_path = dir_path / ".cache" / CACHE_FILENAME
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(
            json.dumps(graph, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )
        return graph

    @staticmethod
    def load_cache(dir_path: Path) -> Optional[Dict[str, Any]]:
        """加载缓存的图谱（若存在）。"""
        cache_path = dir_path / ".cache" / CACHE_FILENAME
        if cache_path.exists():
            try:
                return json.loads(cache_path.read_text(encoding="utf-8"))
            except Exception:
                return None
        return None


# ═══════════════════════════════════════════════════════════════
#  9. 便捷的异步触发入口（供 BackgroundTasks 调用）
# ═══════════════════════════════════════════════════════════════

def run_schema_profiler_in_background(user_dir: Path) -> None:
    """
    后台静默运行 Schema Profiler。
    供 FastAPI BackgroundTasks 调用，不阻塞主流程。
    缓存写入 user_dir/.cache/schema_graph.json，避免污染源目录。
    """
    try:
        profiler = SchemaProfiler()
        profiler.build_and_cache(user_dir)
    except Exception:
        # 静默失败，不影响主流程
        pass


def get_schema_summary_for_agent(dir_path: Path) -> Optional[Dict[str, Any]]:
    """
    为 Agent 工具提供提炼后的图谱摘要。
    读取缓存，仅返回 summary 和 edges 的精简版。

    Returns:
        {"summary": ..., "edges": [...]} 或 None
    """
    cache = SchemaProfiler.load_cache(dir_path)
    if not cache:
        return None

    # 只保留高置信度边（>= 0.5），并精简字段
    high_conf_edges = [
        {
            "source": e["source"],
            "target": e["target"],
            "type": e["type"],
            "confidence": e["confidence"],
            "detail": e.get("detail", ""),
        }
        for e in cache.get("edges", [])
        if e.get("confidence", 0) >= 0.5
    ]

    # 按置信度降序
    high_conf_edges.sort(key=lambda x: -x["confidence"])

    return {
        "summary": cache.get("summary", {}),
        "meta": cache.get("meta", {}),
        "edges": high_conf_edges[:50],  # 最多 50 条，避免上下文爆炸
    }
