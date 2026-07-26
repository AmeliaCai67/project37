import json
import mimetypes
import shutil
from datetime import datetime
from pathlib import Path
from typing import List, Optional
from sqlalchemy.orm import Session
from models.workspace import Workspace
from models.file import File
from models.user import User
from services.file_service import FileService
from services.file_extractor import extract_file_content
from core.logging import get_logger

logger = get_logger(__name__)


class WorkspaceService:
    @staticmethod
    def get_or_create_internal(db: Session, user: User) -> Workspace:
        ws = db.query(Workspace).filter_by(
            owner_id=user.id, type="internal"
        ).first()
        if ws:
            return ws

        user_dir = FileService._get_user_dir(user.id)
        output_path = str(user_dir / "37-output")
        ws = Workspace(
            owner_id=user.id,
            name="我的数据空间",
            type="internal",
            source_path=None,
            output_path=output_path
        )
        db.add(ws)
        db.commit()
        db.refresh(ws)
        return ws

    @staticmethod
    def mount(db: Session, user: User, local_path: str, name: str) -> Workspace:
        p = Path(local_path).resolve()
        if not p.exists():
            raise ValueError(f"Path does not exist: {local_path}")
        if not p.is_dir():
            raise ValueError(f"Path is not a directory: {local_path}")

        try:
            next(p.iterdir())
        except PermissionError:
            raise ValueError(f"Cannot read directory: {local_path}")
        except StopIteration:
            pass

        output_path = str(p / "37-output")
        ws = Workspace(
            owner_id=user.id,
            name=name,
            type="external",
            source_path=str(p),
            output_path=output_path
        )
        db.add(ws)
        db.commit()
        db.refresh(ws)
        return ws

    @staticmethod
    def unmount(db: Session, user: User, workspace_id: int) -> None:
        ws = db.query(Workspace).filter_by(id=workspace_id, owner_id=user.id).first()
        if not ws:
            raise ValueError("Workspace not found")
        # 解除关联的文件（保留用户上传数据，不级联删除）
        db.query(File).filter_by(workspace_id=ws.id).update(
            {File.workspace_id: None}
        )
        db.delete(ws)
        db.commit()

    @staticmethod
    def set_output_path(db: Session, user: User, workspace_id: int, output_path: str) -> Workspace:
        p = Path(output_path).resolve()
        if p.exists() and not p.is_dir():
            raise ValueError(f"Invalid output path: {output_path}")
        p.mkdir(parents=True, exist_ok=True)
        if not p.is_dir():
            raise ValueError(f"Invalid output path: {output_path}")

        ws = db.query(Workspace).filter_by(id=workspace_id, owner_id=user.id).first()
        if not ws:
            raise ValueError("Workspace not found")

        ws.output_path = str(p)
        db.commit()
        db.refresh(ws)
        return ws

    @staticmethod
    def get_output_date_dir(workspace: Workspace) -> Path:
        return Path(workspace.output_path) / datetime.now().strftime("%Y-%m-%d")

    @staticmethod
    def get_internal_copy_dir(user_id: int, workspace_id: int) -> Path:
        base = Path(FileService._get_user_dir(user_id)) / "mounts" / str(workspace_id)
        base.mkdir(parents=True, exist_ok=True)
        return base

    # ── 同步黑名单（手动「移出档案柜」的文件）──

    @staticmethod
    def get_sync_exclusions(workspace: Workspace) -> List[dict]:
        """解析黑名单 JSON，容错返回 []"""
        try:
            data = json.loads(workspace.sync_exclusions or "[]")
            return data if isinstance(data, list) else []
        except (ValueError, TypeError):
            return []

    @staticmethod
    def add_sync_exclusion(
        db: Session, workspace: Workspace, name: str, source_mtime: Optional[float]
    ) -> None:
        """将文件名加入同步黑名单（按 name 去重）"""
        exclusions = [
            e for e in WorkspaceService.get_sync_exclusions(workspace)
            if e.get("name") != name
        ]
        exclusions.append({"name": name, "deleted_source_mtime": source_mtime})
        workspace.sync_exclusions = json.dumps(exclusions, ensure_ascii=False)
        db.commit()

    @staticmethod
    def sync_external_to_copy(
        db: Optional[Session], workspace: Workspace, copy_dir: Path
    ) -> None:
        if workspace.type != "external":
            return
        src = Path(workspace.source_path).resolve()
        copy_dir.mkdir(parents=True, exist_ok=True)

        # 黑名单：name → 删除时源文件 mtime；源文件被修改（mtime 更新）则移出黑名单
        exclusions = WorkspaceService.get_sync_exclusions(workspace)
        excluded = {e.get("name"): e.get("deleted_source_mtime") for e in exclusions}
        exclusions_dirty = False

        allowed_ext = {".csv", ".xlsx", ".xls", ".json", ".txt", ".md", ".pdf", ".docx"}
        MAX_FILES = 1000  # 防止超大目录导致性能问题
        copied = 0

        for f in src.iterdir():
            if not f.is_file() or f.suffix.lower() not in allowed_ext:
                continue
            if f.name in excluded:
                deleted_mtime = excluded[f.name]
                if deleted_mtime is not None and f.stat().st_mtime > deleted_mtime:
                    # 用户在源文件夹修改过该文件：移出黑名单，恢复同步
                    excluded.pop(f.name)
                    exclusions = [e for e in exclusions if e.get("name") != f.name]
                    exclusions_dirty = True
                else:
                    continue
            dest = copy_dir / f.name
            # 增量同步：仅当目标不存在或源文件更新时才复制
            if dest.exists():
                if f.stat().st_mtime <= dest.stat().st_mtime:
                    continue
            shutil.copy2(f, dest)
            copied += 1
            if copied >= MAX_FILES:
                break

        if exclusions_dirty:
            workspace.sync_exclusions = json.dumps(exclusions, ensure_ascii=False)
            if db is not None:
                db.commit()

    @staticmethod
    def sync_and_register(db: Session, user: User, workspace: Workspace) -> List[File]:
        """同步外部目录到隔离副本，并为副本中的文件登记 File 记录（幂等）

        挂载后【文件】页即可看到目录内文件；后续源目录新增的文件在聊天时增量登记。
        已登记的文件（按 filepath 判重）跳过，不重复提取。
        """
        copy_dir = WorkspaceService.get_internal_copy_dir(user.id, workspace.id)
        WorkspaceService.sync_external_to_copy(db, workspace, copy_dir)
        new_files = WorkspaceService._register_copy_dir(db, user, workspace, copy_dir)

        # 就地提取文本（增量、文件量小，耗时可接受）
        for db_file in new_files:
            result = extract_file_content(db_file.filepath, db_file.mime_type)
            if result["success"]:
                db_file.extracted_text = result["text"]
                db_file.status = "ready"
            else:
                db_file.status = "error"
                db_file.error_message = result.get("error", "提取失败")
            db_file.processed_at = datetime.utcnow()

        db.commit()
        if new_files:
            logger.info(
                "Registered %d files for workspace %s", len(new_files), workspace.id
            )
        return new_files

    @staticmethod
    def sync_and_register_deferred(db: Session, user: User, workspace: Workspace) -> List[int]:
        """同步 + 快速登记（不提取文本），返回新登记的文件 id 列表

        供「切换数据空间 / 进入文件页」使用：立即返回不阻塞，
        文本提取由调用方交给后台任务（FileService.extract_content_in_background）。
        """
        if workspace.type != "external":
            return []
        copy_dir = WorkspaceService.get_internal_copy_dir(user.id, workspace.id)
        WorkspaceService.sync_external_to_copy(db, workspace, copy_dir)
        new_files = WorkspaceService._register_copy_dir(db, user, workspace, copy_dir)
        db.commit()
        if new_files:
            logger.info(
                "Deferred-registered %d files for workspace %s",
                len(new_files), workspace.id,
            )
        return [f.id for f in new_files]

    @staticmethod
    def _register_copy_dir(
        db: Session, user: User, workspace: Workspace, copy_dir: Path
    ) -> List[File]:
        """为副本目录中未登记的文件创建 File 记录（status=pending，幂等）"""
        allowed_ext = {".csv", ".xlsx", ".xls", ".json", ".txt", ".md", ".pdf", ".docx"}
        new_files: List[File] = []

        for f in sorted(copy_dir.iterdir()):
            if not f.is_file() or f.suffix.lower() not in allowed_ext:
                continue
            exists = db.query(File).filter_by(
                owner_id=user.id, filepath=str(f)
            ).first()
            if exists:
                # 孤儿记录：之前所属 workspace 被卸载，workspace_id 被置为 NULL。
                # 重新挂载同目录（SQLite 复用 workspace id，副本路径相同）时，
                # 应把该记录重新关联到当前 workspace，否则文件页会假空。
                if exists.workspace_id is None:
                    exists.workspace_id = workspace.id
                    exists.status = "pending"
                    db.add(exists)
                    new_files.append(exists)
                continue

            mime_type, _ = mimetypes.guess_type(f.name)
            db_file = File(
                owner_id=user.id,
                filename=f.name,
                original_name=f.name,
                filepath=str(f),
                size=f.stat().st_size,
                mime_type=mime_type,
                file_hash=FileService._calculate_hash(f),
                status="pending",
                uploaded_at=datetime.utcnow(),
                workspace_id=workspace.id,
            )
            db.add(db_file)
            db.flush()
            new_files.append(db_file)

        return new_files
