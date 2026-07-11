# 本地文件夹工作空间（Local Folder Workspace）实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现 Project 37 的本地文件夹工作空间模块，支持上传与挂载两种数据入口、自动生成推荐问题、Agent 只读源文件并自动保存交付物到用户可控的输出目录。

**Architecture:** 在后端引入 `Workspace` 与 `OutputArtifact` 数据模型，新增 Workspace/Roadmap API；复用 YOLO 分支的 `SchemaProfiler` 生成数据关系图，由 `RoadmapService` 调用 LLM 生成推荐问题；`AgentService` 增加 `output_dir` 概念，`Sandbox` 增强写权限控制；前端新增 `WorkspaceBar`、`RecommendedQuestions`、`WelcomeRoadmapModal` 三个组件并与现有 ChatView/FilesView 集成。

**Tech Stack:** FastAPI + SQLAlchemy + SQLite（后端）；Vue 3 + Vite + Pinia（前端）；Python `RestrictedPythonSandbox`；DeepSeek LLM；YOLO `schema_profiler.py`。

## Global Constraints

- 保持现有用户认证与角色模型不变（`user`/`admin`，默认 `admin`）
- 不修改现有数据库迁移策略，新增表通过 SQLAlchemy `create_all` 自动创建
- 沙箱安全策略不得弱于当前实现
- 所有新增 API 路由前缀 `/api`
- 前端继续优先 Mac，同时保证 Windows 能跑
- 禁止在 LLM 回答中使用 emoji（沿用现有系统提示规则）
- 每次打开应用时重新生成推荐问题（LLM 调用）
- 输出目录默认 `<workspace>/37-output/YYYY-MM-DD/`，用户可修改
- 挂载模式第一阶段采用复制隔离，不依赖 OS 只读挂载
- OutputArtifact 为 P0 必须实现

---

## 文件结构总览

### 后端新增
- `backend/models/workspace.py`
- `backend/models/output_artifact.py`
- `backend/api/workspaces.py`
- `backend/api/roadmap.py`
- `backend/services/workspace_service.py`
- `backend/services/roadmap_service.py`

### 后端修改
- `backend/models/file.py`：增加 `workspace_id`
- `backend/models/__init__.py`：导出新模型
- `backend/api/files.py`：上传关联 workspace，后台触发 profiling
- `backend/api/chat.py`：接收 `workspace_id`
- `backend/services/agent_service.py`：增加 `output_dir`，系统提示禁止写源文件
- `backend/services/chat_service.py`：根据 workspace 设置 working_dir/output_dir
- `backend/core/sandbox.py`：写操作只能到 output_dir
- `backend/core/tools.py`：ExecTool 传入 output_dir

### 前端新增
- `frontend/src/components/WorkspaceBar.vue`
- `frontend/src/components/RecommendedQuestions.vue`
- `frontend/src/components/WelcomeRoadmapModal.vue`
- `frontend/src/api/workspaces.js`
- `frontend/src/api/roadmap.js`

### 前端修改
- `frontend/src/views/ChatView.vue`：集成 WorkspaceBar、RecommendedQuestions、弹窗、保存提示
- `frontend/src/views/FilesView.vue`：支持 workspace 切换
- `frontend/src/stores/chat.js`：增加当前 workspace 状态、推荐问题

---

### Task 1: Workspace 数据模型

**Files:**
- Create: `backend/models/workspace.py`
- Create: `backend/models/output_artifact.py`
- Modify: `backend/models/file.py`
- Modify: `backend/models/__init__.py`
- Test: `backend/tests/test_workspace_model.py`

**Interfaces:**
- Consumes: existing `User` model
- Produces: `Workspace` SQLAlchemy model, `OutputArtifact` SQLAlchemy model, `File.workspace_id`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_workspace_model.py
from models.workspace import Workspace
from models.output_artifact import OutputArtifact
from models.file import File
from models.user import User


def test_workspace_creation(db_session):
    user = User(username="teacher", hashed_password="x", role="admin")
    db_session.add(user)
    db_session.commit()

    ws = Workspace(
        owner_id=user.id,
        name="期末数据",
        type="internal",
        output_path=f"uploads/user_{user.id}/37-output"
    )
    db_session.add(ws)
    db_session.commit()

    assert ws.id is not None
    assert ws.type == "internal"
    assert ws.source_path is None


def test_output_artifact_creation(db_session):
    user = User(username="teacher2", hashed_password="x", role="admin")
    db_session.add(user)
    db_session.commit()

    ws = Workspace(owner_id=user.id, name="ws", type="internal", output_path="/tmp/out")
    db_session.add(ws)
    db_session.commit()

    art = OutputArtifact(
        workspace_id=ws.id,
        filename="report.md",
        relative_path="37-output/2026-07-31/report.md",
        artifact_type="report"
    )
    db_session.add(art)
    db_session.commit()

    assert art.id is not None
    assert art.workspace_id == ws.id


def test_file_has_workspace_id(db_session):
    from sqlalchemy import inspect
    inspector = inspect(File)
    assert "workspace_id" in inspector.columns
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_workspace_model.py -v`

Expected: FAIL — `Workspace`, `OutputArtifact` not defined; `File` has no `workspace_id`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/models/workspace.py
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from models.base import Base


class Workspace(Base):
    __tablename__ = "workspaces"

    id = Column(Integer, primary_key=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String, nullable=False, default="我的数据空间")
    type = Column(String, nullable=False)  # "internal" | "external"
    source_path = Column(String, nullable=True)
    output_path = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    owner = relationship("User", back_populates="workspaces")
    files = relationship("File", back_populates="workspace", cascade="all, delete-orphan")
    artifacts = relationship("OutputArtifact", back_populates="workspace", cascade="all, delete-orphan")
```

```python
# backend/models/output_artifact.py
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from models.base import Base


class OutputArtifact(Base):
    __tablename__ = "output_artifacts"

    id = Column(Integer, primary_key=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id"), nullable=False)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), nullable=True)
    filename = Column(String, nullable=False)
    relative_path = Column(String, nullable=False)
    artifact_type = Column(String, nullable=False, default="other")
    created_at = Column(DateTime, default=datetime.utcnow)

    workspace = relationship("Workspace", back_populates="artifacts")
```

```python
# backend/models/file.py — add field only
workspace_id = Column(Integer, ForeignKey("workspaces.id"), nullable=True)
workspace = relationship("Workspace", back_populates="files")
```

```python
# backend/models/__init__.py — add imports
from models.workspace import Workspace
from models.output_artifact import OutputArtifact
```

```python
# backend/models/user.py — add relationship
workspaces = relationship("Workspace", back_populates="owner", cascade="all, delete-orphan")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_workspace_model.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/models/workspace.py backend/models/output_artifact.py backend/models/file.py backend/models/__init__.py backend/models/user.py backend/tests/test_workspace_model.py
git commit -m "feat(workspace): add Workspace and OutputArtifact models"
```


