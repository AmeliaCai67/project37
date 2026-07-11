# 本地文件夹工作空间（Local Folder Workspace）设计文档

> **目标读者**：后续负责实现的工程师  
> **对应需求**：Project 37 核心功能点 #3（一键挂载 + 自动探索路线图）与 #4（无痕安全交付）

---

## 1. 一句话目标

让用户把“一整个文件夹”交给 37，37 自动理解里面的表格关系并推荐问题，同时以只读方式分析、把交付物自动归档到用户可见的输出目录，完全不碰原数据。

---

## 2. 范围与边界

**包含在本 spec 内：**
- Workspace 抽象（上传模式 + 挂载模式）
- 文件夹挂载 / 卸载 API 与生命周期
- 自动 schema profiling 与推荐问题生成
- 用户可见的 Roadmap UI（侧边栏 + 首次进入弹窗）
- 输出目录管理（默认 `37-output/YYYY-MM-DD/`，用户可修改）
- Agent 只读约束与沙箱写权限控制
- 自动保存分析交付物到输出目录

**明确不包含：**
- 打包 / 双击安装（功能点 #1）
- 桌面像素小人 37（功能点 #2）
- 付费、多用户协作、云端同步
- 持续监听文件夹变化（inotify / FSEvents）——本次只支持显式触发重跑

---

## 3. 用户故事与验收标准

### 故事 A：上传模式
> 张老师从 U 盘拷了几张期末成绩表，想直接拖到 37 里分析。

**验收标准：**
- 她可以拖拽上传 CSV/Excel 到 37
- 上传完成后，37 自动分析表格关系
- 她看到推荐问题：“语文成绩和数学成绩的相关性如何？”
- 她点击问题后得到回答，回答下方提示结果已保存到 `37-output/2026-07-31/`

### 故事 B：挂载模式
> 李老师电脑里有一个专门放数据的文件夹，他不想每次都上传。

**验收标准：**
- 他可以选择本地文件夹挂载到 37
- 37 只读访问该文件夹，不修改原文件
- 分析结果自动保存到该文件夹下的 `37-output/YYYY-MM-DD/`
- 他可以在 UI 上修改输出目录

### 故事 C：安全保证
> 王老师担心 AI 会改乱他的原始数据。

**验收标准：**
- 37 的系统提示明确禁止修改/删除源文件
- Agent 执行 Python 时，沙箱只允许写入输出目录
- 如果 Agent 代码试图覆盖源文件，执行失败并返回错误

---

## 4. 架构设计

```
┌─────────────────────────────────────────────────────────────┐
│                         前端 Vue 3                           │
│  ┌─────────────┐  ┌──────────────────┐  ┌─────────────────┐ │
│  │ WorkspaceBar│  │ RecommendedQuestions│ │ WelcomeRoadmapModal│ │
│  └─────────────┘  └──────────────────┘  └─────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                       FastAPI 后端                           │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │ workspace   │  │   roadmap   │  │   chat (existing)   │  │
│  │   API       │  │   API       │  │                     │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │ FileService │  │RoadmapService│  │   AgentService      │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
│  ┌─────────────────────────────────────────────────────────┐│
│  │         SchemaProfiler (from YOLO branch)               ││
│  └─────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                     本地文件系统                             │
│   <workspace>/                                              │
│   ├── 源文件.csv  （只读）                                   │
│   └── 37-output/YYYY-MM-DD/  （可写）                        │
└─────────────────────────────────────────────────────────────┘
```

### 关键设计决策

| 决策 | 选择 | 理由 |
|---|---|---|
| 上传 vs 挂载 | **两者都支持** | 上传解决 U 盘/临时文件；挂载解决已有数据目录 |
| 挂载只读策略 | **第一阶段用复制隔离；后续优化为 OS 只读挂载** | 跨平台 OS 只读实现复杂；复制隔离能立即保证不污染用户原文件夹 |
| 推荐问题生成 | **LLM 首次进入 + 规则 fallback** | 每次打开都有新鲜感；失败时仍有保底 |
| 输出目录 | **默认 `<workspace>/37-output/YYYY-MM-DD/`，可修改** | 傻瓜式自动归档，同时给用户控制权 |
| 自动保存 | **所有交付物自动保存** | 减少用户操作，符合“无痕交付” |

---

## 5. 数据模型

### 5.1 Workspace（新增）

