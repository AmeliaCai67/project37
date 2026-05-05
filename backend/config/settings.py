from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings

BASE_DIR = Path(__file__).resolve().parent.parent


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
    SECRET_KEY: str = "your-secret-key-change-in-production"
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
    LLM_PROVIDER: Literal["deepseek", "minimax", "openai"] = "deepseek"
    LLM_API_KEY: str = ""
    LLM_BASE_URL: str = ""
    LLM_MODEL: str = "deepseek-chat"  # 或 minimax-text-01
    LLM_MAX_TOKENS: int = 4096
    LLM_TEMPERATURE: float = 0.7
    
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
        super().__init__(**kwargs)
        # 确保上传目录存在
        self.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


settings = Settings()
