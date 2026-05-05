# 问数 - 前端

基于 Vue 3 + Vite 的现代化前端应用。

## 技术栈

- **Vue 3** - 渐进式 JavaScript 框架
- **Vue Router** - 官方路由管理
- **Pinia** - 状态管理
- **Axios** - HTTP 客户端
- **Marked** - Markdown 解析
- **Vite** - 构建工具

## 项目结构

```
frontend/
├── public/                  # 静态资源
│   └── logo.svg
├── src/
│   ├── api/                 # API 接口
│   │   ├── request.js       # Axios 配置
│   │   ├── auth.js          # 认证接口
│   │   ├── chat.js          # 聊天接口
│   │   └── files.js         # 文件接口
│   ├── components/          # 组件
│   │   └── AgentSteps.vue   # Agent 思考过程展示
│   ├── stores/              # Pinia Store
│   │   ├── user.js          # 用户状态
│   │   └── chat.js          # 聊天状态
│   ├── views/               # 页面视图
│   │   ├── LoginView.vue    # 登录页
│   │   ├── HomeView.vue     # 主页布局
│   │   ├── ChatView.vue     # 对话页面
│   │   └── FilesView.vue    # 文件管理
│   ├── router/              # 路由配置
│   │   └── index.js
│   ├── App.vue              # 根组件
│   └── main.js              # 入口文件
├── index.html
├── package.json
├── vite.config.js
└── README.md
```

## 核心功能

### 1. ReAct Agent 展示

`AgentSteps.vue` 组件展示 AI 的思考过程：

```
💭 思考 -> 🔧 行动 -> 📋 观察 -> ... -> 最终答案
```

支持展开/收起，实时流式更新。

### 2. 权限区分

| 权限 | 行为差异 |
|-----|---------|
| 只读 | 必须先选择文件，AI 只分析选定的文件 |
| 读写 | AI 可以自主探索所有文件 |

### 3. 流式输出

实时显示 Agent 的思考过程，支持 SSE 格式。

## 开发

```bash
# 安装依赖
npm install

# 启动开发服务器
npm run dev

# 构建生产版本
npm run build

# 预览生产构建
npm run preview
```

## 环境变量

创建 `.env` 文件：

```env
# API 基础地址
VITE_API_BASE_URL=http://localhost:8000
```

## 与后端集成

开发时代理配置在 `vite.config.js`：

```javascript
server: {
  proxy: {
    '/api': {
      target: 'http://localhost:8000',
      changeOrigin: true,
    }
  }
}
```

## 注意事项

1. **AgentSteps 组件** - 这是展示 ReAct 循环的核心组件
2. **流式输出** - 使用原生 fetch 读取 SSE，而非 axios
3. **文件选择** - 只读用户必须选择文件才能发送消息
4. **权限控制** - 前端只是提示，真正的权限控制在后端

## 待完善

- [ ] 对话历史列表展示
- [ ] 文件预览功能
- [ ] Markdown 代码高亮
- [ ] 移动端适配优化
- [ ] 深色模式
