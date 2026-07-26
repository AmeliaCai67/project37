"""沙箱内 openpyxl / mimetypes 初始化相关测试

打包产物中 openpyxl 会读取 /etc/apache2/mime.types，沙箱必须放行该路径，
否则 pd.read_excel 在 Agent exec 中无法使用。
"""
from pathlib import Path

import pandas as pd
import pytest

import core.sandbox
from core.sandbox import RestrictedPythonSandbox


def _patch_frozen(monkeypatch):
    """模拟 PyInstaller 冻结环境，强制走 multiprocessing spawn 路径。"""
    monkeypatch.setattr(core.sandbox, "_is_frozen", lambda: True)


def test_frozen_openpyxl_mimetypes_initialization(monkeypatch, tmp_path):
    """openpyxl 内部实例化 MimeTypes 时不应因 /etc/apache2/mime.types 被拦截而失败。"""
    _patch_frozen(monkeypatch)
    sb = RestrictedPythonSandbox(working_dir=tmp_path, output_dir=tmp_path / "out")
    result = sb.execute(
        "from openpyxl.packaging.manifest import MimeTypes\n"
        "m = MimeTypes()\n"
        "print('openpyxl mimetypes ok')"
    )
    assert result["success"] is True, result
    assert "openpyxl mimetypes ok" in result["output"]


def test_frozen_pandas_read_excel(monkeypatch, tmp_path):
    """frozen 沙箱内 pd.read_excel 应能正常读取工作目录下的 xlsx 文件。"""
    _patch_frozen(monkeypatch)
    work = tmp_path / "work"
    out = tmp_path / "out"
    work.mkdir()
    xlsx = work / "data.xlsx"
    with pd.ExcelWriter(xlsx, engine="openpyxl") as writer:
        pd.DataFrame({"A": [1, 2], "B": ["x", "y"]}).to_excel(writer, index=False)

    sb = RestrictedPythonSandbox(working_dir=work, output_dir=out)
    result = sb.execute(
        "import pandas as pd\n"
        "df = pd.read_excel('data.xlsx')\n"
        "print(df.shape)\n"
        "print(list(df.columns))"
    )
    assert result["success"] is True, result
    assert "(2, 2)" in result["output"]
    assert "'A'" in result["output"]
