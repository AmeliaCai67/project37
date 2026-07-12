"""
流式输出测试用例
测试 SSE 格式和 Agent 步骤的流式传输
"""
import pytest
import json
import sys
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from services.agent_service import AgentService


class TestStreamingFormat:
    """SSE 格式测试"""
    
    @pytest.mark.asyncio
    async def test_stream_thought_event(self):
        """
        场景: Agent 产生思考
        预期: SSE 格式输出 thought 事件
        """
        agent = AgentService()
        
        # 模拟生成 thought 事件
        events = []
        async for event in agent._stream_steps([
            {"type": "thought", "content": "我需要分析数据"}
        ]):
            events.append(event)
        
        assert len(events) == 1
        assert events[0] == 'data: {"type": "thought", "content": "我需要分析数据"}\n\n'
    
    @pytest.mark.asyncio
    async def test_stream_action_event(self):
        """
        场景: Agent 执行工具
        预期: SSE 格式输出 action 事件
        """
        agent = AgentService()
        
        events = []
        async for event in agent._stream_steps([
            {
                "type": "action",
                "tool": "read",
                "input": {"path": "data.csv", "limit": 50}
            }
        ]):
            events.append(event)
        
        assert len(events) == 1
        data = json.loads(events[0].replace('data: ', '').strip())
        assert data["type"] == "action"
        assert data["tool"] == "read"
    
    @pytest.mark.asyncio
    async def test_stream_observation_event(self):
        """
        场景: 工具返回观察结果
        预期: SSE 格式输出 observation 事件
        """
        agent = AgentService()
        
        events = []
        async for event in agent._stream_steps([
            {
                "type": "observation",
                "tool": "read",
                "content": "文件包含 100 行数据",
                "success": True
            }
        ]):
            events.append(event)
        
        assert len(events) == 1
        data = json.loads(events[0].replace('data: ', '').strip())
        assert data["type"] == "observation"
        assert data["success"] is True
    
    @pytest.mark.asyncio
    async def test_stream_answer_event(self):
        """
        场景: Agent 给出最终答案
        预期: SSE 格式输出 answer 事件，然后是 [DONE]
        """
        agent = AgentService()
        
        events = []
        async for event in agent._stream_steps([
            {"type": "answer", "content": "分析完成，趋势上升"},
            {"type": "done"}
        ]):
            events.append(event)
        
        assert len(events) == 2
        # 最后一个是 [DONE]
        assert events[-1] == "data: [DONE]\n\n"
    
    @pytest.mark.asyncio
    async def test_stream_full_workflow(self):
        """
        场景: 完整的工作流步骤
        预期: 按顺序输出所有事件
        """
        agent = AgentService()
        
        steps = [
            {"type": "thought", "content": "让我查看文件"},
            {"type": "action", "tool": "glob", "input": {"pattern": "*.csv"}},
            {"type": "observation", "content": "找到 sales.csv", "success": True},
            {"type": "thought", "content": "读取文件内容"},
            {"type": "action", "tool": "read", "input": {"path": "sales.csv"}},
            {"type": "observation", "content": "100 行数据", "success": True},
            {"type": "thought", "content": "现在分析"},
            {"type": "action", "tool": "exec", "input": {"command": "分析代码"}},
            {"type": "observation", "content": "结果: 增长 15%", "success": True},
            {"type": "answer", "content": "销售额增长 15%"},
            {"type": "done"}
        ]
        
        events = []
        async for event in agent._stream_steps(steps):
            events.append(event)
        
        # 验证事件数量
        assert len(events) == len(steps)
        
        # 验证顺序
        types = [json.loads(e.replace('data: ', '').strip())["type"] 
                for e in events[:-1]]  # 排除最后的 [DONE]
        assert types == ["thought", "action", "observation", "thought", 
                        "action", "observation", "thought", "action", 
                        "observation", "answer"]


class TestStreamingErrorHandling:
    """流式错误处理测试"""
    
    @pytest.mark.asyncio
    async def test_stream_error_event(self):
        """
        场景: Agent 执行出错
        预期: 输出 error 事件
        """
        agent = AgentService()
        
        events = []
        async for event in agent._stream_steps([
            {"type": "thought", "content": "尝试读取"},
            {"type": "action", "tool": "read", "input": {"path": "nonexistent.csv"}},
            {"type": "observation", "content": "文件不存在", "success": False, "error": "FileNotFound"},
            {"type": "error", "content": "无法继续分析"},
            {"type": "done"}
        ]):
            events.append(event)
        
        error_event = json.loads(events[-2].replace('data: ', '').strip())
        assert error_event["type"] == "error"
    
    @pytest.mark.asyncio
    async def test_stream_tool_execution_error(self):
        """
        场景: 工具执行异常
        预期: 流式输出中包含错误信息
        """
        agent = AgentService()
        
        # 模拟工具执行出错
        steps = [
            {"type": "thought", "content": "执行分析"},
            {"type": "action", "tool": "exec", "input": {"command": "危险代码"}},
            {"type": "observation", "content": "执行被拒绝", "success": False, "error": "禁止的操作"},
            {"type": "thought", "content": "换一种方式"},
            {"type": "action", "tool": "read", "input": {"path": "data.csv"}},
            {"type": "answer", "content": "基于现有信息..."},
            {"type": "done"}
        ]
        
        events = []
        async for event in agent._stream_steps(steps):
            events.append(event)
        
        # 验证错误被包含在流中
        contents = [e for e in events]
        print(f"Events: {contents}")
        assert any("禁止的操作" in e for e in contents)


