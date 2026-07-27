import os
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings

from core import paths, config_store

BASE_DIR = Path(__file__).resolve().parent.parent


def _resolve_env_file() -> Path:
    """生产/打包环境使用用户目录 .env；开发环境回退到项目根目录 .env。"""
    if paths.is_frozen() or os.environ.get("ENV") == "prod":
        config_store.ensure_user_config()
        return paths.get_user_env_file()
    project_env = BASE_DIR / ".env"
    if project_env.exists():
        return project_env
    # 兜底：确保用户目录 .env 存在，避免启动失败
    return config_store.ensure_user_config()


class Settings(BaseSettings):
    # 基础配置
    APP_NAME: str = "问数 API"
    DEBUG: bool = False
    ENV: Literal["dev", "test", "prod"] = "dev"

    # 服务器
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # 数据库
    DATABASE_URL: str = f"sqlite:///{BASE_DIR.parent}/data.db"

    # JWT
    SECRET_KEY: str = ""
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 1天

    # 文件上传
    UPLOAD_DIR: Path = BASE_DIR.parent / "uploads"
    MAX_UPLOAD_SIZE: int = 500 * 1024 * 1024  # 500MB
    ALLOWED_EXTENSIONS: set[str] = {"pdf", "docx", "csv", "xlsx", "txt", "json", "md", "py", "js", "html"}

    # 文件即知识库配置
    MAX_FILE_CONTENT_LENGTH: int = 80000  # 单个文件最大上下文长度（字符）
    MAX_FILES_PER_CHAT: int = 5  # 单次对话最多引用文件数

    # LLM 配置
    # 任意 OpenAI 兼容服务商：deepseek/kimi/qwen/zhipu/minimax/openai/custom...
    LLM_PROVIDER: str = "deepseek"
    LLM_API_KEY: str = ""
    LLM_BASE_URL: str = ""
    LLM_MODEL: str = "deepseek-chat"  # 或 minimax-text-01
    LLM_MAX_TOKENS: int = 4096
    LLM_TEMPERATURE: float = 0.7

    # 备选 LLM（选填；主模型请求失败时自动切换一次）
    LLM_FALLBACK_PROVIDER: str = ""
    LLM_FALLBACK_API_KEY: str = ""
    LLM_FALLBACK_BASE_URL: str = ""
    LLM_FALLBACK_MODEL: str = ""

    # 运行模式
    APP_MODE: Literal["personal", "team"] = "personal"
    ADMIN_USERS: str = ""  # 团队模式下管理员用户名，逗号分隔

    # 日志
    LOG_LEVEL: str = "INFO"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"

    def __init__(self, **kwargs):
        env_file = _resolve_env_file()
        super().__init__(_env_file=env_file, **kwargs)

        # 生产/打包环境：强制把持久化目录放到用户数据目录
        if paths.is_frozen() or self.ENV == "prod":
            data_dir = paths.get_app_data_dir()
            self.DATABASE_URL = f"sqlite:///{data_dir / 'data.db'}"
            self.UPLOAD_DIR = data_dir / "uploads"
            self.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

        # 安全检查：拒绝使用默认或空 SECRET_KEY
        if not self.SECRET_KEY or self.SECRET_KEY == "your-secret-key-change-in-production":
            raise ValueError(
                "SECRET_KEY 未设置或仍为默认值。"
                "请在 .env 文件中设置一个强随机密钥。\n"
                "生成方式: python -c \"import secrets; print(secrets.token_urlsafe(64))\""
            )


settings = Settings()
