from fastapi import APIRouter

from .auth import router as auth_router
from .files import router as files_router
from .conversations import router as conversations_router
from .chat import router as chat_router
from .workspaces import router as workspaces_router
from .roadmap import router as roadmap_router
from .config import router as config_router

api_router = APIRouter(prefix="/api")

api_router.include_router(auth_router, prefix="/auth", tags=["认证"])
api_router.include_router(files_router, prefix="/files", tags=["文件"])
api_router.include_router(conversations_router, prefix="/conversations", tags=["对话"])
api_router.include_router(chat_router, prefix="/chat", tags=["聊天"])
api_router.include_router(workspaces_router, prefix="/workspaces", tags=["工作空间"])
api_router.include_router(roadmap_router)
api_router.include_router(config_router, prefix="/config", tags=["配置"])
