# 测试用例说明

本文档说明后端改造后的测试用例设计。

## 测试文件结构

```
tests/
├── conftest.py              # Pytest 配置和通用 fixtures
├── test_tools.py            # 工具系统测试（glob/read/grep/exec/stat）
├── test_sandbox.py          # 受限 Python 沙箱测试（安全性）
├── test_agent_service.py    # Agent 服务测试（ReAct 循环、权限、Token 控制）
├── test_streaming.py        # 流式输出测试（SSE 格式）
├── test_end_to_end.py       # 端到端测试（完整用户场景）
└── README.md                # 本文件
```

## 测试分类

### 1. 工具系统测试 (`test_tools.py`)

| 测试类 | 测试场景 | 关键断言 |
|-------|---------|---------|
| `TestGlobTool` | 文件发现 | `glob("*.csv")` 返回匹配文件列表 |
| `TestReadTool` | 文件读取 | 支持 offset/limit 分页，大文件截断 |
| `TestGrepTool` | 内容搜索 | 支持正则，返回匹配行和上下文 |
| `TestStatTool` | 文件统计 | 返回行数、列数、列名等 |
| `TestExecTool` | 代码执行 | 调用 Sandbox 执行 Python 分析 |

**安全测试**：
- `test_read_outside_working_dir`: 验证路径穿越防护

### 2. 沙箱安全测试 (`test_sandbox.py`)

| 测试类 | 测试场景 | 关键断言 |
|-------|---------|---------|
| `TestSandboxBasic` | 基础功能 | Pandas/Numpy 正常执行 |
| `TestSandboxSecurity` | **安全核心** | 禁止危险操作 |
| `TestSandboxResourceLimits` | 资源限制 | 超时控制 |
| `TestSandboxWorkspace` | 文件访问 | 只能在用户目录读写 |
| `TestSandboxErrorHandling` | 错误处理 | 语法错误、运行时错误 |

**关键安全测试**：
- `test_forbid_os_system`: 禁止 `os.system()`
- `test_forbid_subprocess`: 禁止 `subprocess`
- `test_forbid_network_requests`: 禁止网络请求
- `test_forbid_eval_exec`: 禁止动态代码执行
- `test_file_access_outside_working_dir`: 禁止越权文件访问
- `test_forbid_file_deletion`: 禁止删除系统文件

### 3. Agent 服务测试 (`test_agent_service.py`)

| 测试类 | 测试场景 | 关键断言 |
|-------|---------|---------|
| `TestAgentServiceBasic` | 基础功能 | Thought-Action-Observation 循环 |
| `TestAgentPermissions` | 权限区分 | 普通用户/管理员不同系统提示 |
| `TestAgentLoopControl` | 循环控制 | MAX_ITERATIONS 限制 |
| `TestAgentTokenControl` | Token 控制 | 上下文压缩、截断 |
| `TestAgentWithRealFiles` | 集成测试 | 完整分析工作流 |

**关键权限测试**：
- `test_user_with_file_selection`: 普通用户只能读选定文件
- `test_admin_user_can_use_glob`: 管理员可以使用 glob 探索

### 4. 流式输出测试 (`test_streaming.py`)

| 测试类 | 测试场景 | 关键断言 |
|-------|---------|---------|
| `TestStreamingFormat` | SSE 格式 | `data: {...}\n\n` 格式正确 |
| `TestStreamingErrorHandling` | 错误流 | error 事件正确输出 |
| `TestStreamingWithRealAgent` | 集成测试 | 真实 Agent 流式运行 |
| `TestStreamingFrontendIntegration` | 前端兼容 | JSON 可解析 |

**事件类型**：
- `thought`: AI 思考过程
- `action`: 工具调用
- `observation`: 工具返回
- `answer`: 最终答案
- `error`: 错误信息
- `metadata`: Token 统计等
- `[DONE]`: 流结束标记

### 5. 端到端测试 (`test_end_to_end.py`)

| 测试类 | 测试场景 |
|-------|---------|
| `TestEndToEndUser` | 普通用户完整使用流程 |
| `TestEndToEndAdmin` | 管理员完整使用流程 |
| `TestEndToEndErrorScenarios` | 错误处理流程 |
| `TestEndToEndComplexAnalysis` | 复杂分析场景 |
| `TestEndToEndConversation` | 对话上下文 |

