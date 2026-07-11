from pydantic import BaseModel


class MountRequest(BaseModel):
    local_path: str
    name: str


class OutputPathRequest(BaseModel):
    output_path: str
