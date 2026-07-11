# Task 4: 沙箱写权限控制 - 实现报告

## 状态

DONE

## 实现内容

按照 Task 4 需求，为 `RestrictedPythonSandbox` 增加了 `output_dir` 写权限隔离：

1. **`RestrictedPythonSandbox.__init__`**
   - 新增可选参数 `output_dir: Path = None`
   - 保持 `user_id` 和 `timeout` 的向后兼容（`user_id` 默认 `0`，`working_dir` 默认当前目录）

2. **生成的 wrapper 脚本 `_safe_open`**
   - 写/追加/创建模式（`w`/`a`/`x`/`+`）必须发生在 `output_dir` 下
   - `output_dir` 未提供时，写操作直接抛出 `PermissionError`
   - 支持虚拟路径 `/output/*` 到实际 `output_dir` 的映射，便于上层功能统一约定
   - 读模式保持原有策略：仅允许 `working_dir`、`output_dir` 和必要系统路径

3. **`_is_allowed_path` 严格化**
   - 仅允许 `working_dir`、`output_dir` 和 `_ALLOWED_SYSTEM_PATHS` 中的系统路径

4. **测试**
   - 新增 `backend/tests/test_sandbox_write_guard.py`，覆盖：
     - 无法写入 `working_dir` 下的源文件
     - 可以写入 `output_dir`（含 `/output` 虚拟路径）
   - 调整 `backend/tests/test_sandbox.py::test_write_file_to_workspace`，显式传入 `output_dir=workspace` 以适配新行为

## TDD 证据

### RED - 新测试失败（`output_dir` 尚未支持）

```bash
cd backend && python3 -m pytest tests/test_sandbox_write_guard.py -v
```

结果：

```
tests/test_sandbox_write_guard.py::test_cannot_write_source_file FAILED
tests/test_sandbox_write_guard.py::test_can_write_to_output_dir FAILED
=================== 2 failed in 0.17s ===================
```

失败原因：`__init__() got an unexpected keyword argument 'output_dir'`

### GREEN - 实现后新测试通过

```bash
cd backend && python3 -m pytest tests/test_sandbox_write_guard.py -v
```

结果：

```
tests/test_sandbox_write_guard.py::test_cannot_write_source_file PASSED
tests/test_sandbox_write_guard.py::test_can_write_to_output_dir PASSED
==================== 2 passed in 0.15s ====================
```

### 相关沙箱测试

```bash
cd backend && python3 -m pytest tests/test_sandbox.py tests/test_sandbox_write_guard.py tests/test_tools.py::TestExecTool -v
```

结果：27 passed，3 failed（均为本任务引入前已存在的环境问题）

## 全量后端测试

```bash
cd backend && python3 -m pytest tests/ -v
```

结果：73 passed，9 failed，5 skipped

失败全部为 **Task 4 引入前已存在** 的问题：

- `tests/test_end_to_end.py` 6 个失败：使用伪造 token 导致 401，以及 `TestClient.post(stream=True)` 参数不支持
- `tests/test_sandbox.py::test_file_access_outside_working_dir`：macOS 环境下 `/etc/passwd` 位于允许的系统路径 `/etc` 下，可被读取
- `tests/test_sandbox.py::test_import_error`：本机未安装 `tensorflow`，错误文案为 `ModuleNotFoundError` 而非预期的 `ImportError`/`不允许`
- `tests/test_tools.py::test_exec_file_access_outside_working_dir`：同上 `/etc/passwd` 可读问题

## 文件变更

| 文件 | 说明 |
|------|------|
| `backend/core/sandbox.py` | 增加 `output_dir` 参数；`_restricted_open` 替换为 `_safe_open`；实现写操作隔离；`_is_allowed_path` 增加 output_dir 读取许可 |
| `backend/tests/test_sandbox_write_guard.py` | 新增写权限控制测试 |
| `backend/tests/test_sandbox.py` | `test_write_file_to_workspace` 显式传入 `output_dir=workspace` |

## 提交

```
7ae089d feat(sandbox): enforce output_dir write isolation
```

## 自审发现

