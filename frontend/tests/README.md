# 前端测试用例

本文档说明前端测试用例的设计和组织。

## 测试工具

- **Vitest** - 单元测试框架（Vite 原生支持）
- **@vue/test-utils** - Vue 组件测试工具
- **jsdom** - DOM 环境模拟
- **Playwright** - 端到端测试

## 目录结构

```
tests/
├── setup.js                     # 测试配置和全局 Mock
├── unit/                        # 单元测试
│   ├── stores/                  # Store 测试
│   │   ├── user.spec.js         # 用户状态测试
│   │   └── chat.spec.js         # 聊天状态测试
│   ├── components/              # 组件测试
│   │   ├── AgentSteps.spec.js   # Agent 步骤组件
│   │   ├── LoginView.spec.js    # 登录页
│   │   └── ChatView.spec.js     # 聊天页
│   └── api/                     # API 测试
│       └── chat.spec.js         # 聊天 API
└── e2e/                         # 端到端测试
    ├── login.spec.js            # 登录流程
    ├── chat-agent.spec.js       # Agent 对话
    └── permissions.spec.js      # 权限控制
```

## 运行测试

```bash
# 安装测试依赖
npm install

# 运行单元测试
npm run test

# 运行单元测试（UI 界面）
npm run test:ui

# 生成覆盖率报告
npm run test:coverage

# 运行端到端测试
npm run test:e2e

# 运行端到端测试（UI 界面）
npm run test:e2e:ui
```

## 测试分类

### 1. Store 测试 (`tests/unit/stores/`)

#### user.spec.js - 用户状态
- **初始状态** - 未登录状态正确
- **权限计算** - 只读/读写/管理员权限判断
- **登录/登出** - 状态变化和 localStorage 同步

#### chat.spec.js - 聊天状态
- **文件选择** - 添加/取消/清空选择
- **Agent 步骤** - 步骤管理和类型识别
- **消息管理** - 发送消息、新对话清空
- **流式状态** - 流式输出状态管理

### 2. 组件测试 (`tests/unit/components/`)

#### AgentSteps.spec.js - 核心组件
- **步骤渲染** - 不同类型步骤正确显示
- **展开/收起** - 点击 header 切换显示
- **类型图标** - thought/action/observation 不同图标
- **错误状态** - 失败步骤红色高亮
- **流式动画** - 思考中闪烁效果

#### LoginView.spec.js - 登录页
- **表单渲染** - 用户名输入、权限选择
- **权限切换** - 点击切换只读/读写/删除
- **输入绑定** - 用户名双向绑定
- **加载状态** - 登录按钮禁用和 loading

#### ChatView.spec.js - 聊天页
- **界面渲染** - 消息区、输入区、侧边栏
- **权限区分** - 只读用户显示文件选择栏
- **消息发送** - 输入、发送、清空
- **流式显示** - Agent 步骤实时展示
- **Markdown** - 消息内容 Markdown 渲染

### 3. API 测试 (`tests/unit/api/`)

#### chat.spec.js - 聊天 API
- **非流式发送** - 正常发送消息
- **流式发送** - fetch 调用和 SSE 处理
- **对话管理** - 获取列表、详情、删除

### 4. 端到端测试 (`tests/e2e/`)

#### login.spec.js - 登录流程
- **页面显示** - 登录表单、权限选项
- **登录流程** - 只读/读写用户完整登录
- **权限说明** - 不同权限的说明文字
- **状态保持** - 刷新后保持登录
- **登出功能** - 退出后回到登录页

#### chat-agent.spec.js - Agent 对话
- **欢迎页面** - 初始显示欢迎信息
- **发送消息** - 输入和发送
- **流式输出** - 实时显示思考过程
- **步骤交互** - 展开/收起 Agent 步骤
- **快速示例** - 点击示例填充输入
- **新建对话** - 清空状态重新开始
- **键盘交互** - Enter 发送、Shift+Enter 换行

#### permissions.spec.js - 权限控制
- **只读用户** - 必须选择文件、不显示上传
- **读写用户** - 无需选文件、显示上传
- **管理员** - 完整权限、可删除文件
- **权限切换** - 切换后界面正确更新

## 关键测试场景

### 场景 1: 只读用户工作流程
```javascript
// 1. 以只读权限登录
// 2. 验证显示文件选择栏
// 3. 尝试不选文件发送，验证提示
// 4. 选择文件
// 5. 发送消息，验证正常
```

### 场景 2: Agent 流式输出
```javascript
// 1. 发送消息
// 2. 验证显示"思考中"
// 3. 接收 thought 步骤，验证显示
// 4. 接收 action 步骤，验证工具名
// 5. 接收 observation，验证结果
// 6. 接收 answer，验证最终答案
// 7. 验证步骤可展开收起
```

### 场景 3: 权限切换
```javascript
// 1. 以只读登录，验证文件选择栏存在
// 2. 登出
// 3. 以读写登录同一账号
// 4. 验证文件选择栏消失
// 5. 验证可直接发送消息
```

## Mock 数据

### localStorage Mock
```javascript
global.localStorage = {
  store: {},
  getItem(key) { return this.store[key] || null },
  setItem(key, value) { this.store[key] = value },
  removeItem(key) { delete this.store[key] },
  clear() { this.store = {} }
}
```

### fetch Mock (SSE)
```javascript
global.fetch = vi.fn(() =>
  Promise.resolve({
    body: new ReadableStream({
      start(controller) {
        // 模拟 SSE 数据
        controller.enqueue(new TextEncoder().encode('data: {"type":"thought"}\n\n'))
        controller.close()
      }
    })
  })
)
```

## 注意事项

1. **Store 测试** - 每个测试前重置 Pinia
2. **组件测试** - 使用 `mount` 挂载组件，`createPinia()` 提供状态
3. **API 测试** - Mock 请求，不调用真实后端
4. **E2E 测试** - 需要前后端服务运行
5. **SSE 测试** - 使用 ReadableStream 模拟流式数据

## 覆盖率目标

| 模块 | 目标覆盖率 |
|-----|-----------|
| stores/user.js | 90%+ |
| stores/chat.js | 85%+ |
| components/AgentSteps.vue | 90%+ |
| views/LoginView.vue | 80%+ |
| views/ChatView.vue | 75%+ |
| api/chat.js | 85%+ |

## 待补充

- [ ] 文件管理页面测试
- [ ] 路由守卫测试
- [ ] 错误处理测试（网络错误、API 错误）
- [ ] 移动端适配测试
- [ ] 性能测试（大数据量渲染）
