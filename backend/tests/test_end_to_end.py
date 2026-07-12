"""
端到端测试
模拟完整用户使用场景
"""
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch
import json


class TestEndToEndUser:
    """普通用户完整使用流程"""

    def test_user_analyze_selected_file(self, client, auth_headers_user):
        """
        场景: 普通用户选择文件并要求分析

        流程:
        1. 用户登录
        2. 选择文件（file_ids=[1]）
        3. 提问"分析这个销售数据"
        4. AI 直接读取指定文件
        5. 给出分析结果

        预期: AI 不执行 glob，只读取用户指定的文件
        """
        # Mock LLM 响应
        mock_responses = [
            {
                "choices": [{
                    "message": {
                        "content": "Thought: 用户指定了文件，我将读取它\nAction: read\nAction Input: {\"path\": \"sales.csv\", \"limit\": 100}"
                    }
                }],
                "usage": {"total_tokens": 80}
            },
            {
                "choices": [{
                    "message": {
                        "content": "Thought: 基于数据分析\nAnswer: 销售数据显示 Q1 增长 15%..."
                    }
                }],
                "usage": {"total_tokens": 120}
            }
        ]

        with patch('services.agent_service.llm_client.chat_completion',
                   new=AsyncMock(side_effect=mock_responses)):

            response = client.post(
                "/api/chat/send",
                headers=auth_headers_user,
                json={
                    "message": "分析销售数据",
                    "file_ids": [1]
                }
            )

            assert response.status_code == 200
            data = response.json()
            assert data["code"] == 200
            assert "Q1 增长" in data["data"]["response"]

    @pytest.mark.skip(reason="待实现：需要完整的数据库 fixture 和文件上传流程")
    def test_user_cannot_glob(self, client, auth_headers_user):
        """
        场景: 普通用户的 AI 尝试执行 glob

        预期: 系统提示中不包含 glob 工具，AI 不应该发起 glob 请求
        """
        pass


class TestEndToEndAdmin:
    """管理员用户完整使用流程"""

    def test_admin_explore_and_analyze(self, client, auth_headers_admin):
        """
        场景: 管理员上传多个文件，要求综合分析

        流程:
        1. 上传 sales.csv, products.csv, customers.csv
        2. 提问"分析我的业务数据"
        3. AI 执行 glob 发现所有文件
        4. AI 选择性读取相关文件
        5. AI 执行关联分析
        6. 给出综合报告
        """
        # Mock LLM 响应序列
        mock_responses = [
            {  # Step 1: 发现文件
                "choices": [{
                    "message": {
                        "content": "Thought: 让我先看看有哪些文件\nAction: glob\nAction Input: {\"pattern\": \"*.csv\"}"
                    }
                }],
                "usage": {"total_tokens": 50}
            },
            {  # Step 2: 查看 sales 文件结构
                "choices": [{
                    "message": {
                        "content": "Thought: 找到了 sales.csv，让我了解结构\nAction: stat\nAction Input: {\"path\": \"sales.csv\"}"
                    }
                }],
                "usage": {"total_tokens": 60}
            },
            {  # Step 3: 读取 sales 数据
                "choices": [{
                    "message": {
                        "content": "Thought: 文件不大，读取全部内容\nAction: read\nAction Input: {\"path\": \"sales.csv\"}"
                    }
                }],
                "usage": {"total_tokens": 70}
            },
            {  # Step 4: 执行分析
                "choices": [{
                    "message": {
                        "content": "Thought: 现在执行数据分析\nAction: exec\nAction Input: {\"command\": \"import pandas as pd; ...\", \"type\": \"python\"}"
                    }
                }],
                "usage": {"total_tokens": 80}
            },
            {  # Step 5: 给出答案
                "choices": [{
                    "message": {
                        "content": "Answer: 基于分析，您的业务呈现以下趋势：1. Q1 销售额增长 15%..."
                    }
                }],
                "usage": {"total_tokens": 200}
            }
        ]

        with patch('services.agent_service.llm_client.chat_completion',
                   new=AsyncMock(side_effect=mock_responses)):

            response = client.post(
                "/api/chat/send",
                headers=auth_headers_admin,
                json={
                    "message": "分析我的业务数据",
                    "file_ids": []
                }
            )

            assert response.status_code == 200
            data = response.json()
            assert data["code"] == 200
            # 当前 Agent 每轮会生成 thought/action/observation 等多个步骤，
            # 因此只保证步骤数不少于 mock 的 LLM 调用次数即可
            assert len(data["data"]["steps"]) >= 5

    def test_admin_streaming_analysis(self, client, auth_headers_admin):
        """
        场景: 管理员使用流式接口

        预期: 实时看到 AI 的思考过程
        """
        with client.stream(
            "POST",
            "/api/chat/send/stream",
            headers=auth_headers_admin,
            json={"message": "分析数据"}
        ) as response:

            assert response.status_code == 200

            # 验证 SSE 流
            events = []
            for line in response.iter_lines():
                if line:
                    line_str = line if isinstance(line, str) else line.decode('utf-8')
                    events.append(line_str)

        # 应该包含多个事件
        assert len(events) > 0
        # 最后是 [DONE]
        assert events[-1] == "data: [DONE]"


