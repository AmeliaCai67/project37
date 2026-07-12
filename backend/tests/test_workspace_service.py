from datetime import datetime
from pathlib import Path
import pytest
from services.workspace_service import WorkspaceService
from models.workspace import Workspace


def test_get_or_create_internal_creates_once(db_session):
    from models.user import User
    user = User(username="u1", hashed_password="x", role="admin")
    db_session.add(user)
    db_session.commit()

    ws1 = WorkspaceService.get_or_create_internal(db_session, user)
    ws2 = WorkspaceService.get_or_create_internal(db_session, user)
    assert ws1.id == ws2.id
    assert ws1.type == "internal"
    assert ws1.output_path.endswith("37-output")


def test_mount_external_workspace(db_session, tmp_path):
    from models.user import User
    user = User(username="u2", hashed_password="x", role="admin")
    db_session.add(user)
    db_session.commit()

    src = tmp_path / "data"
    src.mkdir()
    (src / "a.csv").write_text("x,y\n1,2\n")

    ws = WorkspaceService.mount(db_session, user, str(src), "我的数据")
    assert ws.type == "external"
    assert ws.source_path == str(src)
    assert ws.output_path == str(src / "37-output")


def test_unmount_deletes_record(db_session, tmp_path):
    from models.user import User
    user = User(username="u3", hashed_password="x", role="admin")
    db_session.add(user)
    db_session.commit()

    src = tmp_path / "data"
    src.mkdir()
    ws = WorkspaceService.mount(db_session, user, str(src), "x")
    WorkspaceService.unmount(db_session, user, ws.id)

    assert db_session.query(Workspace).filter_by(id=ws.id).first() is None


def test_get_output_date_dir(db_session, tmp_path):
    from models.user import User
    user = User(username="u4", hashed_password="x", role="admin")
    db_session.add(user)
    db_session.commit()

    ws = WorkspaceService.get_or_create_internal(db_session, user)
    date_dir = WorkspaceService.get_output_date_dir(ws)
    assert date_dir.parent == Path(ws.output_path)
    assert date_dir.name == datetime.now().strftime("%Y-%m-%d")
