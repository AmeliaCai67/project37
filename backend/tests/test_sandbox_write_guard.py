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


def test_cannot_read_sibling_directory(tmp_path):
    """工作目录前缀相同但不能读取兄弟目录（如 /tmp/source2 不是 /tmp/source 的子目录）"""
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    sibling_dir = tmp_path / "source2"
    sibling_dir.mkdir()
    (sibling_dir / "secret.txt").write_text("secret")

    sandbox = RestrictedPythonSandbox(working_dir=str(source_dir))

    code = f"""
with open('{sibling_dir}/secret.txt', 'r') as f:
    print(f.read())
"""
    result = sandbox.execute(code)
    assert result["success"] is False
    assert "PermissionError" in result.get("stderr", "") or "权限" in result.get("error", "")


def test_output_virtual_path_strict_prefix(tmp_path):
    """/output_file.txt 不应被误映射到 output_dir"""
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    output_dir = tmp_path / "output"
    output_dir.mkdir()

    sandbox = RestrictedPythonSandbox(
        working_dir=str(source_dir),
        output_dir=str(output_dir)
    )

    code = """
with open('/output_file.txt', 'w') as f:
    f.write('hacked')
"""
    result = sandbox.execute(code)
    assert result["success"] is False
    assert "Cannot write outside output directory" in result.get("stderr", "")
