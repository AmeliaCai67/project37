from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class FileBase(BaseModel):
    filename: str
    original_name: str


class FileCreate(FileBase):
    filepath: str
    size: int
    mime_type: Optional[str] = None
    file_hash: Optional[str] = None


class FileResponse(BaseModel):
    id: int
    filename: str
    original_name: str
    size: int
    mime_type: Optional[str]
    status: str
    uploaded_at: datetime
    processed_at: Optional[datetime]
    workspace_id: Optional[int] = None
    
    class Config:
        from_attributes = True


class FileListResponse(BaseModel):
    files: list[FileResponse]
    total: int
