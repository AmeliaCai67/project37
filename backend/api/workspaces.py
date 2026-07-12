"""工作空间相关路由"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from api.deps import get_current_user
from models.base import get_db
from models.user import User
from models.workspace import Workspace
from schemas.common import BaseResponse
from schemas.workspace import MountRequest, OutputPathRequest
from services.workspace_service import WorkspaceService

router = APIRouter()


@router.get("/list", response_model=BaseResponse)
async def list_workspaces(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取当前用户的工作空间列表"""
    WorkspaceService.get_or_create_internal(db, current_user)
    workspaces = db.query(Workspace).filter_by(owner_id=current_user.id).all()
    return BaseResponse(data=[
        {
            "id": ws.id,
            "name": ws.name,
            "type": ws.type,
            "source_path": ws.source_path,
            "output_path": ws.output_path,
            "is_active": ws.is_active,
            "created_at": ws.created_at.isoformat() if ws.created_at else None,
        }
        for ws in workspaces
    ])


@router.post("/mount", response_model=BaseResponse)
async def mount_workspace(
    req: MountRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """挂载本地目录为外部工作空间"""
    try:
        ws = WorkspaceService.mount(db, current_user, req.local_path, req.name)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    return BaseResponse(data={
        "id": ws.id,
        "name": ws.name,
        "type": ws.type,
        "source_path": ws.source_path,
        "output_path": ws.output_path,
    })


@router.post("/{workspace_id}/unmount", response_model=BaseResponse)
async def unmount_workspace(
    workspace_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """卸载指定工作空间"""
    try:
        WorkspaceService.unmount(db, current_user, workspace_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    return BaseResponse(data={"unmounted": True})


@router.put("/{workspace_id}/output-path", response_model=BaseResponse)
async def update_output_path(
    workspace_id: int,
    req: OutputPathRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """更新工作空间的输出路径"""
    try:
        ws = WorkspaceService.set_output_path(
            db, current_user, workspace_id, req.output_path
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    return BaseResponse(data={
        "id": ws.id,
        "output_path": ws.output_path,
    })
