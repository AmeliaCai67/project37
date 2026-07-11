"""
沙箱写权限控制测试
验证 write 操作只能发生在 output_dir，read 操作限制在 working_dir
"""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.sandbox import RestrictedPythonSandbox


def test_cannot_write_source_file(tmp_path):
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    (source_dir / "data.csv").write_text("x\n1\n")

    sandbox = RestrictedPythonSandbox(
        working_dir=str(source_dir),
        output_dir=str(output_dir)
    )

    code = """
with open('data.csv', 'w') as f:
    f.write('hacked')
"""
    result = sandbox.execute(code)
    assert result["success"] is False
    assert "PermissionError" in result.get("stderr", "") or "Cannot write" in result.get("stderr", "")


def test_can_write_to_output_dir(tmp_path):
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    output_dir = tmp_path / "output"
    output_dir.mkdir()

    sandbox = RestrictedPythonSandbox(
        working_dir=str(source_dir),
        output_dir=str(output_dir)
    )

    code = """
with open('/output/result.txt', 'w') as f:
    f.write('hello')
"""
    result = sandbox.execute(code)
    assert result["success"] is True
    assert (output_dir / "result.txt").read_text() == "hello"
