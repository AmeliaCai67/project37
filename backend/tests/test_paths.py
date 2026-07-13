from pathlib import Path

from core import paths


def test_project_base_dir_exists():
    assert paths.get_project_base_dir().exists()


def test_app_data_dir_under_user_data_in_prod(monkeypatch, tmp_path):
    monkeypatch.setenv("ENV", "prod")
    monkeypatch.setattr(
        paths, "user_data_dir", lambda app, author: str(tmp_path / "data")
    )
    d = paths.get_app_data_dir()
    assert "Project37" in str(d) or str(tmp_path) in str(d)
    assert d.exists()


def test_user_env_file_path():
    env_file = paths.get_user_env_file()
    assert env_file.name == ".env"
    assert env_file.parent == paths.get_app_data_dir()