**完整场景示例**：
```
用户（写权限）: "分析我的业务数据"
  ↓
Agent: Thought: 让我看看有哪些文件
       Action: glob("*.csv")
  ↓
Observation: [sales.csv, products.csv, customers.csv]
  ↓
Agent: Thought: 先了解 sales 文件结构
       Action: stat("sales.csv")
  ↓
Observation: {line_count: 10000, columns: [date, amount, ...]}
  ↓
Agent: Thought: 文件较大，读取前100行样本
       Action: read("sales.csv", limit=100)
  ↓
Observation: [数据内容...]
  ↓
Agent: Thought: 现在执行分析脚本
       Action: exec("import pandas as pd; df = pd.read_csv('sales.csv'); ...")
  ↓
Observation: 分析结果: Q1 增长 15%
  ↓
Agent: Answer: 根据分析，您的业务呈现上升趋势...
```

## 运行测试

```bash
cd backend

# 安装测试依赖
pip install pytest pytest-asyncio httpx

# 运行所有测试
pytest tests/ -v

# 运行特定测试文件
pytest tests/test_sandbox.py -v

# 运行安全测试（重要！）
pytest tests/test_sandbox.py::TestSandboxSecurity -v

# 运行权限测试
pytest tests/test_agent_service.py::TestAgentPermissions -v

# 带覆盖率报告
pytest tests/ --cov=services --cov=core --cov-report=html
```

## 关键测试断言示例

### 权限控制
```python
def test_user_cannot_use_glob(self):
    agent = AgentService()
    system_prompt = agent._build_system_prompt(role="user", file_names=["sales.csv"])
    
    assert "glob" not in system_prompt  # 普通用户不应该看到 glob
    assert "用户已选择以下文件" in system_prompt
```

### 安全沙箱
```python
def test_forbid_os_system(self, tmp_path):
    sandbox = RestrictedPythonSandbox(user_id=999, working_dir=tmp_path)
    
    code = """
import os
os.system('ls -la /')
"""
    result = sandbox.execute(code)
    
    assert result["success"] is False  # 必须失败！
    assert "禁止" in result["error"]
```

### Agent 循环
```python
async def test_max_iterations_limit(self):
    # Mock LLM 永远返回 Action
    mock_response = {
        "choices": [{
            "message": {
                "content": "Thought: 继续\nAction: glob\nAction Input: {}"
            }
        }]
    }
    
    agent = AgentService()
    agent.MAX_ITERATIONS = 3
    
    result = await agent.run(user=mock_user, message="test")
    
    assert result["steps"][-1]["type"] == "error"
    assert "达到最大迭代次数" in result["steps"][-1]["content"]
```

## 测试覆盖目标

| 模块 | 目标覆盖率 | 关键测试 |
|-----|-----------|---------|
| `core/tools.py` | 90%+ | 所有工具的正常和异常路径 |
| `core/sandbox.py` | 95%+ | **所有安全限制必须100%覆盖** |
| `services/agent_service.py` | 85%+ | ReAct循环、权限、Token控制 |
| `services/chat_service.py` | 80%+ | 集成 Agent、流式输出 |
| `api/chat.py` | 80%+ | API 端点、错误处理 |

## 注意事项

1. **安全测试最重要**: `test_sandbox.py` 中的测试必须全部通过，任何失败都是严重问题
2. **权限测试**: 确保普通用户确实无法越权访问
3. **Mock 使用**: LLM 调用使用 Mock，但工具执行使用真实实现（在安全环境下）
4. **临时目录**: 所有文件操作在 `tmp_path` 中进行，自动清理
5. **超时设置**: 测试中的超时设置比生产环境短，加速测试

## 待补充测试

以下场景需要在实现后补充测试：

1. **并发测试**: 多个用户同时使用 Agent
2. **数据库集成**: Agent 步骤持久化到数据库
3. **真实 LLM 集成**: 使用真实 API 的冒烟测试（可选）
4. **性能测试**: 大文件处理性能基准
5. **内存泄漏**: 长时间运行的内存使用测试
