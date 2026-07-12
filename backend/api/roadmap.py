"""Roadmap 相关路由"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from api.deps import get_current_user
from models.base import get_db
from models.user import User
from models.workspace import Workspace
from schemas.common import BaseResponse
from services.roadmap_service import RoadmapService
from core.logging import get_logger

router = APIRouter(prefix="/workspaces", tags=["roadmap"])

logger = get_logger(__name__)


@router.get(
    "/{workspace_id}/roadmap",
    response_model=BaseResponse,
    response_model_exclude_none=True,
)
async def get_roadmap(
    workspace_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取指定工作空间的数据画像与推荐问题"""
    ws = db.query(Workspace).filter_by(
        id=workspace_id, owner_id=current_user.id
    ).first()
    if not ws:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found",
        )

    try:
        roadmap = await RoadmapService.build_roadmap(ws)
    except Exception:
        logger.exception("Failed to build roadmap for workspace %s", workspace_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to build roadmap. Please try again later.",
        )

    return BaseResponse(data=roadmap)
