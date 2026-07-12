"""
Agent Service 测试用例
测试 ReAct 循环、权限区分、Token 控制
"""
import pytest
from unittest.mock import AsyncMock, patch
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from services.agent_service import AgentService


class TestAgentServiceBasic:
    """基础 Agent 功能测试"""

    @pytest.mark.asyncio
    async def test_agent_single_step_answer(self, tmp_path):
        """
        场景: 用户问题简单，Agent 一轮就给出答案
        预期: 直接返回最终答案，不调用工具
        """
        # Mock LLM 响应 - 直接给出答案
        mock_llm_response = {
            "choices": [{
                "message": {
                    "content": "Thought: 这是一个简单问题\nAnswer: 答案是 42"
                }
            }],
            "usage": {"total_tokens": 100}
        }

        with patch('services.agent_service.llm_client.chat_completion',
                   new=AsyncMock(return_value=mock_llm_response)):

            agent = AgentService(working_dir=tmp_path)  # 空目录，避免幻觉检查误触发
            result = await agent.run(
                user=AsyncMock(id=1, role="user"),
                message="1+1等于几",
                file_names=[]
            )

            assert result["success"] is True
            assert result["answer"] == "答案是 42"
            assert len(result["steps"]) == 1
            assert result["steps"][0]["type"] == "final"

    @pytest.mark.asyncio
    async def test_agent_multi_step_with_glob(self, tmp_path):
        """
        场景: 管理员用户问"分析我的数据"
        预期: Agent 先 glob 发现文件，再读取分析
        """
        # 准备文件
        (tmp_path / "sales.csv").write_text("month,amount\nJan,100\nFeb,200")

        # Mock LLM - 第一轮调用 glob，第二轮给出答案
        responses = [
            {  # 第一轮: 要 glob
                "choices": [{
                    "message": {
                        "content": "Thought: 我需要先查看有哪些文件\nAction: glob\nAction Input: {\"pattern\": \"*.csv\"}"
                    }
                }],
                "usage": {"total_tokens": 50}
            },
            {  # 第二轮: 给出答案
                "choices": [{
                    "message": {
                        "content": "Thought: 找到了 sales.csv\nAnswer: 发现 sales.csv，包含 2 个月的数据"
                    }
                }],
                "usage": {"total_tokens": 80}
            }
        ]

        with patch('services.agent_service.llm_client.chat_completion',
                   new=AsyncMock(side_effect=responses)):

            agent = AgentService(working_dir=tmp_path)
            result = await agent.run(
                user=AsyncMock(id=1, role="admin"),
                message="分析我的数据",
                file_names=[]
            )

            assert result["success"] is True
            # steps: thought, action (glob), observation, final = 4 steps
            assert len(result["steps"]) == 4
            assert result["steps"][0]["type"] == "thought"
            assert result["steps"][1]["action"] == "glob"
            assert result["steps"][2]["type"] == "observation"
            assert result["steps"][3]["type"] == "final"

    @pytest.mark.asyncio
    async def test_user_with_file_selection(self, tmp_path):
        """
        场景: 普通用户选择了特定文件，要求分析
        预期: Agent 直接读取选定文件，不执行 glob
        """
        (tmp_path / "sales.csv").write_text("month,amount\nJan,100")
        (tmp_path / "secret.csv").write_text("机密数据")  # 不应该被访问

        mock_response = {
            "choices": [{
                "message": {
                    "content": "Thought: 用户选择了文件，我将读取它\nAction: read\nAction Input: {\"path\": \"sales.csv\", \"limit\": 50}"
                }
            }],
            "usage": {"total_tokens": 100}
        }

        with patch('services.agent_service.llm_client.chat_completion',
                   new=AsyncMock(return_value=mock_response)):

            agent = AgentService(working_dir=tmp_path)
            result = await agent.run(
                user=AsyncMock(id=1, role="user"),
                message="分析销售数据",
                file_names=["sales.csv"]
            )

            # 验证系统提示中不包含 glob 工具说明
            call_args = agent.llm_client.chat_completion.call_args
            messages = call_args[0][0]  # 第一个位置参数
            system_prompt = messages[0]["content"]

            # 普通用户不应该有 glob 工具描述
            assert "- glob:" not in system_prompt
            assert "- read:" in system_prompt
            assert "- exec:" not in system_prompt  # 普通用户也不能执行代码


