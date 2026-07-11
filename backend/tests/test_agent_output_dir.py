"""
AgentService / ExecTool output_dir 透传测试
验证 Agent 能够将输出目录传递给沙箱，使 exec 工具只能写入 output_dir。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from services.agent_service import AgentService
from core.tools import ExecTool


def test_agent_service_accepts_output_dir(tmp_path):
    """AgentService 应接受并保存 output_dir"""
    source = tmp_path / "source"
    source.mkdir()
    output = tmp_path / "output"
    output.mkdir()
    (source / "data.csv").write_text("x,y\n1,2\n")

    agent = AgentService(
        working_dir=source,
        output_dir=output,
    )
    assert agent.working_dir == source
    assert agent.output_dir == output


def test_exec_tool_accepts_output_dir(tmp_path):
    """ExecTool 应接受 output_dir 并允许写入该目录"""
    output = tmp_path / "output"
    output.mkdir()

    tool = ExecTool(working_dir=tmp_path, output_dir=output)
    result = tool.execute(
        command="with open('/output/result.txt', 'w') as f: f.write('hello')",
        type="python",
    )

    assert result["success"] is True
    assert (output / "result.txt").read_text() == "hello"


def test_exec_tool_without_output_dir_denies_write(tmp_path):
    """ExecTool 未提供 output_dir 时应拒绝写入"""
    tool = ExecTool(working_dir=tmp_path)
    result = tool.execute(
        command="with open('result.txt', 'w') as f: f.write('hello')",
        type="python",
    )

    assert result["success"] is False
    assert "权限" in result["error"] or "PermissionError" in result["error"]