class TestEndToEndErrorScenarios:
    """错误场景端到端测试"""

    def test_file_not_found_during_analysis(self, client, auth_headers_admin):
        """
        场景: AI 尝试读取已删除的文件

        流程:
        1. Agent 开始分析
        2. 用户删除了正在分析的文件
        3. Agent read 失败
        4. Agent 应该优雅处理错误并告知用户
        """
        mock_responses = [
            {
                "choices": [{
                    "message": {
                        "content": "Thought: 读取文件\nAction: read\nAction Input: {\"path\": \"deleted.csv\"}"
                    }
                }],
                "usage": {"total_tokens": 50}
            },
            {
                "choices": [{
                    "message": {
                        "content": "Thought: 文件不存在，让我查看还有哪些文件可用\nAction: glob\nAction Input: {\"pattern\": \"*\"}"
                    }
                }],
                "usage": {"total_tokens": 60}
            },
            {
                "choices": [{
                    "message": {
                        "content": "Answer: 抱歉，您指定的文件已被删除。目前可用文件有..."
                    }
                }],
                "usage": {"total_tokens": 80}
            }
        ]

        with patch('services.agent_service.llm_client.chat_completion',
                   new=AsyncMock(side_effect=mock_responses)):

            response = client.post(
                "/api/chat/send",
                headers=auth_headers_admin,
                json={"message": "分析 deleted.csv"}
            )

            assert response.status_code == 200

    @pytest.mark.skip(reason="待实现：需要完整的 sandbox 错误场景 fixture")
    def test_sandbox_code_error(self, client, auth_headers_admin):
        """
        场景: AI 生成的分析代码有语法错误

        预期: Sandbox 返回错误，Agent 应该重试或告知用户
        """
        pass

    def test_llm_timeout(self, client, auth_headers_admin):
        """
        场景: LLM API 超时

        预期: 返回友好错误信息
        """
        with patch('services.agent_service.llm_client.chat_completion',
                   side_effect=TimeoutError("LLM API timeout")):

            response = client.post(
                "/api/chat/send",
                headers=auth_headers_admin,
                json={"message": "分析数据"}
            )

            # 当前实现遇到 LLM 异常会返回 200 并给出友好的兜底回复
            assert response.status_code == 200
            assert "抱歉" in response.json()["data"]["response"]


class TestEndToEndComplexAnalysis:
    """复杂分析场景"""

    def test_multi_file_join_analysis(self, client, auth_headers_admin):
        """
        场景: 需要关联多个文件进行分析

        例如：
        - sales.csv (订单数据)
        - products.csv (产品信息)
        - customers.csv (客户信息)

        分析：各地区各产品类别的销售额

        预期: AI 读取多个文件，执行 join 分析
        """
        mock_responses = [
            {  # 发现所有文件
                "choices": [{
                    "message": {
                        "content": "Thought: 发现所有 CSV 文件\nAction: glob\nAction Input: {\"pattern\": \"*.csv\"}"
                    }
                }],
                "usage": {"total_tokens": 50}
            },
            {  # 读取 sales
                "choices": [{
                    "message": {
                        "content": "Thought: 读取销售数据\nAction: read\nAction Input: {\"path\": \"sales.csv\", \"limit\": 50}"
                    }
                }],
                "usage": {"total_tokens": 60}
            },
            {  # 读取 products
                "choices": [{
                    "message": {
                        "content": "Thought: 读取产品信息\nAction: read\nAction Input: {\"path\": \"products.csv\"}"
                    }
                }],
                "usage": {"total_tokens": 60}
            },
            {  # 执行关联分析
                "choices": [{
                    "message": {
                        "content": "Thought: 执行关联分析\nAction: exec\nAction Input: {\"command\": \"import pandas as pd; sales = pd.read_csv('sales.csv'); products = pd.read_csv('products.csv'); merged = sales.merge(products, on='product_id'); result = merged.groupby(['region', 'category'])['amount'].sum(); print(result)\", \"type\": \"python\"}"
                    }
                }],
                "usage": {"total_tokens": 100}
            },
            {  # 给出答案
                "choices": [{
                    "message": {
                        "content": "Answer: 各区域各品类销售额分析：华东-电子产品: 50000..."
                    }
                }],
                "usage": {"total_tokens": 150}
            }
        ]

        with patch('services.agent_service.llm_client.chat_completion',
                   new=AsyncMock(side_effect=mock_responses)):

            response = client.post(
                "/api/chat/send",
                headers=auth_headers_admin,
                json={"message": "分析各区域各品类销售额"}
            )

            assert response.status_code == 200
            data = response.json()
            assert "华东" in data["data"]["response"]

    @pytest.mark.skip(reason="待实现：需要创建大文件测试 fixture")
    def test_large_file_partial_read(self, client, auth_headers_admin):
        """
        场景: 文件非常大（100MB CSV）

        预期: AI 不会一次性读取，而是：
        1. stat 查看结构
        2. read 前 N 行了解结构
        3. grep 查找特定时间段
        4. exec 用 pandas 做聚合（pandas 可以处理大文件）
        """
        pass


class TestEndToEndConversation:
    """对话上下文测试"""

    @pytest.mark.skip(reason="待实现：需要完整的多轮对话 fixture")
    def test_conversation_context_preserved(self, client, auth_headers_admin):
        """
        场景: 多轮对话，上下文应该被保留

        流程:
        1. 用户: "分析销售数据"
        2. AI: 分析 sales.csv
        3. 用户: "那环比呢？"（指代上一轮的销售数据）
        4. AI: 应该记住我们在讨论 sales.csv，直接计算环比
        """
        pass

    @pytest.mark.skip(reason="待实现：需要完整的多轮对话 fixture")
    def test_new_conversation_no_context(self, client, auth_headers_admin):
        """
        场景: 新对话不应该有旧上下文

        预期: 新对话从头开始分析
        """
        pass
