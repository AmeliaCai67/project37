from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from models.base import Base


class Workspace(Base):
    __tablename__ = "workspaces"

    id = Column(Integer, primary_key=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String, nullable=False, default="我的数据空间")
    type = Column(String, nullable=False)  # "internal" | "external"
    source_path = Column(String, nullable=True)
    output_path = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    owner = relationship("User", back_populates="workspaces")
    # File 使用 save-update, merge：卸载 workspace 时不删除用户上传的文件，
    # unmount() 中会先将 File.workspace_id 置为 NULL 再删除 workspace
    files = relationship("File", back_populates="workspace", cascade="save-update, merge")
    # OutputArtifact 是输出交付物，workspace 删除时可以级联清理
    artifacts = relationship("OutputArtifact", back_populates="workspace", cascade="all, delete-orphan")
