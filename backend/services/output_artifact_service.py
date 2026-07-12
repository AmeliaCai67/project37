from pathlib import Path
from datetime import datetime
from typing import List
from sqlalchemy.orm import Session

from models.output_artifact import OutputArtifact
from models.workspace import Workspace


class OutputArtifactService:
    _TYPE_MAP = {
        ".md": "report",
        ".png": "chart",
        ".jpg": "chart",
        ".jpeg": "chart",
        ".svg": "chart",
        ".csv": "csv",
        ".xlsx": "spreadsheet",
        ".xls": "spreadsheet",
        ".json": "json",
        ".txt": "text",
        ".pdf": "pdf",
    }

    @staticmethod
    def get_output_date_dir(workspace: Workspace) -> Path:
        """返回当前日期的输出子目录：{output_path}/YYYY-MM-DD/"""
        return Path(workspace.output_path) / datetime.now().strftime("%Y-%m-%d")

    @staticmethod
    def ensure_output_date_dir(workspace: Workspace) -> Path:
        """确保当前日期的输出子目录存在"""
        p = OutputArtifactService.get_output_date_dir(workspace)
        p.mkdir(parents=True, exist_ok=True)
        return p

    @staticmethod
    def scan_and_record(
        db: Session,
        workspace: Workspace,
        output_dir: Path,
        conversation_id: int = None,
    ) -> List[OutputArtifact]:
        """扫描输出目录中的文件并记录为 OutputArtifact"""
        if not output_dir.exists():
            return []

        artifacts = []
        workspace_root = Path(workspace.output_path)

        for f in output_dir.iterdir():
            if not f.is_file():
                continue
            try:
                relative_path = str(f.relative_to(workspace_root))
            except ValueError:
                relative_path = str(f)

            art = OutputArtifact(
                workspace_id=workspace.id,
                conversation_id=conversation_id,
                filename=f.name,
                relative_path=relative_path,
                artifact_type=OutputArtifactService._TYPE_MAP.get(
                    f.suffix.lower(), "other"
                ),
            )
            db.add(art)
            artifacts.append(art)

        if artifacts:
            db.commit()
        return artifacts

    @staticmethod
    def list_by_workspace(db: Session, workspace_id: int) -> List[OutputArtifact]:
        return (
            db.query(OutputArtifact)
            .filter_by(workspace_id=workspace_id)
            .order_by(OutputArtifact.created_at.desc())
            .all()
        )