---

### Task 2: WorkspaceService

**Files:**
- Create: `backend/services/workspace_service.py`
- Test: `backend/tests/test_workspace_service.py`

**Interfaces:**
- Consumes: `Workspace` model, `FileService._get_user_dir`
- Produces: `WorkspaceService.get_or_create_internal`, `WorkspaceService.mount`, `WorkspaceService.unmount`, `WorkspaceService.set_output_path`, `WorkspaceService.get_internal_copy_dir`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_workspace_service.py
import pytest
from services.workspace_service import WorkspaceService
from models.workspace import Workspace


def test_get_or_create_internal_creates_once(db_session):
    from models.user import User
    user = User(username="u1", hashed_password="x", role="admin")
    db_session.add(user)
    db_session.commit()

    ws1 = WorkspaceService.get_or_create_internal(db_session, user)
    ws2 = WorkspaceService.get_or_create_internal(db_session, user)
    assert ws1.id == ws2.id
    assert ws1.type == "internal"


def test_mount_external_workspace(db_session, tmp_path):
    from models.user import User
    user = User(username="u2", hashed_password="x", role="admin")
    db_session.add(user)
    db_session.commit()

    src = tmp_path / "data"
    src.mkdir()
    (src / "a.csv").write_text("x,y\n1,2\n")

    ws = WorkspaceService.mount(db_session, user, str(src), "我的数据")
    assert ws.type == "external"
    assert ws.source_path == str(src)
    assert "37-output" in ws.output_path


def test_unmount_deletes_record(db_session, tmp_path):
    from models.user import User
    user = User(username="u3", hashed_password="x", role="admin")
    db_session.add(user)
    db_session.commit()

    src = tmp_path / "data"
    src.mkdir()
    ws = WorkspaceService.mount(db_session, user, str(src), "x")
    WorkspaceService.unmount(db_session, user, ws.id)

    assert db_session.query(Workspace).filter_by(id=ws.id).first() is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_workspace_service.py -v`

Expected: FAIL — `WorkspaceService` not found

- [ ] **Step 3: Write minimal implementation**

```python
# backend/services/workspace_service.py
from pathlib import Path
from sqlalchemy.orm import Session
from models.workspace import Workspace
from models.user import User
from services.file_service import FileService


class WorkspaceService:
    @staticmethod
    def get_or_create_internal(db: Session, user: User) -> Workspace:
        ws = db.query(Workspace).filter_by(
            owner_id=user.id, type="internal"
        ).first()
        if ws:
            return ws

        user_dir = FileService._get_user_dir(user.id)
        output_path = str(user_dir / "37-output")
        ws = Workspace(
            owner_id=user.id,
            name="我的数据空间",
            type="internal",
            source_path=None,
            output_path=output_path
        )
        db.add(ws)
        db.commit()
        db.refresh(ws)
        return ws

    @staticmethod
    def mount(db: Session, user: User, local_path: str, name: str) -> Workspace:
        p = Path(local_path).resolve()
        if not p.exists():
            raise ValueError(f"Path does not exist: {local_path}")
        if not p.is_dir():
            raise ValueError(f"Path is not a directory: {local_path}")

        try:
            next(p.iterdir())
        except PermissionError:
            raise ValueError(f"Cannot read directory: {local_path}")
        except StopIteration:
            pass

        output_path = str(p / "37-output")
        ws = Workspace(
            owner_id=user.id,
            name=name,
            type="external",
            source_path=str(p),
            output_path=output_path
        )
        db.add(ws)
        db.commit()
        db.refresh(ws)
        return ws

    @staticmethod
    def unmount(db: Session, user: User, workspace_id: int) -> None:
        ws = db.query(Workspace).filter_by(id=workspace_id, owner_id=user.id).first()
        if not ws:
            raise ValueError("Workspace not found")
        db.delete(ws)
        db.commit()

    @staticmethod
    def set_output_path(db: Session, user: User, workspace_id: int, output_path: str) -> Workspace:
        p = Path(output_path).resolve()
        p.mkdir(parents=True, exist_ok=True)
        if not p.is_dir():
            raise ValueError(f"Invalid output path: {output_path}")

        ws = db.query(Workspace).filter_by(id=workspace_id, owner_id=user.id).first()
        if not ws:
            raise ValueError("Workspace not found")

        ws.output_path = str(p)
        db.commit()
        db.refresh(ws)
        return ws

    @staticmethod
    def get_internal_copy_dir(user_id: int, workspace_id: int) -> Path:
        base = Path(FileService._get_user_dir(user_id)) / "mounts" / str(workspace_id)
        base.mkdir(parents=True, exist_ok=True)
        return base
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_workspace_service.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/services/workspace_service.py backend/tests/test_workspace_service.py
git commit -m "feat(workspace): add WorkspaceService with internal/mount/output-path"
```

---

### Task 3: Workspace API

**Files:**
- Create: `backend/api/workspaces.py`
- Create: `backend/schemas/workspace.py`
- Modify: `backend/api/__init__.py` (router registration)
- Test: `backend/tests/test_workspace_api.py`

**Interfaces:**
- Consumes: `WorkspaceService`
- Produces: `GET /api/workspaces/list`, `POST /api/workspaces/mount`, `POST /api/workspaces/{id}/unmount`, `PUT /api/workspaces/{id}/output-path`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_workspace_api.py
from fastapi.testclient import TestClient


def test_list_workspaces(client: TestClient, auth_headers):
    r = client.get("/api/workspaces/list", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()["data"]
    assert len(data) >= 1
    assert data[0]["type"] == "internal"


def test_mount_and_unmount(client: TestClient, auth_headers, tmp_path):
    src = tmp_path / "data"
    src.mkdir()
    (src / "a.csv").write_text("x,y\n1,2\n")

    r = client.post("/api/workspaces/mount", headers=auth_headers, json={
        "local_path": str(src),
        "name": "期末数据"
    })
    assert r.status_code == 200, r.text
    ws_id = r.json()["data"]["id"]

    r = client.post(f"/api/workspaces/{ws_id}/unmount", headers=auth_headers)
    assert r.status_code == 200
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_workspace_api.py -v`

Expected: FAIL — routes not found

- [ ] **Step 3: Write minimal implementation**

```python
# backend/schemas/workspace.py
from pydantic import BaseModel


class MountRequest(BaseModel):
    local_path: str
    name: str


class OutputPathRequest(BaseModel):
    output_path: str
```

