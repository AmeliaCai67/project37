import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


def test_health_and_static_mount_in_prod(tmp_path):
    """在子进程中以 ENV=prod 启动应用，验证 health 接口与静态文件挂载。"""
    dist_dir = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
    if not (dist_dir / "index.html").exists():
        pytest.skip("frontend/dist/index.html not found")

    env = os.environ.copy()
    env["ENV"] = "prod"
    script = """
import json, logging, sys
sys.path.insert(0, '.')
logging.basicConfig(level=logging.ERROR)
from fastapi.testclient import TestClient
from main import app
client = TestClient(app)
result = {
    "env": client.get('/health').json()['env'],
    "index_status": client.get('/').status_code,
    # SPA 回退：前端 history 路由（如 /setup）应返回 index.html
    "spa_status": client.get('/setup').status_code,
    "spa_is_html": b'id="app"' in client.get('/setup').content,
    # 未知 API 路径仍应返回 404，不回退到前端
    "api_404": client.get('/api/nonexistent').status_code,
}
print(json.dumps(result))
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=str(Path(__file__).resolve().parent.parent),
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout.strip().splitlines()[-1])
    assert data["env"] == "prod"
    assert data["index_status"] == 200
    assert data["spa_status"] == 200
    assert data["spa_is_html"] is True
    assert data["api_404"] == 404
