import os
import sys
from pathlib import Path
from typing import Optional

from platformdirs import user_data_dir

APP_NAME = "Project37"
APP_AUTHOR = "Project37"


def is_frozen() -> bool:
    return getattr(sys, "frozen", False)


def get_meipass() -> Optional[Path]:
    if is_frozen():
        return Path(getattr(sys, "_MEIPASS"))
    return None


def get_project_base_dir() -> Path:
    """返回项目根目录。PyInstaller 环境下为 _MEIPASS，开发环境下为仓库根目录。"""
    if is_frozen():
        return get_meipass()
    # backend/core/paths.py -> backend/core -> backend -> project root
    return Path(__file__).resolve().parent.parent.parent


def get_app_data_dir() -> Path:
    """返回应用数据目录（打包/生产模式下使用平台用户目录，开发模式下使用 local_data）。"""
    if is_frozen() or os.environ.get("ENV") == "prod":
        p = Path(user_data_dir(APP_NAME, APP_AUTHOR))
    else:
        p = get_project_base_dir() / "local_data"
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_frontend_dist_dir() -> Optional[Path]:
    """查找前端构建产物目录。"""
    candidates = [
        get_project_base_dir() / "frontend" / "dist",
        get_project_base_dir() / "dist",
    ]
    for c in candidates:
        if (c / "index.html").exists():
            return c
    return None


def get_user_env_file() -> Path:
    return get_app_data_dir() / ".env"
