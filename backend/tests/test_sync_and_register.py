"""挂载外部文件夹后文件自动登记到 File 表（【文件】页可见）"""
from pathlib import Path

import pytest

from config import settings
from models.file import File
from services.workspace_service import WorkspaceService


@pytest.fixture
def upload_dir_tmp(tmp_path, monkeypatch):
    d = tmp_path / "uploads"
    d.mkdir()
    monkeypatch.setattr(settings, "UPLOAD_DIR", d)
    return d


def _make_user(db_session, name="r1"):
    from models.user import User
    user = User(username=name, hashed_password="x", role="admin")
    db_session.add(user)
    db_session.commit()
    return user


def test_sync_and_register_creates_file_records(db_session, tmp_path, upload_dir_tmp):
    user = _make_user(db_session)
    src = tmp_path / "source"
    src.mkdir()
    (src / "orders.csv").write_text("a,b\n1,2\n")
    (src / "notes.txt").write_text("hello")
    (src / "ignored.exe").write_bytes(b"MZ")  # 不在允许扩展名内

    ws = WorkspaceService.mount(db_session, user, str(src), "s")
    new_files = WorkspaceService.sync_and_register(db_session, user, ws)

    assert len(new_files) == 2
    files = db_session.query(File).filter_by(owner_id=user.id, workspace_id=ws.id).all()
    assert len(files) == 2
    by_name = {f.original_name: f for f in files}
    assert set(by_name) == {"orders.csv", "notes.txt"}
    # 已提取文本、状态 ready，【文件】页与对话预加载可直接使用
    assert by_name["orders.csv"].status == "ready"
    assert by_name["orders.csv"].extracted_text
    assert by_name["notes.txt"].status == "ready"


def test_sync_and_register_is_idempotent(db_session, tmp_path, upload_dir_tmp):
    user = _make_user(db_session, "r2")
    src = tmp_path / "source"
    src.mkdir()
    (src / "a.csv").write_text("x\n1\n")

    ws = WorkspaceService.mount(db_session, user, str(src), "s")
    WorkspaceService.sync_and_register(db_session, user, ws)
    again = WorkspaceService.sync_and_register(db_session, user, ws)

    assert again == []
    assert db_session.query(File).filter_by(owner_id=user.id, workspace_id=ws.id).count() == 1


def test_sync_and_register_picks_up_new_source_files(db_session, tmp_path, upload_dir_tmp):
    user = _make_user(db_session, "r3")
    src = tmp_path / "source"
    src.mkdir()
    (src / "a.csv").write_text("x\n1\n")

    ws = WorkspaceService.mount(db_session, user, str(src), "s")
    WorkspaceService.sync_and_register(db_session, user, ws)

    # 源目录新增文件后再次同步（聊天时自动触发）→ 增量登记
    (src / "b.csv").write_text("y\n2\n")
    new_files = WorkspaceService.sync_and_register(db_session, user, ws)

    assert [f.original_name for f in new_files] == ["b.csv"]
    assert db_session.query(File).filter_by(owner_id=user.id, workspace_id=ws.id).count() == 2
