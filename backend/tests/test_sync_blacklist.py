"""同步黑名单 + /workspaces/{id}/sync 接口 + ensure_columns 迁移测试"""
import json
import os

import pytest

from config import settings
from models.file import File
from models.workspace import Workspace
from services.workspace_service import WorkspaceService


@pytest.fixture
def upload_dir_tmp(tmp_path, monkeypatch):
    d = tmp_path / "uploads"
    d.mkdir()
    monkeypatch.setattr(settings, "UPLOAD_DIR", d)
    return d


def _mount_with_file(db_session, user, tmp_path, filename="data.csv", content="a,b\n1,2\n"):
    src = tmp_path / "source"
    src.mkdir(exist_ok=True)
    (src / filename).write_text(content)
    ws = WorkspaceService.mount(db_session, user, str(src), "s")
    WorkspaceService.sync_and_register(db_session, user, ws)
    return ws, src


def test_sync_endpoint_registers_external(client, db_session, auth_headers_admin, tmp_path, upload_dir_tmp):
    from models.user import User
    user = db_session.query(User).filter_by(username="test_admin").first()
    src = tmp_path / "source"
    src.mkdir()
    (src / "a.csv").write_text("x\n1\n")
    ws = WorkspaceService.mount(db_session, user, str(src), "ext")

    r = client.post(f"/api/workspaces/{ws.id}/sync", headers=auth_headers_admin)
    assert r.status_code == 200
    assert r.json()["data"]["new_files"] == 1
    assert db_session.query(File).filter_by(workspace_id=ws.id).count() == 1

    # 再次同步：幂等，无新文件
    r = client.post(f"/api/workspaces/{ws.id}/sync", headers=auth_headers_admin)
    assert r.json()["data"]["new_files"] == 0


def test_sync_endpoint_internal_noop(client, db_session, auth_headers_admin, upload_dir_tmp):
    from models.user import User
    user = db_session.query(User).filter_by(username="test_admin").first()
    ws = WorkspaceService.get_or_create_internal(db_session, user)

    r = client.post(f"/api/workspaces/{ws.id}/sync", headers=auth_headers_admin)
    assert r.status_code == 200
    assert r.json()["data"]["new_files"] == 0


def test_delete_copy_file_adds_blacklist_and_skips_resync(
    client, db_session, auth_headers_admin, tmp_path, upload_dir_tmp
):
    from models.user import User
    user = db_session.query(User).filter_by(username="test_admin").first()
    ws, src = _mount_with_file(db_session, user, tmp_path)
    db_file = db_session.query(File).filter_by(workspace_id=ws.id).first()

    r = client.delete(f"/api/files/{db_file.id}", headers=auth_headers_admin)
    assert r.status_code == 200

    db_session.refresh(ws)
    exclusions = json.loads(ws.sync_exclusions)
    assert len(exclusions) == 1
    assert exclusions[0]["name"] == "data.csv"
    assert exclusions[0]["deleted_source_mtime"] is not None

    # 再次同步：黑名单文件不复制、不登记
    new_files = WorkspaceService.sync_and_register(db_session, user, ws)
    assert new_files == []
    assert db_session.query(File).filter_by(workspace_id=ws.id).count() == 0


def test_modified_source_file_leaves_blacklist_and_resyncs(
    client, db_session, auth_headers_admin, tmp_path, upload_dir_tmp
):
    from models.user import User
    user = db_session.query(User).filter_by(username="test_admin").first()
    ws, src = _mount_with_file(db_session, user, tmp_path)
    db_file = db_session.query(File).filter_by(workspace_id=ws.id).first()
    client.delete(f"/api/files/{db_file.id}", headers=auth_headers_admin)

    # 用户在源文件夹修改了该文件（mtime 变新）
    import time
    src_file = src / "data.csv"
    src_file.write_text("a,b,c\n1,2,3\n")
    future = time.time() + 3600
    os.utime(src_file, (future, future))

    new_files = WorkspaceService.sync_and_register(db_session, user, ws)
    assert len(new_files) == 1
    db_session.refresh(ws)
    assert json.loads(ws.sync_exclusions) == []


def test_internal_workspace_delete_no_blacklist(
    client, db_session, auth_headers_admin, tmp_path, upload_dir_tmp
):
    from models.user import User
    user = db_session.query(User).filter_by(username="test_admin").first()
    ws = WorkspaceService.get_or_create_internal(db_session, user)
    f = tmp_path / "manual.csv"
    f.write_text("x\n1\n")
    db_file = File(
        owner_id=user.id, filename="manual.csv", original_name="manual.csv",
        filepath=str(f), size=5, status="ready", workspace_id=ws.id,
    )
    db_session.add(db_file)
    db_session.commit()

    r = client.delete(f"/api/files/{db_file.id}", headers=auth_headers_admin)
    assert r.status_code == 200
    db_session.refresh(ws)
    assert json.loads(ws.sync_exclusions) == []


def test_ensure_columns_adds_missing_column(tmp_path, monkeypatch):
    from sqlalchemy import create_engine, inspect, text
    from models.base import ensure_columns

    eng = create_engine(f"sqlite:///{tmp_path}/old.db")
    with eng.begin() as conn:
        conn.execute(text("CREATE TABLE workspaces (id INTEGER PRIMARY KEY, name TEXT)"))

    monkeypatch.setattr("models.base.engine", eng)
    ensure_columns()

    cols = {c["name"] for c in inspect(eng).get_columns("workspaces")}
    assert "sync_exclusions" in cols

    # 幂等：重复执行不报错
    ensure_columns()
