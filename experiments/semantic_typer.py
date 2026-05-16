"""
语义类型打标模块（Semantic Typing）

基于正则表达式对列样本值进行业务语义识别，提升跨表关联的准确率。
"""

import re
from typing import Optional


class SemanticTyper:
    """轻量级语义类型识别器。"""

    PATTERNS = {
        "email": re.compile(
            r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        ),
        "ip_address": re.compile(
            r"^(\d{1,3}\.){3}\d{1,3}$"
        ),
        "phone_number": re.compile(
            r"^(\+?\d{1,3}[-.\s]?)?\(?\d{2,4}\)?[-.\s]?\d{3,4}[-.\s]?\d{3,4}$"
        ),
        "url": re.compile(
            r"^https?://[^\s/$.?#].[^\s]*$", re.IGNORECASE
        ),
        "uuid": re.compile(
            r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
            re.IGNORECASE,
        ),
        "id_card_cn": re.compile(
            r"^\d{17}[\dXx]$"
        ),
        "latitude_longitude": re.compile(
            r"^-?\d{1,3}\.\d+[,\s]+-?\d{1,3}\.\d+$"
        ),
        "date_iso": re.compile(
            r"^\d{4}-\d{2}-\d{2}$"
        ),
        "datetime_iso": re.compile(
            r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}"
        ),
        "hex_color": re.compile(
            r"^#([0-9a-fA-F]{3}){1,2}$"
        ),
        "mac_address": re.compile(
            r"^([0-9a-fA-F]{2}[:-]){5}[0-9a-fA-F]{2}$"
        ),
    }

    # 列名关键词到语义类型的快速映射（辅助判断）
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
        """
        根据样本值的正则匹配率推断语义类型。
        返回匹配率 >= 70% 的最佳类型，否则 None。
        """
        if not sample_values:
            return None

        scores = {}
        n = len(sample_values)
        for type_name, pattern in self.PATTERNS.items():
            matched = sum(
                1 for v in sample_values if pattern.match(str(v))
            )
            if matched > 0:
                scores[type_name] = matched / n

        if not scores:
            return None

        best = max(scores, key=scores.get)
        return best if scores[best] >= 0.7 else None

    def infer_from_column_name(self, col_name: str) -> Optional[str]:
        """根据列名关键词推断语义类型。"""
        col_lower = col_name.lower()
        for sem_type, keywords in self.COLUMN_KEYWORDS.items():
            for kw in keywords:
                if kw in col_lower:
                    return sem_type
        return None

    def infer(self, sample_values: list, col_name: str) -> Optional[str]:
        """
        综合样本值和列名进行语义推断。
        优先以值匹配为准，若值匹配不足再以列名关键词兜底。
        """
        val_type = self.infer_from_values(sample_values)
        if val_type:
            return val_type
        return self.infer_from_column_name(col_name)
