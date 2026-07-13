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
