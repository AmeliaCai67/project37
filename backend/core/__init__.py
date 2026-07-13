from .security import verify_password, get_password_hash, create_access_token, decode_token

__all__ = [
    "verify_password", "get_password_hash", "create_access_token", "decode_token",
    "get_logger",
    "LLMClient",
]


def __getattr__(name: str):
    """懒加载依赖 settings 的子模块，避免 settings 初始化阶段循环导入。"""
    if name == "get_logger":
        from .logging import get_logger
        return get_logger
    if name == "LLMClient":
        from .llm_client import LLMClient
        return LLMClient
    raise AttributeError(f"module 'core' has no attribute '{name}'")
