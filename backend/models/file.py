from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, BigInteger, Text
from sqlalchemy.orm import relationship

from .base import Base


class File(Base):
    __tablename__ = "files"
    
    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    filename = Column(String(255), nullable=False)
    original_name = Column(String(255), nullable=False)
    filepath = Column(Text, nullable=False)
    size = Column(BigInteger, default=0)
    mime_type = Column(String(100))
    file_hash = Column(String(64), index=True)  # SHA256
    status = Column(String(20), default="pending")  # pending, processing, ready, error
    extracted_text = Column(Text)  # 文件提取的文本内容
    error_message = Column(Text)
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    processed_at = Column(DateTime)
    
    # Relationships
    owner = relationship("User", back_populates="files")
