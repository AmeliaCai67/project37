from pathlib import Path
import sys

import core.sandbox
from core.sandbox import RestrictedPythonSandbox


def test_python_executable_falls_back_to_sys_executable_in_dev():
    sb = RestrictedPythonSandbox(working_dir=Path.cwd())
    assert sb._get_python_executable() == sys.executable


def test_sandbox_runs_simple_code(tmp_path):
    sb = RestrictedPythonSandbox(working_dir=tmp_path, output_dir=tmp_path / "out")
    result = sb.execute("print('hello')")
    assert result["success"] is True
    assert "hello" in result["output"]


def _patch_frozen(monkeypatch):
    """模拟 PyInstaller 冻结环境：execute() 应走 multiprocessing spawn 路径。"""
    # 不能 patch sys.frozen——multiprocessing 会据此构造 --multiprocessing-fork
    # 命令行（只有 PyInstaller bootloader 能识别）；改 patch sandbox 自身的判断函数。
    monkeypatch.setattr(core.sandbox, "_is_frozen", lambda: True)


def test_frozen_runs_simple_code(monkeypatch, tmp_path):
    _patch_frozen(monkeypatch)
    sb = RestrictedPythonSandbox(working_dir=tmp_path, output_dir=tmp_path / "out")
    result = sb.execute("print('hello frozen')")
    assert result["success"] is True
    assert "hello frozen" in result["output"]


def test_frozen_reads_working_dir_file(monkeypatch, tmp_path):
    _patch_frozen(monkeypatch)
    (tmp_path / "data.csv").write_text("a,b\n1,2\n", encoding="utf-8")
    sb = RestrictedPythonSandbox(working_dir=tmp_path, output_dir=tmp_path / "out")
    result = sb.execute("print(open('data.csv').read().strip())")
    assert result["success"] is True
    assert "a,b" in result["output"]


def test_frozen_blocks_outside_file(monkeypatch, tmp_path):
    _patch_frozen(monkeypatch)
    sb = RestrictedPythonSandbox(working_dir=tmp_path, output_dir=tmp_path / "out")
    result = sb.execute("open('/etc/passwd').read()")
    assert result["success"] is False
    assert result["error_type"] in ("permission_error", "file_error")


def test_frozen_error_classification(monkeypatch, tmp_path):
    _patch_frozen(monkeypatch)
    sb = RestrictedPythonSandbox(working_dir=tmp_path, output_dir=tmp_path / "out")
    result = sb.execute("1/0")
    assert result["success"] is False
    assert result["error_type"] == "runtime_error"
    assert "ZeroDivisionError" in result["error"]


def test_pathlib_methods_no_recursion(tmp_path):
    """回归：_OrigPath 是 Path 别名，补丁后调用原始方法曾导致无限递归。"""
    sb = RestrictedPythonSandbox(working_dir=tmp_path, output_dir=tmp_path / "out")
    result = sb.execute(
        "from pathlib import Path\n"
        "Path('sub/deep').mkdir(parents=True, exist_ok=True)\n"
        "print(Path('.').exists(), Path('.').is_dir())"
    )
    assert result["success"] is True
    assert "True True" in result["output"]


def test_frozen_pathlib_mkdir_no_recursion(monkeypatch, tmp_path):
    _patch_frozen(monkeypatch)
    sb = RestrictedPythonSandbox(working_dir=tmp_path, output_dir=tmp_path / "out")
    result = sb.execute(
        "from pathlib import Path\n"
        "Path('sub/deep').mkdir(parents=True, exist_ok=True)\n"
        "print('mkdir ok')"
    )
    assert result["success"] is True
    assert "mkdir ok" in result["output"]


def test_relative_write_error_guides_to_sandbox_output(tmp_path):
    """相对路径写入仍被拦截（保护源文件），但错误信息应引导到 /sandbox_output/。"""
    work = tmp_path / "work"
    out = tmp_path / "out"
    work.mkdir()
    sb = RestrictedPythonSandbox(working_dir=work, output_dir=out)
    result = sb.execute("with open('chart.txt', 'w') as f:\n    f.write('png-bytes')")
    assert result["success"] is False
    assert "/sandbox_output/" in result.get("stderr", "")
    assert not (work / "chart.txt").exists()


def test_mplconfig_write_allowed(tmp_path):
    """matplotlib 字体缓存目录允许写入（frozen 子进程将 MPLCONFIGDIR 指到这里）。"""
    work = tmp_path / "work"
    out = tmp_path / "out"
    work.mkdir()
    sb = RestrictedPythonSandbox(working_dir=work, output_dir=out)
    result = sb.execute(
        "from pathlib import Path\n"
        "Path('.mplconfig').mkdir(exist_ok=True)\n"
        "p = Path('.mplconfig') / 'fontlist.json'\n"
        "with open(str(p.absolute()), 'w') as f:\n"
        "    f.write('{}')\n"
        "print('cache ok')"
    )
    assert result["success"] is True
    assert "cache ok" in result["output"]


def test_frozen_timeout(monkeypatch, tmp_path):
    _patch_frozen(monkeypatch)
    sb = RestrictedPythonSandbox(working_dir=tmp_path, output_dir=tmp_path / "out", timeout=2)
    result = sb.execute("while True: pass")
    assert result["success"] is False
    assert result["error"] == "执行超时"
