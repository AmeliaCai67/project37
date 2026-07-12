"""Roadmap 相关 Schema"""
from typing import Any, List
from pydantic import BaseModel


class RoadmapResponse(BaseModel):
    """工作空间数据画像与推荐问题响应"""

    tables: List[Any]
    relationships: List[Any]
    questions: List[str]
