"""
MinHash + LSH（局部敏感哈希）模块

用于将高维的列取值集合快速分桶，将 O(N²) 的暴力比对降为接近 O(N)。
"""

import hashlib
import random
from typing import Dict, List, Set, Tuple


class MinHash:
    """MinHash 签名生成器。"""

    def __init__(self, num_perm: int = 128, seed: int = 37):
        self.num_perm = num_perm
        self.seed = seed
        random.seed(seed)
        # 生成线性哈希参数 (a, b)，大素数 p = 2^31 - 1
        self.p = 2147483647
        self.perms = [
            (random.randint(1, self.p - 1), random.randint(0, self.p - 1))
            for _ in range(num_perm)
        ]

    def compute(self, values: Set[str]) -> List[int]:
        """为一组字符串值计算 MinHash 签名。"""
        if not values:
            return [self.p] * self.num_perm

        sig = [self.p] * self.num_perm
        for val in values:
            # 基础哈希：用 Python 内置 hash 取正
            base = (hash(val) & 0x7FFFFFFF) % self.p
            for i, (a, b) in enumerate(self.perms):
                h = ((a * base + b) % self.p) & 0x7FFFFFFF
                if h < sig[i]:
                    sig[i] = h
        return sig


class LSH:
    """基于 MinHash 签名的局部敏感哈希分桶器。"""

    def __init__(self, num_perm: int = 128, num_bands: int = 16):
        self.num_perm = num_perm
        self.num_bands = num_bands
        self.rows_per_band = num_perm // num_bands

    def _band_key(self, signature: List[int], band_idx: int) -> str:
        start = band_idx * self.rows_per_band
        end = start + self.rows_per_band
        return hashlib.md5(str(signature[start:end]).encode()).hexdigest()[:16]

    def get_buckets(self, sig_map: Dict[str, List[int]]) -> Dict[str, List[str]]:
        """
        输入: {column_id: minhash_signature}
        输出: {bucket_key: [column_id, ...]}
        只有被分到同一个桶里的列对，才值得做精确 Jaccard 计算。
        """
        buckets: Dict[str, List[str]] = {}
        for col_id, sig in sig_map.items():
            for band_idx in range(self.num_bands):
                key = f"b{band_idx}:{self._band_key(sig, band_idx)}"
                buckets.setdefault(key, []).append(col_id)
        return buckets

    def candidate_pairs(self, sig_map: Dict[str, List[int]]) -> Set[Tuple[str, str]]:
        """返回所有需要精确比对的候选列对（去重、无序）。"""
        buckets = self.get_buckets(sig_map)
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
