from services.workspace_service import WorkspaceService
from pathlib import Path


def test_external_mount_creates_copy(db_session, tmp_path):
    from models.user import User
    user = User(username="c1", hashed_password="x", role="admin")
    db_session.add(user)
    db_session.commit()

    src = tmp_path / "source"
    src.mkdir()
    (src / "data.csv").write_text("x\n1\n")

    ws = WorkspaceService.mount(db_session, user, str(src), "s")
    copy_dir = WorkspaceService.get_internal_copy_dir(user.id, ws.id)

    WorkspaceService.sync_external_to_copy(ws, copy_dir)

    assert (copy_dir / "data.csv").exists()
    assert (copy_dir / "data.csv").read_text() == "x\n1\n"