class TestAgentPermissions:
    """权限测试"""

    @pytest.mark.asyncio
    async def test_admin_user_can_use_glob(self):
        """
        场景: 管理员用户的系统提示
        预期: 包含 glob 工具，允许自主探索
        """
        agent = AgentService()
        system_prompt = agent._build_system_prompt(role="admin", file_names=[])

        assert "- glob:" in system_prompt
        assert "你可以访问用户的所有文件" in system_prompt

    @pytest.mark.asyncio
    async def test_user_cannot_use_glob(self):
        """
        场景: 普通用户的系统提示
        预期: 不包含 glob 工具描述，只能读取指定文件
        """
        agent = AgentService()
        system_prompt = agent._build_system_prompt(role="user", file_names=["sales.csv", "products.csv"])

        assert "- glob:" not in system_prompt
        assert "- exec:" not in system_prompt
        assert "用户已选择以下文件可供分析" in system_prompt
        assert "sales.csv" in system_prompt and "products.csv" in system_prompt

    @pytest.mark.asyncio
    async def test_admin_user_has_all_tools(self):
        """
        场景: 管理员权限
        预期: 可以使用所有工具（glob, read, grep, stat, exec）
        """
        agent = AgentService()
        system_prompt = agent._build_system_prompt(role="admin", file_names=[])

        assert "- glob:" in system_prompt
        assert "- read:" in system_prompt
        assert "- exec:" in system_prompt


class TestAgentLoopControl:
    """Agent 循环控制测试"""

    @pytest.mark.asyncio
    async def test_max_iterations_limit(self):
        """
        场景: Agent 陷入循环，不停调用工具
        预期: 达到 MAX_ITERATIONS 后强制终止
        """
        # Mock LLM 永远返回 Action，不返回 Answer
        mock_response = {
            "choices": [{
                "message": {
                    "content": "Thought: 我需要更多信息\nAction: glob\nAction Input: {\"pattern\": \"*\"}"
                }
            }],
            "usage": {"total_tokens": 50}
        }

        with patch('services.agent_service.llm_client.chat_completion',
                   new=AsyncMock(return_value=mock_response)):

            agent = AgentService()
            agent.MAX_ITERATIONS = 3  # 测试时用小的限制

            result = await agent.run(
                user=AsyncMock(id=1, role="admin"),
                message="分析数据",
                file_names=[]
            )

            # 应该达到最大迭代次数后停止
            assert result["steps"][-1]["type"] == "error"
            assert "分析过程过长" in result["steps"][-1]["content"]

    @pytest.mark.asyncio
    async def test_tool_execution_error_handling(self):
        """
        场景: 工具执行失败（如文件不存在）
        预期: Agent 收到错误 observation，继续或报告错误
        """
        responses = [
            {  # 第一轮：尝试读取不存在的文件
                "choices": [{
                    "message": {
                        "content": "Thought: 让我读取文件\nAction: read\nAction Input: {\"path\": \"nonexistent.csv\"}"
                    }
                }],
                "usage": {"total_tokens": 50}
            },
            {  # 第二轮：收到错误后决定怎么做
                "choices": [{
                    "message": {
                        "content": "Thought: 文件不存在，让我查看有哪些文件\nAction: glob\nAction Input: {\"pattern\": \"*\"}"
                    }
                }],
                "usage": {"total_tokens": 60}
            },
            {  # 第三轮：给出答案
                "choices": [{
                    "message": {
                        "content": "Answer: 未找到指定文件，但目录下有..."
                    }
                }],
                "usage": {"total_tokens": 70}
            }
        ]

        with patch('services.agent_service.llm_client.chat_completion',
                   new=AsyncMock(side_effect=responses)):

            agent = AgentService()
            result = await agent.run(
                user=AsyncMock(id=1, role="admin"),
                message="读取文件",
                file_names=[]
            )

            # 验证错误被正确处理 - observation 步骤的 success 为 False
            assert any(step.get("type") == "observation" and step.get("success") is False
                      for step in result["steps"])