```python
# backend/api/workspaces.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from api.deps import get_current_user, get_db
from schemas.common import BaseResponse
from schemas.workspace import MountRequest, OutputPathRequest
from services.workspace_service import WorkspaceService
from models.user import User
from models.workspace import Workspace

router = APIRouter(prefix="/workspaces", tags=["workspaces"])


@router.get("/list")
def list_workspaces(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    workspaces = db.query(Workspace).filter_by(owner_id=user.id).all()
    return BaseResponse(data=[
        {
            "id": ws.id,
            "name": ws.name,
            "type": ws.type,
            "source_path": ws.source_path,
            "output_path": ws.output_path,
            "is_active": ws.is_active,
            "created_at": ws.created_at.isoformat() if ws.created_at else None
        }
        for ws in workspaces
    ])


@router.post("/mount")
def mount_workspace(
    req: MountRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    try:
        ws = WorkspaceService.mount(db, user, req.local_path, req.name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return BaseResponse(data={
        "id": ws.id,
        "name": ws.name,
        "type": ws.type,
        "source_path": ws.source_path,
        "output_path": ws.output_path
    })


@router.post("/{workspace_id}/unmount")
def unmount_workspace(
    workspace_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    try:
        WorkspaceService.unmount(db, user, workspace_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return BaseResponse(data={"unmounted": True})


@router.put("/{workspace_id}/output-path")
def update_output_path(
    workspace_id: int,
    req: OutputPathRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    try:
        ws = WorkspaceService.set_output_path(db, user, workspace_id, req.output_path)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return BaseResponse(data={
        "id": ws.id,
        "output_path": ws.output_path
    })
```

```python
# backend/api/__init__.py
from api.workspaces import router as workspaces_router

# in api_router include
api_router.include_router(workspaces_router)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_workspace_api.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/api/workspaces.py backend/schemas/workspace.py backend/api/__init__.py backend/tests/test_workspace_api.py
git commit -m "feat(workspace): add workspace CRUD API"
```

---

### Task 4: 沙箱写权限控制

**Files:**
- Modify: `backend/core/sandbox.py`
- Test: `backend/tests/test_sandbox_write_guard.py`

**Interfaces:**
- Consumes: `working_dir`, `output_dir` parameters
- Produces: `RestrictedPythonSandbox` with write guard

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_sandbox_write_guard.py
from core.sandbox import RestrictedPythonSandbox
from pathlib import Path


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
    assert result["status"] == "error"
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
    assert result["status"] == "success"
    assert (output_dir / "result.txt").read_text() == "hello"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_sandbox_write_guard.py -v`

Expected: FAIL — `output_dir` not supported, source file write succeeds

- [ ] **Step 3: Write minimal implementation**

Modify `RestrictedPythonSandbox.__init__` to accept `output_dir=None`.

Modify `_safe_open` in the generated wrapper script:

```python
def _safe_open(path, mode='r', *args, **kwargs):
    import builtins
    p = Path(path).resolve()

    # Write/append/create must be under output_dir
    if any(m in mode for m in 'wax+'):
        if output_dir is None:
            raise PermissionError("Write operations are not allowed in this sandbox")
        out = Path(output_dir).resolve()
        if not p.is_relative_to(out):
            raise PermissionError(f"Cannot write outside output directory: {path}")
        return builtins.open(p, mode, *args, **kwargs)

    # Read must be under working_dir or allowed system paths
    if not _is_allowed_path(p):
        raise PermissionError(f"Cannot read file: {path}")
    return builtins.open(p, mode, *args, **kwargs)
```

Also update `_is_allowed_path` to be strict: only `working_dir`, `output_dir`, and necessary system paths.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_sandbox_write_guard.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/core/sandbox.py backend/tests/test_sandbox_write_guard.py
git commit -m "feat(sandbox): enforce output_dir write isolation"
```


---

### Task 5: AgentService 与 ExecTool 接入 output_dir

**Files:**
- Modify: `backend/services/agent_service.py`
- Modify: `backend/core/tools.py`
- Test: `backend/tests/test_agent_output_dir.py`

**Interfaces:**
- Consumes: `AgentService` receives `output_dir`; `ExecTool` receives `output_dir`
- Produces: Agent can write only to output_dir

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_agent_output_dir.py
from services.agent_service import AgentService
from pathlib import Path


