"""认证相关路由"""
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from models.base import get_db
from models.user import User, Role
from schemas.user import UserCreate, UserResponse, UserLogin, Token
from schemas.common import BaseResponse
from services.user_service import UserService
from api.deps import get_current_user
from core.security import create_access_token, get_password_hash
from core.logging import get_logger
from config import settings

router = APIRouter()
logger = get_logger(__name__)


def resolve_role(username: str) -> Role:
    """根据系统配置自动分配用户角色"""
    if settings.APP_MODE == "personal":
        return Role.ADMIN
    admin_list = [u.strip() for u in settings.ADMIN_USERS.split(",") if u.strip()]
    return Role.ADMIN if username in admin_list else Role.USER


@router.post("/register", response_model=BaseResponse)
async def register(user_create: UserCreate, db: Session = Depends(get_db)):
    """用户注册"""
    try:
        if user_create.role is None:
            user_create.role = resolve_role(user_create.username)
        user = UserService.create(db, user_create)
        return BaseResponse(
            data={
                "id": user.id,
                "username": user.username,
                "role": user.role.value,
            }
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post("/auto", response_model=Token)
async def auto_login(db: Session = Depends(get_db)):
    """打包版自动登录：personal 模式下自动创建/返回默认用户 Token。"""
    if settings.APP_MODE != "personal":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="auto login 仅在 personal 模式下可用",
        )
    user = UserService.get_or_create_default_user(db)
    access_token = create_access_token(
        data={"sub": user.username, "role": user.role.value}
    )
    logger.info(f"Auto logged in: {user.username}")
    return Token(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/login", response_model=Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    """用户登录 - 支持 form-data 格式"""
    user = UserService.authenticate(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token = create_access_token(
        data={"sub": user.username, "role": user.role.value}
    )
    
    logger.info(f"User logged in: {user.username}")
    
    return Token(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/login/json", response_model=Token)
async def login_json(user_login: UserLogin, db: Session = Depends(get_db)):
    """用户登录 - 支持 JSON 格式"""
    user = UserService.authenticate(db, user_login.username, user_login.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
        )
    
    access_token = create_access_token(
        data={"sub": user.username, "role": user.role.value}
    )
    
    logger.info(f"User logged in: {user.username}")
    
    return Token(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    """获取当前用户信息"""
    return current_user