```python
class Workspace(Base):
    __tablename__ = "workspaces"

    id = Column(Integer, primary_key=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String, nullable=False)  # 用户可自定义，默认 "我的数据空间"
    type = Column(String, nullable=False)  # "internal" | "external"
    source_path = Column(String, nullable=True)  # 外部挂载的本地绝对路径；internal 为 None
    output_path = Column(String, nullable=False)  # 输出目录绝对路径
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
```

**说明：**
- 每个用户默认有一个 `internal` workspace，source_path 指向 `uploads/user_{id}/`
- 外部挂载创建新的 `external` workspace
- `output_path` 用户可修改；internal 默认 `uploads/user_{id}/37-output/`

### 5.2 File（修改）

```python
class File(Base):
    # 现有字段不变
    workspace_id = Column(Integer, ForeignKey("workspaces.id"), nullable=True)
```

**说明：**
- 上传的文件关联到 internal workspace
- 外部挂载的文件在首次 profiling 时扫描生成 File 记录，便于后续列表展示

### 5.3 OutputArtifact（新增，P0 必须）

```python
class OutputArtifact(Base):
    __tablename__ = "output_artifacts"

    id = Column(Integer, primary_key=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id"), nullable=False)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), nullable=True)
    filename = Column(String, nullable=False)
    relative_path = Column(String, nullable=False)  # 相对于 workspace 的路径
    artifact_type = Column(String)  # "report" | "chart" | "csv" | "other"
    created_at = Column(DateTime, default=datetime.utcnow)
```

---

## 6. API 设计

### 6.1 Workspace API

```http
GET /api/workspaces/list
```
返回当前用户的 workspace 列表。

```http
POST /api/workspaces/mount
Content-Type: application/json

{
  "local_path": "/Users/teacher/data",
  "name": "期末数据"
}
```
创建 external workspace，校验路径可读，生成默认 output_path。

```http
POST /api/workspaces/{id}/unmount
```
取消挂载，不删除原文件夹，只删除 workspace 记录。

```http
PUT /api/workspaces/{id}/output-path
Content-Type: application/json

{
  "output_path": "/Users/teacher/analysis-output"
}
```
修改输出目录，校验可写。

```http
POST /api/workspaces/{id}/reprofile
```
手动触发重新 profiling。

### 6.2 Roadmap API

```http
GET /api/workspaces/{id}/roadmap
```
返回：

```json
{
  "tables": [
    {"name": "语文成绩.csv", "columns": [...]}
  ],
  "relationships": [
    {"from": "语文成绩.csv.学生姓名", "to": "数学成绩.csv.学生姓名", "type": "one_to_many", "confidence": 0.95}
  ],
  "questions": [
    "语文成绩和数学成绩的相关性如何？"
  ]
}
```

### 6.3 修改现有 API

- `POST /api/files/upload`：增加 `workspace_id` 参数（可选，默认 internal）
- `GET /api/files/list`：增加 `workspace_id` 参数
- `POST /api/chat/send` 与 `/api/chat/send/stream`：增加 `workspace_id` 参数；后端根据 workspace 设置 Agent 的 `working_dir` 和 `output_dir`

---

## 7. 核心服务设计

### 7.1 WorkspaceService

```python
class WorkspaceService:
    @staticmethod
    def get_or_create_internal(user: User) -> Workspace
    @staticmethod
    def mount(user: User, local_path: str, name: str) -> Workspace
    @staticmethod
    def unmount(user: User, workspace_id: int) -> None
    @staticmethod
    def set_output_path(user: User, workspace_id: int, output_path: str) -> Workspace
    @staticmethod
    def get_workspace_path(workspace: Workspace) -> Path
```

### 7.2 RoadmapService

```python
class RoadmapService:
    @staticmethod
    def build_roadmap(workspace: Workspace) -> dict
    @staticmethod
    def generate_questions(workspace: Workspace, schema_graph: dict) -> list[str]
    @staticmethod
    def fallback_questions(schema_graph: dict) -> list[str]
```

**`build_roadmap` 流程：**
1. 调用 `SchemaProfiler.build_and_cache(workspace_path)` 生成/更新 `schema_graph.json`
2. 从缓存读取 schema graph
3. 调用 LLM 生成推荐问题（首次进入 / 挂载 / 上传后）
4. 如果 LLM 失败，使用规则模板 fallback
5. 返回 `{tables, relationships, questions}`

### 7.3 修改 AgentService

```python
class AgentService:
    def __init__(self, working_dir: str, output_dir: str, role: str, ...):
        ...
```