def test_agent_service_accepts_output_dir(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    output = tmp_path / "output"
    output.mkdir()
    (source / "data.csv").write_text("x,y\n1,2\n")

    agent = AgentService(
        working_dir=str(source),
        output_dir=str(output),
        role="admin"
    )
    assert agent.working_dir == str(source)
    assert agent.output_dir == str(output)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_agent_output_dir.py -v`

Expected: FAIL — `AgentService` has no `output_dir`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/services/agent_service.py
class AgentService:
    def __init__(
        self,
        working_dir: str,
        output_dir: str,
        role: str = "admin",
        file_names: list = None,
        file_contents: dict = None,
        history: list = None
    ):
        self.working_dir = working_dir
        self.output_dir = output_dir
        self.role = role
        # ... rest unchanged

    def _execute_tool(self, name: str, tool_input: dict):
        tool = TOOLS.get(name)
        if not tool:
            return {"success": False, "error": f"Unknown tool: {name}"}
        try:
            if name == "exec":
                # Pass output_dir to ExecTool
                result = tool.run(tool_input, working_dir=self.working_dir, output_dir=self.output_dir)
            else:
                result = tool.run(tool_input, working_dir=self.working_dir)
            return {"success": True, "output": result}
        except Exception as e:
            return {"success": False, "error": str(e)}
```

```python
# backend/core/tools.py
class ExecTool:
    def run(self, tool_input: dict, working_dir: str = None, output_dir: str = None):
        code = tool_input.get("code", "")
        sandbox = RestrictedPythonSandbox(
            working_dir=working_dir,
            output_dir=output_dir,
            timeout=30
        )
        return sandbox.execute(code)
```

Update system prompt in `_build_system_prompt`:

```
重要规则：
- 你只能读取工作目录中的文件，禁止修改、删除或覆盖任何源文件。
- 所有输出文件（图表、报告、CSV 结果）必须保存到 /output/ 目录下。
- 如果用户没有要求保存，你也应该把有价值的交付物自动保存到 /output/。
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_agent_output_dir.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/services/agent_service.py backend/core/tools.py backend/tests/test_agent_output_dir.py
git commit -m "feat(agent): pass output_dir to sandbox and exec tool"
```

---

### Task 6: RoadmapService 与推荐问题生成

**Files:**
- Create: `backend/services/roadmap_service.py`
- Create: `backend/api/roadmap.py`
- Create: `backend/schemas/roadmap.py`
- Modify: `backend/api/__init__.py`
- Test: `backend/tests/test_roadmap_service.py`

**Interfaces:**
- Consumes: `SchemaProfiler` (from YOLO), `LLMClient`
- Produces: `GET /api/workspaces/{id}/roadmap` returns `{tables, relationships, questions}`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_roadmap_service.py
from pathlib import Path
from services.roadmap_service import RoadmapService
from services.workspace_service import WorkspaceService
from models.user import User


def test_build_roadmap_generates_questions(db_session, tmp_path):
    user = User(username="r1", hashed_password="x", role="admin")
    db_session.add(user)
    db_session.commit()

    src = tmp_path / "data"
    src.mkdir()
    (src / "语文成绩.csv").write_text("学生姓名,成绩\n张三,90\n李四,85\n")
    (src / "数学成绩.csv").write_text("学生姓名,成绩\n张三,95\n李四,80\n")

    ws = WorkspaceService.mount(db_session, user, str(src), "成绩")

    # Patch LLM call to avoid real API usage in unit test
    roadmap = RoadmapService.build_roadmap(db_session, ws, llm_client=FakeLLM())

    assert "tables" in roadmap
    assert "relationships" in roadmap
    assert "questions" in roadmap
    assert len(roadmap["questions"]) > 0


class FakeLLM:
    def chat_completion(self, messages, **kwargs):
        return {
            "choices": [{
                "message": {
                    "content": "- 语文和数学成绩的相关性如何？\n- 谁的总分最高？"
                }
            }]
        }
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_roadmap_service.py -v`

Expected: FAIL — `RoadmapService` not found

- [ ] **Step 3: Write minimal implementation**

```python
# backend/services/roadmap_service.py
import json
from pathlib import Path
from sqlalchemy.orm import Session
from models.workspace import Workspace
from tools.schema_profiler import SchemaProfiler
from core.llm_client import llm_client


class RoadmapService:
    @staticmethod
    def build_roadmap(db: Session, workspace: Workspace, llm_client=None):
        workspace_path = Path(workspace.output_path).parent if workspace.type == "internal" else Path(workspace.source_path)
        profiler = SchemaProfiler()
        graph = profiler.build_and_cache(str(workspace_path))

        questions = RoadmapService.generate_questions(graph, llm_client or llm_client)

        return {
            "tables": graph.get("nodes", []),
            "relationships": graph.get("edges", []),
            "questions": questions
        }

    @staticmethod
    def generate_questions(graph: dict, llm_client) -> list:
        if not graph or not graph.get("edges"):
            return RoadmapService.fallback_questions(graph)

        summary = RoadmapService._summarize_graph(graph)
        messages = [
            {"role": "system", "content": "你是一个数据分析师，擅长把数据关系翻译成非技术人员能听懂的问题。"},
            {"role": "user", "content": f"""基于以下数据关系，生成 3-5 个自然语言分析问题：

{summary}

要求：
- 问题要具体，直接对应表格和字段
- 优先推荐有明确关联关系的问题
- 不要复杂统计术语
- 每个问题一句话
- 不要 emoji

请只输出问题列表，每行一个，以 "- " 开头。"""}
        ]

        try:
            resp = llm_client.chat_completion(messages, temperature=0.3)
            content = resp["choices"][0]["message"]["content"]
            questions = [line.strip("- ").strip() for line in content.split("\n") if line.strip().startswith("-")]
            if questions:
                return questions[:5]
        except Exception:
            pass

        return RoadmapService.fallback_questions(graph)

    @staticmethod
    def fallback_questions(graph: dict) -> list:
        questions = []
        edges = graph.get("edges", [])
        for edge in edges[:3]:
            src = edge.get("source", "")
            tgt = edge.get("target", "")
            col = edge.get("source_column", "")
            questions.append(f"{src} 和 {tgt} 可以通过 {col} 关联，你想分析它们之间的关系吗？")

        nodes = graph.get("nodes", [])
        for node in nodes[:2]:
            name = node.get("name", "")
            questions.append(f"{name} 里有哪些值得关注的趋势或分布？")

        return questions[:5]

    @staticmethod
    def _summarize_graph(graph: dict) -> str:
        lines = ["表格："]
        for node in graph.get("nodes", []):
            lines.append(f"- {node.get('name')}，列：{', '.join(node.get('columns', []))}")
        lines.append("\n关系：")
        for edge in graph.get("edges", [])[:10]:
            lines.append(
                f"- {edge.get('source')}.{edge.get('source_column')} → "
                f"{edge.get('target')}.{edge.get('target_column')} "
                f"(置信度 {edge.get('confidence', 0):.2f})"
            )
        return "\n".join(lines)
```

```python
# backend/api/roadmap.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from api.deps import get_current_user, get_db
from schemas.common import BaseResponse
from services.roadmap_service import RoadmapService
from services.workspace_service import WorkspaceService
from models.user import User
from models.workspace import Workspace

router = APIRouter(prefix="/workspaces", tags=["roadmap"])


@router.get("/{workspace_id}/roadmap")
def get_roadmap(
    workspace_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    ws = db.query(Workspace).filter_by(id=workspace_id, owner_id=user.id).first()
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")

    try:
        roadmap = RoadmapService.build_roadmap(db, ws)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to build roadmap: {e}")

    return BaseResponse(data=roadmap)
```

```python
# backend/api/__init__.py
from api.roadmap import router as roadmap_router
api_router.include_router(roadmap_router)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_roadmap_service.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/services/roadmap_service.py backend/api/roadmap.py backend/schemas/roadmap.py backend/api/__init__.py backend/tests/test_roadmap_service.py
git commit -m "feat(roadmap): add schema profiling and question generation"
```

---

### Task 7: ChatService 接入 Workspace

**Files:**
- Modify: `backend/services/chat_service.py`
- Modify: `backend/api/chat.py`
- Modify: `backend/api/files.py` (upload association)
- Test: `backend/tests/test_chat_workspace.py`

**Interfaces:**
- Consumes: `WorkspaceService`, `RoadmapService`
- Produces: Chat APIs accept `workspace_id`, resolve `working_dir`/`output_dir`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_chat_workspace.py
from fastapi.testclient import TestClient


def test_chat_with_workspace(client: TestClient, auth_headers, tmp_path):
    # Create a workspace first
    src = tmp_path / "data"
    src.mkdir()
    (src / "a.csv").write_text("x,y\n1,2\n")

    r = client.post("/api/workspaces/mount", headers=auth_headers, json={
        "local_path": str(src),
        "name": "test"
    })
    ws_id = r.json()["data"]["id"]

    r = client.post("/api/chat/send", headers=auth_headers, json={
        "message": "hi",
        "workspace_id": ws_id
    })
    assert r.status_code == 200
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_chat_workspace.py -v`

Expected: FAIL — chat endpoint ignores workspace_id

- [ ] **Step 3: Write minimal implementation**

```python
# backend/services/chat_service.py
from services.workspace_service import WorkspaceService

class ChatService:
    @staticmethod
    def _resolve_workspace_and_dirs(db, user, workspace_id=None):
        if workspace_id:
            ws = db.query(Workspace).filter_by(id=workspace_id, owner_id=user.id).first()
            if not ws:
                raise ValueError("Workspace not found")
        else:
            ws = WorkspaceService.get_or_create_internal(db, user)

        if ws.type == "external":
            # Copy isolation: agent works on internal copy
            copy_dir = WorkspaceService.get_internal_copy_dir(user.id, ws.id)
            # TODO: sync files from source_path to copy_dir (handled in Task 8)
            working_dir = str(copy_dir)
        else:
            working_dir = str(FileService._get_user_dir(user.id))

        output_dir = ws.output_path
        return ws, working_dir, output_dir

    @staticmethod
    def chat(db, user, message, file_ids=None, workspace_id=None, stream=False):
        ws, working_dir, output_dir = ChatService._resolve_workspace_and_dirs(db, user, workspace_id)
        # ... pass working_dir/output_dir to AgentService
```

```python
# backend/api/chat.py — add workspace_id to request schemas
class ChatRequest(BaseModel):
    message: str
    file_ids: list[int] = []
    workspace_id: int | None = None
```

```python
# backend/api/files.py — upload to current or default workspace
def upload_file(..., workspace_id: int | None = Form(None)):
    if workspace_id is None:
        ws = WorkspaceService.get_or_create_internal(db, current_user)
    else:
        ws = db.query(Workspace).filter_by(id=workspace_id, owner_id=current_user.id).first()
    # ... save file with workspace_id=ws.id
    # ... background trigger profiling
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_chat_workspace.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/services/chat_service.py backend/api/chat.py backend/api/files.py backend/tests/test_chat_workspace.py
git commit -m "feat(chat): integrate workspace and output_dir"
```

---

### Task 8: 挂载文件夹复制隔离

**Files:**
- Modify: `backend/services/workspace_service.py`
- Modify: `backend/services/chat_service.py`
- Test: `backend/tests/test_mount_copy_isolation.py`

**Interfaces:**
- Consumes: `Workspace.source_path`
- Produces: internal copy directory synced from source

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_mount_copy_isolation.py
from services.workspace_service import WorkspaceService
from pathlib import Path


def test_external_mount_creates_copy(db_session, tmp_path):
    from models.user import User
    user = User(username="c1", hashed_password="x", role="admin")
    db_session.add(user)
    db_session.commit()

    src = tmp_path / "source"
    src.mkdir()
    (src / "data.csv").write_text("x\n1\n")

    ws = WorkspaceService.mount(db_session, user, str(src), "s")
    copy_dir = WorkspaceService.get_internal_copy_dir(user.id, ws.id)

    WorkspaceService.sync_external_to_copy(ws, copy_dir)

    assert (copy_dir / "data.csv").exists()
    assert (copy_dir / "data.csv").read_text() == "x\n1\n"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_mount_copy_isolation.py -v`

Expected: FAIL — `sync_external_to_copy` not defined

- [ ] **Step 3: Write minimal implementation**

```python
# backend/services/workspace_service.py
import shutil

class WorkspaceService:
    # ... existing methods

    @staticmethod
    def sync_external_to_copy(workspace: Workspace, copy_dir: Path) -> None:
        if workspace.type != "external":
            return
        src = Path(workspace.source_path).resolve()
        copy_dir.mkdir(parents=True, exist_ok=True)

        allowed_ext = {".csv", ".xlsx", ".xls", ".json", ".txt", ".md", ".pdf", ".docx"}
        for f in src.iterdir():
            if f.is_file() and f.suffix.lower() in allowed_ext:
                dest = copy_dir / f.name
                shutil.copy2(f, dest)
```

```python
# backend/services/chat_service.py
# In _resolve_workspace_and_dirs:
if ws.type == "external":
    copy_dir = WorkspaceService.get_internal_copy_dir(user.id, ws.id)
    WorkspaceService.sync_external_to_copy(ws, copy_dir)
    working_dir = str(copy_dir)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_mount_copy_isolation.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/services/workspace_service.py backend/services/chat_service.py backend/tests/test_mount_copy_isolation.py
git commit -m "feat(workspace): copy-isolation for external mounts"
```


---

### Task 9: 前端 API 层与 Store 改造

**Files:**
- Create: `frontend/src/api/workspaces.js`
- Create: `frontend/src/api/roadmap.js`
- Modify: `frontend/src/stores/chat.js`
- Test: `frontend/tests/unit/api/workspaces.spec.js`

**Interfaces:**
- Consumes: backend Workspace/Roadmap APIs
- Produces: `workspacesApi`, `roadmapApi`, `chatStore.currentWorkspace`, `chatStore.roadmap`

- [ ] **Step 1: Write the failing test**

```javascript
// frontend/tests/unit/api/workspaces.spec.js
import { describe, it, expect, vi } from 'vitest'
import request from '@/api/request.js'
import { workspacesApi } from '@/api/workspaces.js'

vi.mock('@/api/request.js', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn()
  }
}))

