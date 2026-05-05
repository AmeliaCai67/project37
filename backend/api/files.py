"""文件相关路由"""
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, UploadFile, File, Query, status
from sqlalchemy.orm import Session

from config import settings
from models.base import get_db
from models.user import User, Role
from schemas.file import FileResponse, FileListResponse
from schemas.common import BaseResponse, PaginatedResponse
from services.file_service import FileService
from api.deps import get_current_user, require_admin
from core.logging import get_logger

router = APIRouter()
logger = get_logger(__name__)


@router.post("/upload", response_model=BaseResponse)
async def upload_file(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """上传文件 - 需要 write 或 admin 权限"""
    try:
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > settings.MAX_UPLOAD_SIZE:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"文件大小超过限制（最大 {settings.MAX_UPLOAD_SIZE // (1024*1024)}MB）",
            )
        content = await file.read()
        db_file = FileService.save_upload(
            db=db,
            user=current_user,
            file_content=content,
            original_filename=file.filename,
        )

        # 文件内容提取放到后台任务，不阻塞上传响应
        background_tasks.add_task(FileService.extract_content_in_background, db_file.id)

        return BaseResponse(data={
            "id": db_file.id,
            "filename": db_file.original_name,
            "size": db_file.size,
            "status": db_file.status,
        })
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get("/list", response_model=PaginatedResponse[FileResponse])
async def list_files(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取文件列表"""
    skip = (page - 1) * page_size
    files, total = FileService.get_user_files(db, current_user.id, skip, page_size)
    
    total_pages = (total + page_size - 1) // page_size
    
    return PaginatedResponse(
        data=files,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/{file_id}", response_model=FileResponse)
async def get_file(
    file_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取单个文件信息"""
    file = FileService.get_by_id(db, file_id)
    if not file or file.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="文件不存在",
        )
    return file


@router.delete("/{file_id}", response_model=BaseResponse)
async def delete_file(
    file_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """删除文件 - 需要 write 或 admin 权限"""
    success = FileService.delete(db, file_id, current_user.id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="文件不存在或无权删除",
        )
    return BaseResponse(message="删除成功")
