"""测试 external workspace 卸载后重新挂载，孤儿 File 记录能被重新关联"""
from pathlib import Path

from models.file import File
from models.workspace import Workspace
from services.workspace_service import WorkspaceService


def test_reregister_orphan_files_after_workspace_remount(
    db_session, mock_user, tmp_path, monkeypatch
):
    """
    场景：挂载 external 空间 -> sync 生成 File 记录 -> 卸载空间 -> 重新挂载同目录。
    SQLite 会复用 workspace id，副本目录路径相同；旧 File 记录的 workspace_id
    被 unmount 置为 NULL 后，再次 sync 应被重新关联到当前 workspace。
    """
    db = db_session
    user = mock_user()

    source = tmp_path / "source"
    source.mkdir()
    (source / "data.csv").write_text("a,b\n1,2\n", encoding="utf-8")

    # 把副本目录重定向到 tmp_path，避免测试污染真实 uploads 目录
    copy_base = tmp_path / "mounts"

    def _fake_copy_dir(user_id, workspace_id):
        p = copy_base / str(workspace_id)
        p.mkdir(parents=True, exist_ok=True)
        return p

    monkeypatch.setattr(
        WorkspaceService, "get_internal_copy_dir", staticmethod(_fake_copy_dir)
    )

    # 第一次挂载并同步
    ws1 = WorkspaceService.mount(db, user, str(source), "test")
    WorkspaceService.sync_and_register(db, user, ws1)
    files_before = db.query(File).filter(File.workspace_id == ws1.id).all()
    assert len(files_before) == 1

    # 卸载：File.workspace_id 被置为 NULL
    WorkspaceService.unmount(db, user, ws1.id)
    orphan = db.query(File).filter(
        File.owner_id == user.id, File.workspace_id == None
    ).first()
    assert orphan is not None
    assert orphan.filename == "data.csv"

    # 模拟 SQLite 复用 workspace id：直接创建新的同名 workspace id
    # （在真实 SQLite 无 AUTOINCREMENT 时，删除最大 id 后会复用）
    ws2 = Workspace(
        id=ws1.id,
        owner_id=user.id,
        name="test",
        type="external",
        source_path=str(source),
        output_path=str(tmp_path / "out"),
    )
    db.add(ws2)
    db.commit()
    db.refresh(ws2)

    # 重新挂载同目录后 sync，孤儿记录应被重新关联
    WorkspaceService.sync_and_register(db, user, ws2)
    files_after = db.query(File).filter(File.workspace_id == ws2.id).all()
    assert len(files_after) == 1
    assert files_after[0].filename == "data.csv"
