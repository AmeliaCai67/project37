from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel

from models.conversation import MessageRole


# ============== Conversation ==============
class ConversationBase(BaseModel):
    title: Optional[str] = "新对话"


class ConversationCreate(ConversationBase):
    pass


class ConversationResponse(ConversationBase):
    id: int
    model: str
    created_at: datetime
    updated_at: datetime
    message_count: int = 0
    
    class Config:
        from_attributes = True


# ============== Message ==============
class MessageBase(BaseModel):
    content: str


class MessageCreate(MessageBase):
    role: MessageRole = MessageRole.USER


class MessageResponse(MessageBase):
    id: int
    role: MessageRole
    tokens_used: int
    created_at: datetime
    
    class Config:
        from_attributes = True


# ============== Chat ==============
class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[int] = None  # None 表示新建对话
    file_ids: Optional[List[int]] = None   # 关联的文件


class ChatResponse(BaseModel):
    response: str
    conversation_id: int
    message_id: int
    tokens_used: int
    files_referenced: Optional[List[int]] = None  # 引用的文件ID列表
