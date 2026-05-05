from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy import or_

from models.user import User, Role
from schemas.user import UserCreate
from core.security import get_password_hash, verify_password
from core.logging import get_logger

logger = get_logger(__name__)


class UserService:
    """用户服务"""
    
    @staticmethod
    def get_by_username(db: Session, username: str) -> Optional[User]:
        """通过用户名获取用户"""
        return db.query(User).filter(User.username == username).first()
    
    @staticmethod
    def get_by_email(db: Session, email: str) -> Optional[User]:
        """通过邮箱获取用户"""
        return db.query(User).filter(User.email == email).first()
    
    @staticmethod
    def get_by_id(db: Session, user_id: int) -> Optional[User]:
        """通过ID获取用户"""
        return db.query(User).filter(User.id == user_id).first()
    
    @staticmethod
    def create(db: Session, user_create: UserCreate) -> User:
        """创建用户"""
        # 检查用户名/邮箱是否存在
        if user_create.email:
            existing = db.query(User).filter(
                or_(User.username == user_create.username, User.email == user_create.email)
            ).first()
        else:
            existing = db.query(User).filter(User.username == user_create.username).first()
        
        if existing:
            raise ValueError("用户名或邮箱已存在")
        
        db_user = User(
            username=user_create.username,
            email=user_create.email,
            hashed_password=get_password_hash(user_create.password),
            role=user_create.role,
            created_at=datetime.utcnow(),
        )
        
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        
        logger.info(f"User created: {db_user.username}")
        return db_user
    
    @staticmethod
    def authenticate(db: Session, username: str, password: str) -> Optional[User]:
        """验证用户密码"""
        user = UserService.get_by_username(db, username)
        if not user:
            return None
        if not verify_password(password, user.hashed_password):
            return None
        return user
    
    @staticmethod
    def update_role(db: Session, user_id: int, new_role: Role) -> Optional[User]:
        """更新用户角色"""
        user = UserService.get_by_id(db, user_id)
        if not user:
            return None
        
        user.role = new_role
        user.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(user)
        
        logger.info(f"User {user.username} role updated to {new_role}")
        return user
