from pathlib import Path
from services.output_artifact_service import OutputArtifactService
from models.workspace import Workspace
from models.user import User


def test_record_artifact(db_session, tmp_path):
    user = User(username="oa1", hashed_password="x", role="admin")
    db_session.add(user)
    db_session.commit()

    ws = Workspace(owner_id=user.id, name="ws", type="internal", output_path=str(tmp_path / "out"))
    db_session.add(ws)
    db_session.commit()

    out_dir = tmp_path / "out" / "2026-07-31"
    out_dir.mkdir(parents=True)
    (out_dir / "report.md").write_text("# 分析")

    arts = OutputArtifactService.scan_and_record(db_session, ws, out_dir)
    assert len(arts) == 1
    assert arts[0].filename == "report.md"
    assert arts[0].artifact_type == "report"


def test_get_output_date_dir(db_session, tmp_path):
    user = User(username="oa2", hashed_password="x", role="admin")
    db_session.add(user)
    db_session.commit()

    ws = Workspace(owner_id=user.id, name="ws", type="internal", output_path=str(tmp_path / "out"))
    db_session.add(ws)
    db_session.commit()

    d = OutputArtifactService.get_output_date_dir(ws)
    assert str(d).startswith(str(tmp_path / "out"))
    assert len(d.name.split("-")) == 3
