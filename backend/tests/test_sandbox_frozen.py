from pathlib import Path
import sys

from core.sandbox import RestrictedPythonSandbox


def test_python_executable_falls_back_to_sys_executable_in_dev():
    sb = RestrictedPythonSandbox(working_dir=Path.cwd())
    assert sb._get_python_executable() == sys.executable


def test_sandbox_runs_simple_code(tmp_path):
    sb = RestrictedPythonSandbox(working_dir=tmp_path, output_dir=tmp_path / "out")
    result = sb.execute("print('hello')")
    assert result["success"] is True
    assert "hello" in result["output"]