- `working_dir`：源文件目录（只读）
- `output_dir`：可写输出目录
- 系统提示增加：禁止修改/删除 `working_dir` 中源文件，所有写入只能到 `output_dir`

### 7.4 修改沙箱 / ExecTool

```python
# sandbox.py 中 open 函数增强
def _safe_open(path, mode='r', *args, **kwargs):
    p = Path(path).resolve()
    if 'w' in mode or 'a' in mode or 'x' in mode:
        if not _is_under_output_dir(p):
            raise PermissionError(f"Cannot write outside output directory: {path}")
    # 读操作保持现有逻辑
```

---

## 8. 沙箱只读策略详细设计

### 8.1 上传模式（internal workspace）

- 源文件在 `uploads/user_{id}/`
- Agent 的 `working_dir = uploads/user_{id}/`
- `output_dir = uploads/user_{id}/37-output/YYYY-MM-DD/`
- **软约束**：系统提示 + 沙箱禁止写 working_dir 内源文件路径
- 实现简单，不依赖 OS

### 8.2 挂载模式（external workspace）

**第一阶段实现：复制隔离**

- 用户选择本地文件夹挂载后，37 立即把该文件夹下的数据文件复制到内部只读副本：`uploads/user_{id}/mounts/{workspace_id}/`
- Agent 的 `working_dir` 指向这个内部副本
- Agent 禁止写 working_dir 中的任何文件
- 输出目录默认设置为 `<原挂载文件夹>/37-output/YYYY-MM-DD/`
- 用户原文件夹**完全不被读取之外的任何操作触碰**

**后续优化：OS 只读挂载**

- macOS：调研 `sandbox-exec` / `chflags` / FSEvents 的只读约束能力
- Windows：调研 ACL / `icacls` 限制进程写权限
- 目标：避免复制大文件夹，直接原地只读挂载
- 注意：此优化不在第一阶段范围内

---

## 9. 前端 UI/UX 设计

### 9.1 新增组件

#### WorkspaceBar.vue

位置：ChatView 顶部或侧边栏上方

显示内容：
- 当前 workspace 名称
- 模式标签：「上传空间」/「挂载：/Users/teacher/data」
- 输出目录：`输出到 37-output/2026-07-31/ （修改）`
- 切换 workspace 下拉菜单
- 「挂载新文件夹」按钮

#### RecommendedQuestions.vue

位置：ChatView 侧边栏中部

显示内容：
- 标题：「37 的发现」
- 3-5 个推荐问题卡片
- 每个问题可点击，点击后自动填入输入框并发送
- 底部：「重新分析数据关系」按钮

#### WelcomeRoadmapModal.vue

触发时机：
- 应用启动后首次进入 ChatView 且 workspace 有文件
- 用户挂载新文件夹后

显示内容：
- 「37 已经看过你的数据，发现了这些：」
- 表格列表 + 关键关系一句话描述
- 推荐问题大按钮
- 「以后不再提示」checkbox

### 9.2 修改组件

#### ChatView.vue
- 集成 WorkspaceBar
- 集成 RecommendedQuestions
- Agent 回答后显示输出保存路径提示

#### FilesView.vue
- 增加 workspace 切换
- 显示当前 workspace 的文件
- 上传时关联到当前 workspace

---

## 10. 推荐问题生成规则

### LLM Prompt 模板

```
你是一个数据分析师。用户的数据文件夹里有以下表格和它们之间的关系：

{schema_graph_summary}

请生成 3-5 个自然语言分析问题，帮助非技术用户快速开始数据分析。
要求：
- 问题要具体，直接对应表格和字段
- 优先推荐有明确关联关系的问题
- 不要涉及复杂统计术语
- 每个问题一句话
```

### Fallback 规则模板

当 schema graph 中存在两表可通过某字段关联时：
- `"{table_a} 和 {table_b} 可以通过 {column} 关联，你想分析它们之间的关系吗？"`
- `"按 {group_column} 汇总 {value_column} 会怎样？"`
- `"{date_column} 随时间的变化趋势如何？"`

---

## 11. 输出目录与自动保存

### 默认输出目录结构

```
<workspace>/
└── 37-output/
    └── 2026-07-31/
        ├── 成绩分析报告.md
        ├── 语文数学相关性.png
        └── 汇总结果.csv
```

### 自动保存规则

- Agent 生成的 Markdown 报告：自动保存为 `分析结论.md`
- Agent 生成的图表（matplotlib/plotly）：自动保存为 PNG/SVG
- Agent 生成的结果表：自动保存为 CSV
- 所有文件名带时间戳前缀避免覆盖：`20260731_173000_分析结论.md`