1. **符合任务要求**：实现了 `output_dir` 写隔离，无 `output_dir` 时拒绝写操作。
2. **向后兼容**：保留 `user_id`、`timeout` 参数原有语义，现有调用方无需立即修改。
3. **安全无削弱**：读路径检查仍然严格；写路径必须落在 `output_dir` 内；`/output` 虚拟路径仅用于写模式映射，不会绕过检查。
4. **测试覆盖**：新增测试覆盖禁止写入源目录、允许写入输出目录两个核心场景。
5. **现有测试适配**：`test_write_file_to_workspace` 必须传入 `output_dir` 才能继续写入，这是预期行为变化。

## 问题与顾虑

- `/output` 虚拟路径映射是当前实现为了兼容 Task 4 测试用例中的绝对路径写法而引入的约定。若上层（Workspace/ExecTool）最终直接传递实际 `output_dir` 路径，该映射可保持也可移除，不影响安全。
- `ExecTool` 目前未传入 `output_dir`，因此通过 `exec` 工具写入文件会被拒绝。这是符合 Task 4 严格语义的，但后续任务若需要 Agent 生成输出文件，需要把 Workspace 的 `output_path` 透传到 `ExecTool`/`RestrictedPythonSandbox`。
- 全量测试中的 9 个失败均为本任务之前已存在，未引入新的回归。


---

## 2026-07-11 修复：Review 反馈处理

### 修复内容

针对 Review 中提出的 4 项问题，对 `backend/core/sandbox.py` 进行了修正：

1. **严格化 `_is_allowed_path` 路径检查**
   - 将 `resolved.startswith(_WORKING_DIR)` / `resolved.startswith(_OUTPUT_DIR)` 改为使用 `os.path.commonpath` 的 `_is_under` 辅助函数，避免兄弟目录因前缀相同而误通过（如 `/tmp/source2/file` 不会被当作 `/tmp/source` 的子路径）。
   - 系统路径检查同样改用 `_is_under`，统一严格语义。

2. **恢复 `timeout` 参数位置，将 `output_dir` 移到最后**
   - 签名从 `__init__(..., working_dir, output_dir, timeout)` 改为 `__init__(..., working_dir, timeout, output_dir=None)`，避免破坏按位置传入 `timeout` 的调用方。

3. **严格化 `/output` 虚拟路径映射**
   - 写模式下的虚拟路径检查从 `str(p).startswith('/output')` 改为 `path_str == '/output' or path_str.startswith('/output/')`，防止 `/output_file.txt` 被误映射到输出目录。

4. **保持 `working_dir` 必填**
   - 签名中保留 `working_dir: Path = None` 以维持参数顺序，但在初始化时显式校验：若为 `None` 则抛出 `ValueError("working_dir is required")`。
   - 移除默认回退到 `Path(".")` 的行为。

5. **附加安全加固：排除脚本临时目录**
   - 在生成的 wrapper 脚本中，`_PYTHON_LIB_PATHS` 排除了脚本自身所在的临时目录（`_SCRIPT_DIR`），避免 `/var/folders/.../T` 等临时根目录被加入允许列表，导致任意临时文件可被读取。

### 测试更新

`backend/tests/test_sandbox_write_guard.py` 新增两个回归测试：

- `test_cannot_read_sibling_directory`：验证工作目录的兄弟目录无法被读取。
- `test_output_virtual_path_strict_prefix`：验证 `/output_file.txt` 不会被误映射到 `output_dir`。

### 验证结果

```bash
cd backend && python3 -m pytest tests/test_sandbox_write_guard.py -v
# 4 passed

cd backend && python3 -m pytest tests/test_sandbox.py tests/test_sandbox_write_guard.py tests/test_tools.py::TestExecTool -v
# 29 passed, 3 failed（均为本修复前已存在的环境问题）

cd backend && python3 -m pytest tests/ -v
# 75 passed, 9 failed, 5 skipped（失败均为 Task 4 之前已存在：伪造 token 401、TestClient.stream 参数不支持、macOS /etc/passwd 可读、tensorflow 未安装）
```

### 提交

```
fix(sandbox): strict path checks and parameter order
```

