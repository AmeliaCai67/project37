"""对话相关路由"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from models.base import get_db
from models.user import User
from schemas.conversation import (
    ConversationCreate, ConversationResponse, 
    MessageResponse
)
from schemas.common import BaseResponse, PaginatedResponse
from services.conversation_service import ConversationService
from api.deps import get_current_user

router = APIRouter()


@router.post("/create", response_model=BaseResponse)
async def create_conversation(
    title: Optional[str] = "新对话",
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """创建新对话"""
    conversation = ConversationService.create(db, current_user, title=title)
    return BaseResponse(data={
        "id": conversation.id,
        "title": conversation.title,
        "created_at": conversation.created_at,
    })


@router.get("/list", response_model=PaginatedResponse[ConversationResponse])
async def list_conversations(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取对话列表"""
    skip = (page - 1) * page_size
    conversations, total = ConversationService.get_user_conversations(
        db, current_user.id, skip, page_size
    )
    
    total_pages = (total + page_size - 1) // page_size
    
    return PaginatedResponse(
        data=conversations,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/{conversation_id}", response_model=BaseResponse)
async def get_conversation(
    conversation_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取对话详情（包含消息）"""
    conversation = ConversationService.get_by_id(db, conversation_id)
    if not conversation or conversation.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="对话不存在",
        )
    
    messages = ConversationService.get_messages(db, conversation_id)
    
    return BaseResponse(data={
        "id": conversation.id,
        "title": conversation.title,
        "model": conversation.model,
        "created_at": conversation.created_at,
        "updated_at": conversation.updated_at,
        "messages": [
            {
                "id": msg.id,
                "role": msg.role.value,
                "content": msg.content,
                "tokens_used": msg.tokens_used,
                "created_at": msg.created_at,
            }
            for msg in messages
        ],
    })


@router.put("/{conversation_id}/title", response_model=BaseResponse)
async def update_title(
    conversation_id: int,
    title: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """更新对话标题"""
    conversation = ConversationService.get_by_id(db, conversation_id)
    if not conversation or conversation.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="对话不存在",
        )
    
    ConversationService.update_title(db, conversation_id, title)
    return BaseResponse(message="更新成功")


@router.delete("/{conversation_id}", response_model=BaseResponse)
async def delete_conversation(
    conversation_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """删除对话"""
    success = ConversationService.delete(db, conversation_id, current_user.id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="对话不存在",
        )
    return BaseResponse(message="删除成功")
