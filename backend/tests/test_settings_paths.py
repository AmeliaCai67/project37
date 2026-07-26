from core import paths
from config.settings import Settings


def test_prod_settings_use_user_data_dir(monkeypatch, tmp_path):
    monkeypatch.setenv("ENV", "prod")
    monkeypatch.setattr(
        paths, "user_data_dir", lambda app, author: str(tmp_path / "p37")
    )
    s = Settings()
    assert "Project37" in str(s.UPLOAD_DIR) or str(tmp_path) in str(s.UPLOAD_DIR)
    assert "Project37" in s.DATABASE_URL or str(tmp_path) in s.DATABASE_URL
