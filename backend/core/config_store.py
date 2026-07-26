import secrets
from pathlib import Path

from core.paths import get_app_data_dir, get_user_env_file

DEFAULT_ENV_TEMPLATE = """# Project37 用户配置
ENV=prod
APP_MODE=personal
LLM_PROVIDER=deepseek
LLM_API_KEY=
LLM_BASE_URL=
LLM_MODEL=deepseek-chat
LOG_LEVEL=INFO
"""


def ensure_user_config() -> Path:
    """确保用户数据目录与 .env 存在；首次运行时自动生成 SECRET_KEY。"""
    get_app_data_dir().mkdir(parents=True, exist_ok=True)
    env_file = get_user_env_file()
    if not env_file.exists():
        secret = secrets.token_urlsafe(64)
        content = f"SECRET_KEY={secret}\n{DEFAULT_ENV_TEMPLATE}"
        env_file.write_text(content, encoding="utf-8")
    else:
        text = env_file.read_text(encoding="utf-8")
        if "SECRET_KEY" not in text:
            secret = secrets.token_urlsafe(64)
            env_file.write_text(f"SECRET_KEY={secret}\n{text}", encoding="utf-8")
    return env_file


def load_user_env() -> dict:
    env_file = get_user_env_file()
    if not env_file.exists():
        return {}
    result = {}
    for line in env_file.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        result[key.strip()] = value.strip()
    return result


def update_user_config(values: dict) -> Path:
    """更新用户 .env 中的键值；不存在的键会追加到末尾。"""
    env_file = ensure_user_config()
    lines = env_file.read_text(encoding="utf-8").splitlines(keepends=True)
    keys_seen = set()
    new_lines = []
    for line in lines:
        if "=" in line and not line.strip().startswith("#"):
            key = line.split("=", 1)[0].strip()
            if key in values:
                new_lines.append(f"{key}={values[key]}\n")
                keys_seen.add(key)
                continue
        new_lines.append(line)
    for key, value in values.items():
        if key not in keys_seen:
            new_lines.append(f"{key}={value}\n")
    env_file.write_text("".join(new_lines), encoding="utf-8")
    return env_file


def has_api_key() -> bool:
    return bool(load_user_env().get("LLM_API_KEY"))