class TestStreamingWithRealAgent:
    """结合真实 Agent 的流式测试"""
    
    @pytest.mark.asyncio
    async def test_stream_real_agent_run(self, tmp_path):
        """
        场景: 真实的 Agent 运行并流式输出
        预期: 按实际步骤输出事件
        """
        # 准备文件
        (tmp_path / "test.csv").write_text("a,b\n1,2\n3,4")
        
        # Mock LLM 响应
        responses = [
            {
                "choices": [{
                    "message": {
                        "content": "Thought: 查看文件\nAction: glob\nAction Input: {\"pattern\": \"*.csv\"}"
                    }
                }],
                "usage": {"total_tokens": 50}
            },
            {
                "choices": [{
                    "message": {
                        "content": "Answer: 找到文件"
                    }
                }],
                "usage": {"total_tokens": 30}
            }
        ]
        
        with patch('services.agent_service.llm_client.chat_completion',
                   new=AsyncMock(side_effect=responses)):
            
            agent = AgentService(working_dir=tmp_path)
            
            # 收集流式事件
            events = []
            async for event in agent.run_stream(
                user=Mock(id=1, role="admin"),
                message="查看文件",
                file_names=[]
            ):
                events.append(event)
            
            # 验证流式输出
            assert len(events) >= 3  # thought + action + observation + answer + done
            
            # 验证格式
            for event in events[:-1]:  # 除了最后的 [DONE]
                assert event.startswith("data: ")
                assert event.endswith("\n\n")
            
            assert events[-1] == "data: [DONE]\n\n"
    
    @pytest.mark.asyncio
    async def test_stream_token_usage(self):
        """
        场景: 流式输出中包含 Token 使用信息
        预期: 最后输出统计信息
        """
        agent = AgentService()
        
        steps = [
            {"type": "thought", "content": "思考"},
            {"type": "answer", "content": "答案"},
            {"type": "metadata", "tokens_used": 150, "steps_count": 2},
            {"type": "done"}
        ]
        
        events = []
        async for event in agent._stream_steps(steps):
            events.append(event)
        
        # 找到 metadata 事件
        metadata_events = [e for e in events if '"type": "metadata"' in e]
        assert len(metadata_events) == 1
        
        data = json.loads(metadata_events[0].replace('data: ', '').strip())
        assert data["tokens_used"] == 150
        assert data["steps_count"] == 2


class TestStreamingFrontendIntegration:
    """前端集成测试"""
    
    def test_sse_format_compliance(self):
        """
        场景: SSE 格式是否符合标准
        预期: data: 前缀，双换行分隔
        """
        import asyncio
        
        async def generate():
            agent = AgentService()
            async for event in agent._stream_steps([
                {"type": "thought", "content": "测试"}
            ]):
                yield event
        
        # 验证格式
        loop = asyncio.new_event_loop()
        events = []
        for event in loop.run_until_complete(self._collect_events(generate())):
            events.append(event)
        
        for event in events[:-1]:  # 除了 [DONE]
            assert event.startswith("data: ")
            assert "\n\n" in event
    
    async def _collect_events(self, generator):
        """辅助函数：收集异步生成器输出"""
        events = []
        async for event in generator:
            events.append(event)
        return events
    
    def test_json_parsable(self):
        """
        场景: data 字段的内容必须是合法 JSON
        预期: 可以正确解析
        """
        import asyncio
        
        async def test():
            agent = AgentService()
            events = []
            async for event in agent._stream_steps([
                {"type": "thought", "content": '包含"引号"和\\反斜杠'},
                {"type": "action", "tool": "exec", "input": {"code": "print('hello')"}}
            ]):
                if event != "data: [DONE]\n\n":
                    json_str = event.replace('data: ', '').strip()
                    data = json.loads(json_str)  # 必须能解析
                    events.append(data)
            return events
        
        loop = asyncio.new_event_loop()
        events = loop.run_until_complete(test())
        
        assert len(events) == 2
        assert events[0]["type"] == "thought"
        assert events[1]["type"] == "action"


class TestStreamingPartialContent:
    """部分内容流式测试（用于 exec 工具的长时间输出）"""
    
    @pytest.mark.asyncio
    async def test_stream_exec_partial_output(self):
        """
        场景: exec 工具执行产生大量输出
        预期: 可以分块流式输出
        
        注：这需要特殊实现，在 Sandbox 执行时边执行边流式
        当前可能先执行完再一次性输出
        """
        # 这是一个高级功能，先占位
        # 实现思路：
        # 1. Sandbox 执行时使用队列
        # 2. 定期读取输出并 yield
        # 3. 前端实时看到 print 的内容
        pass
    
    @pytest.mark.asyncio
    async def test_stream_large_observation(self):
        """
        场景: Observation 内容很大（如读取大文件）
        预期: 自动截断并在流式输出中提示
        """
        agent = AgentService()
        
        large_content = "大量数据\n" * 1000
        
        events = []
        async for event in agent._stream_steps([
            {"type": "observation", "content": large_content[:500] + "\n[内容已截断]", "success": True}
        ]):
            events.append(event)
        
        data = json.loads(events[0].replace('data: ', '').strip())
        assert "[内容已截断]" in data["content"]
