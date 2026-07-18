"""运行时配置接口"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from models.base import get_db
from models.user import User
from schemas.config import ConfigStatus, ConfigUpdate
from api.deps import require_admin
from core import config_store
from core.llm_client import llm_client
from config import settings

router = APIRouter()


@router.get("/status", response_model=ConfigStatus)
async def get_config_status():
    return ConfigStatus(
        has_api_key=bool(settings.LLM_API_KEY),
        llm_provider=settings.LLM_PROVIDER,
        llm_model=settings.LLM_MODEL,
    )


@router.post("/")
async def update_config(
    payload: ConfigUpdate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    values = {
        "LLM_API_KEY": payload.llm_api_key,
        "LLM_PROVIDER": payload.llm_provider,
        "LLM_MODEL": payload.llm_model,
        "LLM_BASE_URL": payload.llm_base_url or "",
    }
    # 持久化到用户 .env
    config_store.update_user_config(values)
    # 更新当前进程中的 settings 对象（字段名为大写，直接用原键名）
    for key, value in values.items():
        if hasattr(settings, key):
            setattr(settings, key, value)
    # 更新 LLM 客户端
    llm_client.reload()
    return {"success": True}
