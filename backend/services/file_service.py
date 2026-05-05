import hashlib
import shutil
from datetime import datetime
from pathlib import Path
from typing import List, Optional
import mimetypes

from sqlalchemy.orm import Session

from models.file import File
from models.user import User
from schemas.file import FileCreate
from config import settings
from core.logging import get_logger
from services.file_extractor import extract_file_content

logger = get_logger(__name__)


class FileService:
    """文件服务"""
    
    @staticmethod
    def _get_user_dir(user_id: int) -> Path:
        """获取用户上传目录"""
        user_dir = settings.UPLOAD_DIR / f"user_{user_id}"
        user_dir.mkdir(parents=True, exist_ok=True)
        return user_dir
    
    @staticmethod
    def _calculate_hash(file_path: Path) -> str:
        """计算文件 SHA256 哈希"""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
    
    @staticmethod
    def get_by_id(db: Session, file_id: int) -> Optional[File]:
        """通过ID获取文件"""
        return db.query(File).filter(File.id == file_id).first()
    
    @staticmethod
    def get_user_files(db: Session, user_id: int, skip: int = 0, limit: int = 100) -> tuple[List[File], int]:
        """获取用户的文件列表"""
        query = db.query(File).filter(File.owner_id == user_id)
        total = query.count()
        files = query.order_by(File.uploaded_at.desc()).offset(skip).limit(limit).all()
        return files, total
    
    @staticmethod
    def save_upload(
        db: Session,
        user: User,
        file_content: bytes,
        original_filename: str,
    ) -> File:
        """保存上传的文件"""
        # 检查文件扩展名
        ext = Path(original_filename).suffix.lower()
        if ext.lstrip(".") not in settings.ALLOWED_EXTENSIONS:
            raise ValueError(f"不支持的文件类型: {ext}")
        
        # 检查文件大小
        if len(file_content) > settings.MAX_UPLOAD_SIZE:
            raise ValueError(f"文件大小超过限制: {settings.MAX_UPLOAD_SIZE / 1024 / 1024}MB")
        
        # 生成存储文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_filename = f"{timestamp}_{original_filename}"
        
        # 用户目录
        user_dir = FileService._get_user_dir(user.id)
        file_path = user_dir / safe_filename
        
        # 写入文件
        with open(file_path, "wb") as f:
            f.write(file_content)
        
        # 计算哈希
        file_hash = FileService._calculate_hash(file_path)
        
        # 检查是否重复上传
        existing = db.query(File).filter(File.file_hash == file_hash, File.owner_id == user.id).first()
        if existing:
            # 删除新上传的文件
            file_path.unlink()
            logger.info(f"Duplicate file upload detected: {original_filename}")
            return existing
        
        # 获取 MIME 类型
        mime_type, _ = mimetypes.guess_type(original_filename)
        
        # 创建数据库记录
        db_file = File(
            owner_id=user.id,
            filename=safe_filename,
            original_name=original_filename,
            filepath=str(file_path),
            size=len(file_content),
            mime_type=mime_type,
            file_hash=file_hash,
            status="pending",  # 等待处理
            uploaded_at=datetime.utcnow(),
        )
        
        db.add(db_file)
        db.commit()
        db.refresh(db_file)
        
        logger.info(f"File uploaded: {original_filename} by {user.username}")
        return db_file

    @staticmethod
    def extract_content_in_background(file_id: int) -> None:
        """后台任务：提取文件内容并更新数据库（创建独立 session）"""
        from models.base import SessionLocal
        db = SessionLocal()
        try:
            file = db.query(File).filter(File.id == file_id).first()
            if not file:
                return

            file.status = "processing"
            db.commit()

            result = extract_file_content(file.filepath, file.mime_type)

            if result["success"]:
                file.extracted_text = result["text"]
                file.status = "ready"
                logger.info(f"File content extracted: {file.original_name} "
                           f"({result['original_size']} chars, truncated: {result['truncated']})")
            else:
                file.status = "error"
                file.error_message = result.get("error", "提取失败")
                logger.error(f"File extraction failed: {file.original_name} - {result.get('error')}")

            db.commit()

        except Exception as e:
            file = db.query(File).filter(File.id == file_id).first()
            if file:
                file.status = "error"
                file.error_message = str(e)
                db.commit()
            logger.error(f"File extraction exception: file_id={file_id} - {e}")
        finally:
            db.close()
    
    @staticmethod
    def delete(db: Session, file_id: int, user_id: int) -> bool:
        """删除文件"""
        file = db.query(File).filter(File.id == file_id, File.owner_id == user_id).first()
        if not file:
            return False
        
        # 删除物理文件
        try:
            Path(file.filepath).unlink(missing_ok=True)
        except Exception as e:
            logger.error(f"Failed to delete file: {e}")
        
        # 删除数据库记录
        db.delete(file)
        db.commit()
        
        logger.info(f"File deleted: {file.original_name}")
        return True
    
    @staticmethod
    def update_status(
        db: Session,
        file_id: int,
        status: str,
        extracted_text: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> Optional[File]:
        """更新文件处理状态"""
        file = FileService.get_by_id(db, file_id)
        if not file:
            return None
        
        file.status = status
        if extracted_text is not None:
            file.extracted_text = extracted_text
        if error_message is not None:
            file.error_message = error_message
        
        file.processed_at = datetime.utcnow()
        db.commit()
        db.refresh(file)
        
        return file
