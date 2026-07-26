"""工作空间相关路由"""
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session

from api.deps import get_current_user
from models.base import get_db
from models.user import User
from models.workspace import Workspace
from schemas.common import BaseResponse
from schemas.workspace import MountRequest, OutputPathRequest
from services.file_service import FileService
from services.roadmap_service import RoadmapService
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
    background_tasks: BackgroundTasks,
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
    # 同步到隔离副本并登记 File 记录，让【文件】页立刻可见目录内文件
    WorkspaceService.sync_and_register(db, current_user, ws)
    # 后台触发数据画像与推荐问题生成
    background_tasks.add_task(RoadmapService.build_roadmap_in_background, ws.id)
    return BaseResponse(data={
        "id": ws.id,
        "name": ws.name,
        "type": ws.type,
        "source_path": ws.source_path,
        "output_path": ws.output_path,
    })


@router.post("/{workspace_id}/sync", response_model=BaseResponse)
async def sync_workspace(
    workspace_id: int,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """实时同步 external 空间源文件夹并登记新文件

    快速返回（文本提取走后台任务），供「切换数据空间 / 进入文件页」触发。
    黑名单内（手动移出档案柜）的文件跳过，除非源文件已被修改。
    """
    ws = db.query(Workspace).filter_by(
        id=workspace_id, owner_id=current_user.id
    ).first()
    if not ws:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found",
        )

    new_file_ids = WorkspaceService.sync_and_register_deferred(db, current_user, ws)
    for fid in new_file_ids:
        background_tasks.add_task(FileService.extract_content_in_background, fid)

    return BaseResponse(data={"new_files": len(new_file_ids)})


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