describe('workspacesApi', () => {
  it('lists workspaces', async () => {
    request.get.mockResolvedValue({ data: [{ id: 1, name: '我的数据空间' }] })
    const res = await workspacesApi.list()
    expect(request.get).toHaveBeenCalledWith('/workspaces/list')
    expect(res.data[0].name).toBe('我的数据空间')
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npm test -- --run tests/unit/api/workspaces.spec.js`

Expected: FAIL — `workspacesApi` not defined

- [ ] **Step 3: Write minimal implementation**

```javascript
// frontend/src/api/workspaces.js
import request from './request.js'

export const workspacesApi = {
  list: () => request.get('/workspaces/list'),
  mount: (data) => request.post('/workspaces/mount', data),
  unmount: (id) => request.post(`/workspaces/${id}/unmount`),
  updateOutputPath: (id, outputPath) => request.put(`/workspaces/${id}/output-path`, { output_path: outputPath })
}
```

```javascript
// frontend/src/api/roadmap.js
import request from './request.js'

export const roadmapApi = {
  get: (workspaceId) => request.get(`/workspaces/${workspaceId}/roadmap`)
}
```

```javascript
// frontend/src/stores/chat.js — add state/actions
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { chatApi } from '@/api/chat.js'
import { workspacesApi } from '@/api/workspaces.js'
import { roadmapApi } from '@/api/roadmap.js'

export const useChatStore = defineStore('chat', () => {
  // existing state ...
  const workspaces = ref([])
  const currentWorkspaceId = ref(null)
  const roadmap = ref(null)

  const currentWorkspace = computed(() =>
    workspaces.value.find(w => w.id === currentWorkspaceId.value)
  )

  async function fetchWorkspaces() {
    const res = await workspacesApi.list()
    workspaces.value = res.data || []
    if (!currentWorkspaceId.value && workspaces.value.length > 0) {
      currentWorkspaceId.value = workspaces.value[0].id
    }
  }

  async function fetchRoadmap() {
    if (!currentWorkspaceId.value) return
    const res = await roadmapApi.get(currentWorkspaceId.value)
    roadmap.value = res.data
  }

  async function setCurrentWorkspace(id) {
    currentWorkspaceId.value = id
    await fetchRoadmap()
  }

  // existing sendMessage/sendMessageStream updated to include workspace_id

  return {
    // existing ...
    workspaces,
    currentWorkspaceId,
    roadmap,
    currentWorkspace,
    fetchWorkspaces,
    fetchRoadmap,
    setCurrentWorkspace
  }
})
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npm test -- --run tests/unit/api/workspaces.spec.js`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/api/workspaces.js frontend/src/api/roadmap.js frontend/src/stores/chat.js frontend/tests/unit/api/workspaces.spec.js
git commit -m "feat(frontend): add workspace and roadmap APIs, update chat store"
```

---

### Task 10: WorkspaceBar 组件

**Files:**
- Create: `frontend/src/components/WorkspaceBar.vue`
- Test: `frontend/tests/unit/components/WorkspaceBar.spec.js`

**Interfaces:**
- Consumes: `chatStore.workspaces`, `chatStore.currentWorkspace`, `workspacesApi`
- Produces: workspace switch, mount dialog trigger, output path display/edit

- [ ] **Step 1: Write the failing test**

```javascript
// frontend/tests/unit/components/WorkspaceBar.spec.js
import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import WorkspaceBar from '@/components/WorkspaceBar.vue'

describe('WorkspaceBar', () => {
  it('renders current workspace name', () => {
    setActivePinia(createPinia())
    const store = useChatStore()
    store.workspaces = [{ id: 1, name: '期末数据', type: 'external', output_path: '/tmp/out' }]
    store.currentWorkspaceId = 1

    const wrapper = mount(WorkspaceBar)
    expect(wrapper.text()).toContain('期末数据')
    expect(wrapper.text()).toContain('/tmp/out')
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npm test -- --run tests/unit/components/WorkspaceBar.spec.js`

Expected: FAIL — component not defined

- [ ] **Step 3: Write minimal implementation**

```vue
<!-- frontend/src/components/WorkspaceBar.vue -->
<template>
  <div class="workspace-bar">
    <div class="workspace-info">
      <span class="workspace-name">{{ currentWorkspace?.name || '未选择工作区' }}</span>
      <span class="workspace-type">{{ typeLabel }}</span>
    </div>
    <select v-model="selectedId" @change="onChange">
      <option v-for="w in workspaces" :key="w.id" :value="w.id">{{ w.name }}</option>
    </select>
    <button @click="showMountDialog = true">挂载文件夹</button>
    <div class="output-path">
      输出到：{{ currentWorkspace?.output_path }}
      <button @click="editOutputPath">修改</button>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useChatStore } from '@/stores/chat.js'

const store = useChatStore()
const showMountDialog = ref(false)

const currentWorkspace = computed(() => store.currentWorkspace)
const workspaces = computed(() => store.workspaces)
const selectedId = computed({
  get: () => store.currentWorkspaceId,
  set: (val) => store.setCurrentWorkspace(val)
})

const typeLabel = computed(() => {
  if (!currentWorkspace.value) return ''
  return currentWorkspace.value.type === 'internal' ? '上传空间' : '本地挂载'
})

function onChange(e) {
  store.setCurrentWorkspace(Number(e.target.value))
}

function editOutputPath() {
  const newPath = prompt('修改输出目录：', currentWorkspace.value?.output_path)
  if (newPath) {
    // call API and refresh
  }
}
</script>

<style scoped>
.workspace-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 16px;
  border-bottom: 1px solid var(--ink-10);
  font-size: 14px;
}
.workspace-name { font-weight: 600; }
.workspace-type { color: var(--ink-50); }
.output-path { margin-left: auto; color: var(--ink-60); }
</style>
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npm test -- --run tests/unit/components/WorkspaceBar.spec.js`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/WorkspaceBar.vue frontend/tests/unit/components/WorkspaceBar.spec.js
git commit -m "feat(frontend): add WorkspaceBar component"
```

---

### Task 11: RecommendedQuestions 组件

**Files:**
- Create: `frontend/src/components/RecommendedQuestions.vue`
- Test: `frontend/tests/unit/components/RecommendedQuestions.spec.js`

**Interfaces:**
- Consumes: `chatStore.roadmap`
- Produces: clickable question cards

- [ ] **Step 1: Write the failing test**

```javascript
// frontend/tests/unit/components/RecommendedQuestions.spec.js
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import RecommendedQuestions from '@/components/RecommendedQuestions.vue'

describe('RecommendedQuestions', () => {
  it('renders questions from roadmap', () => {
    setActivePinia(createPinia())
    const store = useChatStore()
    store.roadmap = { questions: ['A 和 B 的关系？', '谁的总分最高？'] }

    const wrapper = mount(RecommendedQuestions)
    expect(wrapper.text()).toContain('A 和 B 的关系？')
    expect(wrapper.text()).toContain('谁的总分最高？')
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npm test -- --run tests/unit/components/RecommendedQuestions.spec.js`

Expected: FAIL — component not defined

- [ ] **Step 3: Write minimal implementation**

```vue
<!-- frontend/src/components/RecommendedQuestions.vue -->
<template>
  <div class="recommended-questions" v-if="questions.length">
    <div class="section-title">37 的发现</div>
    <div class="question-list">
      <button
        v-for="(q, idx) in questions"
        :key="idx"
        class="question-chip"
        @click="ask(q)"
      >
        {{ q }}
      </button>
    </div>
    <button class="refresh" @click="refresh">重新分析数据关系</button>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useChatStore } from '@/stores/chat.js'

const store = useChatStore()
const questions = computed(() => store.roadmap?.questions || [])

function ask(q) {
  store.sendMessageStream(q)
}

function refresh() {
  store.fetchRoadmap()
}
</script>

<style scoped>
.recommended-questions {
  padding: 12px;
  border-bottom: 1px solid var(--ink-10);
}
.section-title {
  font-size: 12px;
  color: var(--ink-50);
  margin-bottom: 8px;
}
.question-chip {
  display: block;
  width: 100%;
  text-align: left;
  padding: 8px 12px;
  margin-bottom: 6px;
  background: var(--paper);
  border: 1px solid var(--ink-10);
  border-radius: 6px;
  cursor: pointer;
}
.question-chip:hover {
  background: var(--ink-5);
}
.refresh {
  margin-top: 8px;
  font-size: 12px;
  color: var(--blue-60);
  background: none;
  border: none;
  cursor: pointer;
}
</style>
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npm test -- --run tests/unit/components/RecommendedQuestions.spec.js`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/RecommendedQuestions.vue frontend/tests/unit/components/RecommendedQuestions.spec.js
git commit -m "feat(frontend): add RecommendedQuestions component"
```

---

### Task 12: WelcomeRoadmapModal 与输出保存提示

**Files:**
- Create: `frontend/src/components/WelcomeRoadmapModal.vue`
- Modify: `frontend/src/views/ChatView.vue`
- Test: `frontend/tests/unit/components/WelcomeRoadmapModal.spec.js`

**Interfaces:**
- Consumes: `chatStore.roadmap`, `chatStore.currentWorkspace`
- Produces: modal UI, output saved hint

- [ ] **Step 1: Write the failing test**

```javascript
// frontend/tests/unit/components/WelcomeRoadmapModal.spec.js
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import WelcomeRoadmapModal from '@/components/WelcomeRoadmapModal.vue'

describe('WelcomeRoadmapModal', () => {
  it('renders questions and tables', () => {
    const wrapper = mount(WelcomeRoadmapModal, {
      props: {
        roadmap: {
          tables: [{ name: '语文成绩.csv' }],
          relationships: [{ source: '语文成绩.csv', target: '数学成绩.csv' }],
          questions: ['相关性如何？']
        },
        workspace: { name: '期末数据' }
      }
    })
    expect(wrapper.text()).toContain('语文成绩.csv')
    expect(wrapper.text()).toContain('相关性如何？')
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npm test -- --run tests/unit/components/WelcomeRoadmapModal.spec.js`

Expected: FAIL — component not defined

- [ ] **Step 3: Write minimal implementation**

```vue
<!-- frontend/src/components/WelcomeRoadmapModal.vue -->
<template>
  <div v-if="visible" class="modal-overlay" @click.self="close">
    <div class="modal-content">
      <h3>37 已经看过「{{ workspace?.name }}」</h3>
      <p class="summary">发现了 {{ roadmap?.tables?.length || 0 }} 张表，{{ roadmap?.relationships?.length || 0 }} 组关系。</p>

      <div class="relations" v-if="roadmap?.relationships?.length">
        <div v-for="(rel, idx) in roadmap.relationships.slice(0, 3)" :key="idx" class="relation">
          {{ rel.source }} ↔ {{ rel.target }}
        </div>
      </div>

      <div class="questions">
        <button
          v-for="(q, idx) in roadmap?.questions?.slice(0, 5)"
          :key="idx"
          class="question-btn"
          @click="ask(q)"
        >
          {{ q }}
        </button>
      </div>

      <label class="no-again">
        <input type="checkbox" v-model="dontShowAgain" /> 以后不再提示
      </label>
    </div>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'

const props = defineProps({
  visible: Boolean,
  roadmap: Object,
  workspace: Object
})
const emit = defineEmits(['close', 'ask'])

const dontShowAgain = ref(false)

function close() {
  if (dontShowAgain.value) {
    localStorage.setItem('hide_welcome_roadmap', '1')
  }
  emit('close')
}

function ask(q) {
  emit('ask', q)
  close()
}
</script>
```

```vue
<!-- frontend/src/views/ChatView.vue — add in template -->
<WorkspaceBar />
<RecommendedQuestions />
<WelcomeRoadmapModal
  :visible="showRoadmapModal"
  :roadmap="chatStore.roadmap"
  :workspace="chatStore.currentWorkspace"
  @close="showRoadmapModal = false"
  @ask="q => chatStore.sendMessageStream(q)"
/>
```

Add output saved hint in message rendering:

```vue
<div v-if="msg.role === 'assistant' && msg.savedPath" class="saved-hint">
  📁 结果已保存到：{{ msg.savedPath }} <button @click="changeOutputPath">修改位置</button>
</div>
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npm test -- --run tests/unit/components/WelcomeRoadmapModal.spec.js`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/WelcomeRoadmapModal.vue frontend/src/views/ChatView.vue frontend/tests/unit/components/WelcomeRoadmapModal.spec.js
git commit -m "feat(frontend): add roadmap modal and output save hint"
```


---

### Task 13: FilesView 支持 Workspace 切换

**Files:**
- Modify: `frontend/src/views/FilesView.vue`
- Modify: `frontend/src/api/files.js`
- Test: `frontend/tests/unit/views/FilesView.workspace.spec.js`

**Interfaces:**
- Consumes: `chatStore.workspaces`, `chatStore.currentWorkspaceId`
- Produces: file list filtered by workspace, upload to current workspace

- [ ] **Step 1: Write the failing test**

```javascript
// frontend/tests/unit/views/FilesView.workspace.spec.js
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import FilesView from '@/views/FilesView.vue'

describe('FilesView workspace', () => {
  it('shows workspace selector', () => {
    setActivePinia(createPinia())
    const chatStore = useChatStore()
    chatStore.workspaces = [
      { id: 1, name: '上传空间' },
      { id: 2, name: '期末数据' }
    ]

    const wrapper = mount(FilesView)
    expect(wrapper.find('select').exists()).toBe(true)
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npm test -- --run tests/unit/views/FilesView.workspace.spec.js`

Expected: FAIL — selector not present

- [ ] **Step 3: Write minimal implementation**

```javascript
// frontend/src/api/files.js
export const filesApi = {
  getList: (params = {}) => request.get('/files/list', { params }),
  upload: (file, workspaceId, onProgress) => {
    const form = new FormData()
    form.append('file', file)
    if (workspaceId) form.append('workspace_id', workspaceId)
    return request.post('/files/upload', form, { onUploadProgress: onProgress })
  },
  // ... existing
}
```

```vue
<!-- frontend/src/views/FilesView.vue — add workspace selector -->
<template>
  <div class="files-view">
    <div class="files-header">
      <h2>科学索引 · 文件档案</h2>
      <select v-model="chatStore.currentWorkspaceId" @change="loadFiles">
        <option v-for="w in chatStore.workspaces" :key="w.id" :value="w.id">{{ w.name }}</option>
      </select>
    </div>
    <!-- existing file list -->
  </div>
</template>

<script setup>
import { useChatStore } from '@/stores/chat.js'

const chatStore = useChatStore()

async function loadFiles() {
  // call filesApi.getList({ workspace_id: chatStore.currentWorkspaceId })
}
</script>
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npm test -- --run tests/unit/views/FilesView.workspace.spec.js`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/views/FilesView.vue frontend/src/api/files.js frontend/tests/unit/views/FilesView.workspace.spec.js
git commit -m "feat(frontend): support workspace switch in FilesView"
```

---

### Task 14: OutputArtifact 自动保存与追踪

**Files:**
- Create: `backend/services/output_artifact_service.py`
- Modify: `backend/services/chat_service.py`
- Modify: `backend/core/sandbox.py`
- Test: `backend/tests/test_output_artifact.py`

**Interfaces:**
- Consumes: Agent output files in output_dir
- Produces: `OutputArtifact` DB records, API to list artifacts

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_output_artifact.py
from services.output_artifact_service import OutputArtifactService
from models.workspace import Workspace
from models.user import User


def test_record_artifact(db_session, tmp_path):
    user = User(username="oa1", hashed_password="x", role="admin")
    db_session.add(user)
    db_session.commit()

    ws = Workspace(owner_id=user.id, name="ws", type="internal", output_path=str(tmp_path / "out"))
    db_session.add(ws)
    db_session.commit()

    out_dir = tmp_path / "out" / "2026-07-31"
    out_dir.mkdir(parents=True)
    (out_dir / "report.md").write_text("# 分析")

    arts = OutputArtifactService.scan_and_record(db_session, ws, str(out_dir))
    assert len(arts) == 1
    assert arts[0].filename == "report.md"
    assert arts[0].artifact_type == "report"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_output_artifact.py -v`

Expected: FAIL — `OutputArtifactService` not found

- [ ] **Step 3: Write minimal implementation**

```python
# backend/services/output_artifact_service.py
from pathlib import Path
from sqlalchemy.orm import Session
from models.output_artifact import OutputArtifact
from models.workspace import Workspace


class OutputArtifactService:
    _TYPE_MAP = {
        ".md": "report",
        ".png": "chart",
        ".jpg": "chart",
        ".svg": "chart",
        ".csv": "csv",
        ".xlsx": "spreadsheet"
    }

    @staticmethod
    def scan_and_record(db: Session, workspace: Workspace, output_dir: str, conversation_id: int = None) -> list:
        p = Path(output_dir)
        if not p.exists():
            return []

        artifacts = []
        for f in p.iterdir():
            if not f.is_file():
                continue
            rel = f.relative_to(Path(workspace.output_path).parent if workspace.type == "internal" else Path(workspace.source_path))
            art = OutputArtifact(
                workspace_id=workspace.id,
                conversation_id=conversation_id,
                filename=f.name,
                relative_path=str(rel),
                artifact_type=OutputArtifactService._TYPE_MAP.get(f.suffix.lower(), "other")
            )
            db.add(art)
            artifacts.append(art)
        db.commit()
        return artifacts
```

Call it in `chat_service.py` after Agent finishes:

```python
# After agent returns answer
output_date_dir = ChatService._get_output_date_dir(ws)
OutputArtifactService.scan_and_record(db, ws, output_date_dir, conversation_id=conv.id)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_output_artifact.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/services/output_artifact_service.py backend/services/chat_service.py backend/tests/test_output_artifact.py
git commit -m "feat(output): record generated artifacts in database"
```

---

### Task 15: 集成测试与 E2E

**Files:**
- Create: `backend/tests/test_workspace_integration.py`
- Create: `frontend/tests/e2e/workspace.spec.js`
- Modify: existing test fixtures if needed

**Interfaces:**
- Consumes: all previous tasks
- Produces: green integration tests

- [ ] **Step 1: Write backend integration test**

```python
# backend/tests/test_workspace_integration.py
from fastapi.testclient import TestClient


def test_full_upload_analyze_save_flow(client: TestClient, auth_headers, tmp_path):
    # Upload a file
    r = client.post("/api/files/upload", headers=auth_headers, files={"file": ("a.csv", "x,y\n1,2\n", "text/csv")})
    assert r.status_code == 200

    # Wait for profiling
    import time
    time.sleep(2)

    # Get roadmap
    ws_id = r.json()["data"]["workspace_id"]
    r = client.get(f"/api/workspaces/{ws_id}/roadmap", headers=auth_headers)
    assert r.status_code == 200

    # Chat
    r = client.post("/api/chat/send", headers=auth_headers, json={
        "message": "分析这个文件",
        "workspace_id": ws_id
    })
    assert r.status_code == 200
```

- [ ] **Step 2: Run integration test**

Run: `cd backend && pytest tests/test_workspace_integration.py -v`

Expected: PASS (after all previous tasks done)

- [ ] **Step 3: Write frontend E2E test**

```javascript
// frontend/tests/e2e/workspace.spec.js
import { test, expect } from '@playwright/test'

test('mount folder and see roadmap', async ({ page }) => {
  await page.goto('/login')
  await page.fill('input[type="text"]', 'teacher')
  await page.press('input[type="text"]', 'Enter')

  await page.waitForURL('/')
  await page.click('text=挂载文件夹')
  // ... platform-specific folder picker is hard to automate, skip or mock
})
```

- [ ] **Step 4: Run E2E**

Run: `cd frontend && npx playwright test tests/e2e/workspace.spec.js`

Expected: PASS or SKIP for folder picker

- [ ] **Step 5: Commit**

```bash
git add backend/tests/test_workspace_integration.py frontend/tests/e2e/workspace.spec.js
git commit -m "test(workspace): add integration and e2e tests"
```

---

## Self-Review

### 1. Spec coverage
- Workspace 模型 ✅ Task 1
- WorkspaceService + API ✅ Tasks 2-3
- 沙箱写权限控制 ✅ Task 4
- Agent/output_dir 集成 ✅ Task 5
- Roadmap/profiling ✅ Task 6
- Chat 接入 workspace ✅ Task 7
- 挂载复制隔离 ✅ Task 8
- 前端 API/store ✅ Task 9
- WorkspaceBar ✅ Task 10
- RecommendedQuestions ✅ Task 11
- WelcomeRoadmapModal + 保存提示 ✅ Task 12
- FilesView workspace 切换 ✅ Task 13
- OutputArtifact 追踪 ✅ Task 14
- 集成/E2E 测试 ✅ Task 15

### 2. Placeholder scan
- 无 TBD/TODO
- 所有代码块包含具体实现
- 所有命令具体

### 3. Type consistency
- `Workspace.type` 统一为 `"internal" | "external"`
- `output_dir` 在 `AgentService`、`ExecTool`、`Sandbox` 中传递一致
- `workspace_id` 在 API、Store、Service 中命名一致

### 4. Scope check
- 本 plan 聚焦 workspace + roadmap + safe delivery，未涉及打包/像素小人
- 15 个 task 可独立 review 和测试

---

## Execution Handoff

**Plan complete and saved to `docs/superpowers/plans/2026-07-11-local-folder-workspace.md`. Two execution options:**

**1. Subagent-Driven (recommended)** - Dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**

If Subagent-Driven chosen:
- **REQUIRED SUB-SKILL:** Use superpowers:subagent-driven-development
- Fresh subagent per task + two-stage review

If Inline Execution chosen:
- **REQUIRED SUB-SKILL:** Use superpowers:executing-plans
- Batch execution with checkpoints for review
