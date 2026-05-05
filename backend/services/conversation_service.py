from datetime import datetime
from typing import List, Optional

from sqlalchemy.orm import Session

from models.conversation import Conversation, Message, MessageRole
from models.user import User
from schemas.conversation import ConversationCreate
from core.logging import get_logger

logger = get_logger(__name__)


class ConversationService:
    """对话服务"""
    
    @staticmethod
    def get_by_id(db: Session, conversation_id: int) -> Optional[Conversation]:
        """通过ID获取对话"""
        return db.query(Conversation).filter(Conversation.id == conversation_id).first()
    
    @staticmethod
    def get_user_conversations(
        db: Session,
        user_id: int,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[List[Conversation], int]:
        """获取用户的对话列表"""
        query = db.query(Conversation).filter(Conversation.owner_id == user_id)
        total = query.count()
        conversations = query.order_by(Conversation.updated_at.desc()).offset(skip).limit(limit).all()
        return conversations, total
    
    @staticmethod
    def create(db: Session, user: User, title: str = "新对话", model: str = "") -> Conversation:
        """创建新对话"""
        db_conversation = Conversation(
            owner_id=user.id,
            title=title[:200],
            model=model or "deepseek-chat",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        
        db.add(db_conversation)
        db.commit()
        db.refresh(db_conversation)
        
        logger.info(f"Conversation created: {title} by {user.username}")
        return db_conversation
    
    @staticmethod
    def update_title(db: Session, conversation_id: int, title: str) -> Optional[Conversation]:
        """更新对话标题"""
        conversation = ConversationService.get_by_id(db, conversation_id)
        if not conversation:
            return None
        
        conversation.title = title[:200]
        conversation.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(conversation)
        
        return conversation
    
    @staticmethod
    def delete(db: Session, conversation_id: int, user_id: int) -> bool:
        """删除对话"""
        conversation = db.query(Conversation).filter(
            Conversation.id == conversation_id,
            Conversation.owner_id == user_id,
        ).first()
        
        if not conversation:
            return False
        
        db.delete(conversation)
        db.commit()
        
        logger.info(f"Conversation deleted: {conversation_id}")
        return True
    
    # ============== Message 操作 ==============
    
    @staticmethod
    def get_messages(db: Session, conversation_id: int) -> List[Message]:
        """获取对话的所有消息"""
        return db.query(Message).filter(
            Message.conversation_id == conversation_id
        ).order_by(Message.created_at.asc()).all()
    
    @staticmethod
    def add_message(
        db: Session,
        conversation_id: int,
        role: MessageRole,
        content: str,
        tokens_used: int = 0,
    ) -> Message:
        """添加消息"""
        db_message = Message(
            conversation_id=conversation_id,
            role=role,
            content=content,
            tokens_used=tokens_used,
            created_at=datetime.utcnow(),
        )
        
        db.add(db_message)
        
        # 更新对话的 updated_at
        conversation = ConversationService.get_by_id(db, conversation_id)
        if conversation:
            conversation.updated_at = datetime.utcnow()
        
        db.commit()
        db.refresh(db_message)
        
        return db_message
