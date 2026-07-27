from pydantic import BaseModel


class ConfigStatus(BaseModel):
    has_api_key: bool
    llm_provider: str
    llm_model: str


class ConfigUpdate(BaseModel):
    llm_api_key: str
    llm_provider: str = "deepseek"
    llm_model: str = "deepseek-chat"
    llm_base_url: str = ""
    # 备选模型（选填；主模型请求失败时自动切换）
    llm_fallback_provider: str = ""
    llm_fallback_api_key: str = ""
    llm_fallback_model: str = ""
    llm_fallback_base_url: str = ""