### UI 提示

每次 Agent 给出最终答案后，在消息底部显示：
> 📁 结果已保存到：`37-output/2026-07-31/` （点击修改位置）

---

## 12. 错误处理

| 错误场景 | 处理策略 |
|---|---|
| 挂载路径不可读 | 返回 400，提示检查权限；不创建 workspace |
| OS 只读挂载失败 | 降级为复制隔离模式；日志记录 |
| Profiling 失败 | 不阻塞聊天；返回空 relationships/questions；提示用户仍可手动提问 |
| 输出目录不可写 | 提示用户修改输出路径；Agent 无法执行写操作 |
| Agent 试图写源文件 | 沙箱拦截，返回 `PermissionError`；Agent 收到 Observation 后应停止或修正 |
| 外部挂载文件夹被用户删除 | workspace 标记为 stale；访问时提示重新挂载 |

---

## 13. 测试策略

### 后端测试

| 测试文件 | 覆盖内容 |
|---|---|
| `tests/test_workspace_service.py` | Workspace CRUD、挂载、输出路径修改 |
| `tests/test_roadmap_service.py` | Profiling 触发、推荐问题生成、fallback |
| `tests/test_sandbox_write_guard.py` | 禁止写源文件、允许写输出目录 |
| `tests/test_chat_workspace_integration.py` | chat API 带 workspace_id、输出目录正确 |

### 前端测试

| 测试文件 | 覆盖内容 |
|---|---|
| `tests/unit/components/WorkspaceBar.spec.js` | 显示 workspace、切换、修改输出路径 |
| `tests/unit/components/RecommendedQuestions.spec.js` | 点击推荐问题、重新分析 |
| `tests/unit/views/ChatView.workspace.spec.js` | workspace 集成、保存提示 |

### E2E 测试

- 挂载测试文件夹 → 提问 → 验证结果保存到 `37-output/YYYY-MM-DD/`
- 上传文件 → 验证推荐问题出现 → 点击推荐问题 → 验证输出

---

## 14. 实现顺序建议

1. **Workspace 数据模型 + API**（backend）
2. **沙箱写权限控制 + output_dir 概念**（backend）
3. **AgentService 接入 workspace/output_dir**（backend）
4. **推荐问题服务 + Roadmap API**（backend，复用 YOLO profiler）
5. **前端 WorkspaceBar + 推荐问题面板**（frontend）
6. **首次进入弹窗 + 输出保存提示**（frontend）
7. **挂载模式 + 复制隔离**（backend，可选延到后面）
8. **测试补全**

---

## 15. 风险与待决策

| 风险 | 说明 | 建议 |
|---|---|---|
| OS 只读挂载跨平台复杂 | macOS/Windows 机制不同，可能引入大量平台代码 | 第一阶段用复制隔离兜底，后续优化 |
| SchemaProfiler 大文件性能 | 几百 MB CSV profiling 可能耗时 | 继续沿用 YOLO 的采样策略 |
| 外部挂载路径持久化 | 用户移动/删除原文件夹后 workspace 失效 | 增加 stale 检测和重新挂载提示 |
| 推荐问题 LLM 成本 | 每次打开都调用 LLM | 缓存会话内；小 workspace 可用规则替代 |

---

## 16. 附录：与现有代码的关系

### 复用
- `backend/tools/schema_profiler.py`（YOLO）：schema profiling
- `backend/core/tools.py`：注册新工具
- `backend/services/agent_service.py`：接入 workspace/output_dir
- `frontend/src/components/GlobalDropZone.vue`（YOLO）：拖拽上传

### 修改
- `backend/models/file.py`：加 `workspace_id`
- `backend/api/files.py`：上传关联 workspace
- `backend/api/chat.py`：接收 workspace_id
- `frontend/src/views/ChatView.vue`：集成新组件
- `frontend/src/views/FilesView.vue`：支持 workspace 切换

### 新增
- `backend/models/workspace.py`
- `backend/models/output_artifact.py`
- `backend/api/workspaces.py`
- `backend/api/roadmap.py`
- `backend/services/workspace_service.py`
- `backend/services/roadmap_service.py`
- `frontend/src/components/WorkspaceBar.vue`
- `frontend/src/components/RecommendedQuestions.vue`
- `frontend/src/components/WelcomeRoadmapModal.vue`
