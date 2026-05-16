# YOLO 夜间约束（2026-05-10）

## 绝对禁止
1. 不要执行 rm、drop table、delete from 等破坏性命令
2. 不要修改 .env、Dockerfile、docker-compose.yml、nginx.conf
3. 不要执行任何 git 命令
4. 不要安装系统级依赖（apt/brew），pip/npm 安装仅限当前任务必需且先检查是否已存在
5. 不要修改数据库 schema（不新建业务表、不改现有字段、不迁移数据）

## 探索性任务特殊约束
- Task 1 所有代码必须放在 experiments/ 目录，视为一次性原型
- 不要试图将原型今晚就耦合进主业务流（如自动替换现有读取逻辑）
- 若发现需要大规模重构现有代码才能继续，立即停止并记录原因

## 前端任务特殊约束
- 保持现有路由和页面结构不变
- 复用现有 API 封装层（如 api/upload.ts 或等价文件），不要重复写 axios/fetch 底层
- 拖拽组件样式与现有设计系统保持一致

## 失败处理
- 单任务连续报错/测试失败超过 3 次，停止该任务并创建 `experiments/TASK_ERROR_LOG.md` 记录