class TestAgentTokenControl:
    """Token 控制测试"""

    @pytest.mark.asyncio
    async def test_context_compression_triggered(self):
        """
        场景: 多轮对话后上下文超过限制
        预期: 自动触发压缩，摘要历史步骤
        """
        agent = AgentService()
        agent.CONTEXT_LIMIT = 500  # 设置低阈值便于测试

        # 构建一个长历史
        steps = []
        for i in range(20):
            steps.append({
                "step": i,
                "thought": "这是一个很长的思考过程 " * 50,  # 制造长文本
                "action": "read",
                "observation": {"content": "大量数据 " * 100}
            })

        compressed = agent._compress_context(steps)

        # 验证压缩逻辑
        assert len(compressed) <= 8  # 最近3个完整 + 前面摘要
        # 老步骤被摘要
        assert "summary" in compressed[0] or "thought_summary" in compressed[0]
        # 新步骤保留完整
        assert "thought" in compressed[-1]

    @pytest.mark.asyncio
    async def test_observation_truncation(self):
        """
        场景: 读取大文件返回大量数据
        预期: Observation 被截断，保留关键信息
        """
        agent = AgentService()

        # 模拟大文件读取结果
        large_content = "数据行\n" * 1000
        truncated = agent._truncate_observation(large_content, max_length=500)

        assert len(truncated) <= 550  # 有一定余量
        assert "[内容已截断]" in truncated or "[ truncated ]" in truncated


class TestAgentWithRealFiles:
    """集成测试 - 使用真实文件"""

    @pytest.mark.asyncio
    async def test_analyze_sales_data_workflow(self, tmp_path):
        """
        完整工作流测试：
        用户问"分析销售趋势"，Agent 应该：
        1. 发现 sales.csv
        2. 读取了解结构
        3. 执行 Python 分析
        4. 给出趋势结论
        """
        # 准备真实销售数据
        sales_data = """date,product,amount,quantity
2024-01-01,ProductA,1000,10
2024-02-01,ProductA,1200,12
2024-03-01,ProductA,1500,15
2024-01-01,ProductB,800,8
2024-02-01,ProductB,900,9
2024-03-01,ProductB,1100,11
"""
        (tmp_path / "sales.csv").write_text(sales_data)

        # 这里使用 mock 模拟 LLM 的合理响应序列
        # 实际测试可能需要更复杂的 mock 或使用真实 LLM

        # 简化：验证 Agent 可以正确执行工具链
        agent = AgentService(working_dir=tmp_path)

        # 手动模拟一个完整流程
        steps = []

        # Step 1: glob
        result = agent.tools["glob"].execute(pattern="*.csv")
        steps.append({
            "type": "action",
            "tool": "glob",
            "input": {"pattern": "*.csv"},
            "observation": result
        })
        assert "sales.csv" in result["files"]

        # Step 2: stat
        result = agent.tools["stat"].execute(path="sales.csv")
        steps.append({
            "type": "action",
            "tool": "stat",
            "observation": result
        })
        assert result["line_count"] == 7  # 6行数据 + 表头

        # Step 3: read
        result = agent.tools["read"].execute(path="sales.csv", limit=10)
        steps.append({
            "type": "action",
            "tool": "read",
            "observation": result
        })
        assert "ProductA" in str(result["lines"])

        # Step 4: exec 分析
        code = """
import pandas as pd
df = pd.read_csv('sales.csv')
monthly = df.groupby(df['date'].str[:7])['amount'].sum()
print("月度销售额:")
print(monthly)
trend = "上升" if monthly.iloc[-1] > monthly.iloc[0] else "下降"
print(f"\\n趋势: {trend}")
"""
        result = agent.tools["exec"].execute(command=code, type="python")
        steps.append({
            "type": "action",
            "tool": "exec",
            "observation": result
        })

        # 验证分析结果
        assert result["success"] is True
        assert "月度销售额" in result["output"]

        print(f"\n完整工作流执行了 {len(steps)} 步")
        for i, step in enumerate(steps):
            print(f"Step {i+1}: {step['tool']}")
