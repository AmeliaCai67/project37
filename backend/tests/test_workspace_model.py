import pytest

from models.workspace import Workspace
from models.output_artifact import OutputArtifact
from models.file import File
from models.user import User


def test_workspace_creation(db_session):
    user = User(username="teacher", hashed_password="x", role="admin")
    db_session.add(user)
    db_session.commit()

    ws = Workspace(
        owner_id=user.id,
        name="期末数据",
        type="internal",
        output_path=f"uploads/user_{user.id}/37-output"
    )
    db_session.add(ws)
    db_session.commit()

    assert ws.id is not None
    assert ws.type == "internal"
    assert ws.source_path is None


def test_output_artifact_creation(db_session):
    user = User(username="teacher2", hashed_password="x", role="admin")
    db_session.add(user)
    db_session.commit()

    ws = Workspace(owner_id=user.id, name="ws", type="internal", output_path="/tmp/out")
    db_session.add(ws)
    db_session.commit()

    art = OutputArtifact(
        workspace_id=ws.id,
        filename="report.md",
        relative_path="37-output/2026-07-31/report.md",
        artifact_type="report"
    )
    db_session.add(art)
    db_session.commit()

    assert art.id is not None
    assert art.workspace_id == ws.id


def test_file_has_workspace_id(db_session):
    from sqlalchemy import inspect
    inspector = inspect(File)
    assert "workspace_id" in inspector.columns
