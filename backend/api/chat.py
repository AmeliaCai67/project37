"""聊天相关路由"""
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from models.base import get_db
from models.user import User
from schemas.conversation import ChatRequest, ChatResponse
from schemas.common import BaseResponse
from services.chat_service import ChatService
from api.deps import get_current_user
from core.logging import get_logger

router = APIRouter()
logger = get_logger(__name__)


@router.post("/send", response_model=BaseResponse)
async def send_message(
    request: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """发送消息（非流式）"""
    try:
        result = await ChatService.chat(
            db=db,
            user=current_user,
            message=request.message,
            conversation_id=request.conversation_id,
            file_ids=request.file_ids,
            workspace_id=request.workspace_id,
        )
        
        return BaseResponse(data=result)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Chat error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="服务器内部错误",
        )


@router.post("/send/stream")
async def send_message_stream(
    request: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """发送消息（流式 SSE）- 文件即知识库模式"""
    try:
        return StreamingResponse(
            ChatService.chat_stream(
                db=db,
                user=current_user,
                message=request.message,
                conversation_id=request.conversation_id,
                file_ids=request.file_ids,
                workspace_id=request.workspace_id,
            ),
            media_type="text/event-stream",
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Stream chat error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="服务器内部错误",
        )
