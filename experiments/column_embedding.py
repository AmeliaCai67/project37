"""
列名语义嵌入模块（Column Embedding）

使用 scikit-learn 的 TF-IDF（char n-gram）为列名生成轻量级语义向量，
从而识别 cust_no ↔ client_id 这类字面不同但语义相近的列名对。

本地无外部模型依赖，所有计算在内存中完成。
"""

from typing import Dict, List
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


class ColumnEmbedder:
    """基于字符级 TF-IDF 的列名语义嵌入器。"""

    def __init__(self, ngram_range=(2, 4), min_df=1):
        self.vectorizer = TfidfVectorizer(
            analyzer="char",
            ngram_range=ngram_range,
            lowercase=True,
            min_df=min_df,
        )
        self.names: List[str] = []
        self.vectors: np.ndarray = None
        self._name_to_idx: Dict[str, int] = {}

    def fit(self, column_names: List[str]):
        """拟合所有列名。"""
        self.names = list(dict.fromkeys(column_names))  # 去重保序
        self._name_to_idx = {n: i for i, n in enumerate(self.names)}
        if len(self.names) <= 1:
            self.vectors = np.zeros((len(self.names), 1))
            return
        self.vectors = self.vectorizer.fit_transform(self.names).toarray()
        # 清理 NaN/Inf，避免 cosine_similarity 出现除零警告
        self.vectors = np.nan_to_num(self.vectors, nan=0.0, posinf=0.0, neginf=0.0)

    def similarity(self, name_a: str, name_b: str) -> float:
        """计算两个列名的余弦语义相似度（范围 0~1）。"""
        if not hasattr(self.vectorizer, "vocabulary_") or self.vectors is None:
            return 0.0
        try:
            va = self.vectorizer.transform([name_a]).toarray()
            vb = self.vectorizer.transform([name_b]).toarray()
            if np.linalg.norm(va) == 0 or np.linalg.norm(vb) == 0:
                return 0.0
            with np.errstate(invalid='ignore', divide='ignore'):
                return float(cosine_similarity(va, vb)[0, 0])
        except Exception:
            return 0.0

    def batch_similarity(self, query_name: str) -> Dict[str, float]:
        """计算 query_name 与所有已知列名的相似度，返回 {name: score}。"""
        if self.vectors is None or len(self.vectors) == 0:
            return {}
        try:
            vq = self.vectorizer.transform([query_name]).toarray()
            if np.linalg.norm(vq) == 0:
                return {}
            with np.errstate(invalid='ignore', divide='ignore'):
                sims = cosine_similarity(vq, self.vectors)[0]
            return {n: float(s) for n, s in zip(self.names, sims)}
        except Exception:
            return {}

    def top_k(self, query_name: str, k: int = 5, threshold: float = 0.3) -> List[tuple]:
        """返回与 query_name 最相似的 Top-K 列名。"""
        sims = self.batch_similarity(query_name)
        sorted_items = sorted(sims.items(), key=lambda x: -x[1])
        return [(n, s) for n, s in sorted_items[:k] if s >= threshold]
