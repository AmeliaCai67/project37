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
with open('/sandbox_output/result.txt', 'w') as f:
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


def test_pathlib_write_text_blocked(tmp_path):
    """pathlib.Path.write_text 不应绕过沙箱写限制"""
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    (source_dir / "data.csv").write_text("original\n")

    sandbox = RestrictedPythonSandbox(
        working_dir=str(source_dir),
        output_dir=str(output_dir)
    )

    code = """
from pathlib import Path
Path('data.csv').write_text('hacked')
"""
    result = sandbox.execute(code)
    assert result["success"] is False
    assert (source_dir / "data.csv").read_text() == "original\n"


def test_pathlib_open_write_blocked(tmp_path):
    """pathlib.Path.open('w') 不应绕过沙箱写限制"""
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    (source_dir / "data.csv").write_text("original\n")

    sandbox = RestrictedPythonSandbox(
        working_dir=str(source_dir),
        output_dir=str(output_dir)
    )

    code = """
from pathlib import Path
with Path('data.csv').open('w') as f:
    f.write('hacked')
"""
    result = sandbox.execute(code)
    assert result["success"] is False
    assert (source_dir / "data.csv").read_text() == "original\n"


def test_pandas_to_csv_blocked(tmp_path):
    """pandas.DataFrame.to_csv 不应绕过沙箱写限制"""
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    (source_dir / "data.csv").write_text("original\n")

    sandbox = RestrictedPythonSandbox(
        working_dir=str(source_dir),
        output_dir=str(output_dir)
    )

    code = """
import pandas as pd
df = pd.DataFrame({'a': [1]})
df.to_csv('data.csv', index=False)
"""
    result = sandbox.execute(code)
    assert result["success"] is False
    assert "original" in (source_dir / "data.csv").read_text()
