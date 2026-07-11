from datetime import datetime
from pathlib import Path
from sqlalchemy.orm import Session
from models.workspace import Workspace
from models.user import User
from services.file_service import FileService


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
