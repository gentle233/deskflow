# DeskFlow Vue 3 + FastAPI 重构方案

> **分支:** `refactor/vue3-fastapi`
> **目标:** 将 Flask + HTML/JS 架构重构为 FastAPI + Vue 3

**核心原则：** 不动现有 Python 逻辑模块（agents/、orchestrator/、core/、autolearn/、memory/），只换壳。

## 架构对比

```
当前架构                         重构后架构
┌─────────────────┐            ┌─────────────────┐
│  Flask (main.py) │            │  FastAPI + Uvicorn│
│  ┌─ templates/  │            │  ┌─ api/         │
│  │ chat.html    │            │  │  routes/      │
│  │ settings.html│            │  │  main.py (app)│
│  │ setup.html   │            │  └──────────────│
│  └──────────────│            │                 │
│  ┌─ static/    │            │  ┌─ frontend/    │
│  │ app.js      │            │  │  (Vue 3 +     │
│  │ style.css   │            │  │   Vite 构建)  │
│  └──────────────│            │  └──────────────│
│                 │            │                 │
│  agents/        │  ──复用──  │  agents/        │
│  orchestrator/  │  ──复用──  │  orchestrator/  │
│  core/          │  ──复用──  │  core/          │
│  autolearn/     │  ──复用──  │  autolearn/     │
│  memory/        │  ──复用──  │  memory/        │
└─────────────────┘            └─────────────────┘
```

## 阶段划分

### Phase 1 — 后端迁移 (FastAPI)
将 Flask main.py 拆为 FastAPI 路由，保持 API 接口完全一致

### Phase 2 — 前端库 (Vue 3)
用 Vite + Vue 3 重建 chat 和 settings 页面

### Phase 3 — 构建适配
更新 PyInstaller spec + GitHub Actions + build.bat

---

## Phase 1: FastAPI 后端迁移

### Task 1.1: 创建 FastAPI 入口

**文件：** `api/main.py`

替换 Flask app 为 FastAPI，挂载所有路由：
- 聊天接口 `/api/chat` POST、`/api/chat/stream` SSE
- 配置 `/api/config` GET/POST
- 提供商 `/api/providers/*`
- 快捷指令 `/api/shortcuts/*`
- 自动学习 `/api/autolearn/*`
- 文件监控 `/api/monitor/*`
- 定时任务 `/api/tasks/*`
- 日志 `/api/logs/*`
- 邮件 `/api/email/*`
- 搜索 `/api/config/search`
- 设置 `/api/setup`

### Task 1.2: 保留 main.py 做初始化

**文件：** `main.py`（精简）

只保留 `init_deskflow()` 和 `main()`，启动时从 `api/main.py` import app。

### Task 1.3: SSE 适配

FastAPI 的 SSE 用 `StreamingResponse` 替代 Flask 的 `Response(generator())`。

---

## Phase 2: Vue 3 前端

### Task 2.1: 初始化 Vite + Vue 3

**文件：** `frontend/`

```
frontend/
├── package.json
├── vite.config.ts
├── index.html
├── src/
│   ├── main.ts
│   ├── App.vue
│   ├── router/
│   │   └── index.ts
│   ├── views/
│   │   ├── ChatView.vue      # 主聊天页
│   │   ├── SettingsView.vue   # 配置页
│   │   └── SetupView.vue      # 首次设置页
│   ├── components/
│   │   ├── ChatMessage.vue    # 单条消息
│   │   ├── ChatInput.vue      # 输入框
│   │   ├── SuggestionPanel.vue# 学习建议
│   │   └── ...
│   ├── composables/
│   │   ├── useChat.ts         # 聊天逻辑
│   │   └── useConfig.ts       # 配置API
│   └── assets/
│       └── style.css
└── tsconfig.json
```

### Task 2.2: ChatView 组件

迁移 `chat.html` + `app.js` 到 Vue SFC：
- 消息列表（支持 Markdown + 打字机效果）
- SSE 流式接收
- 文件拖曳/粘贴
- 停止生成按钮
- 旁侧学习建议面板
- 聊天历史持久化（localStorage）

### Task 2.3: SettingsView 组件

迁移 `settings.html` + 内联 JS 到 Vue：
- AI 提供商配置
- 多提供商测试
- 搜索设置
- 邮件设置
- 快捷指令
- 文件监控
- 定时任务
- 日志查看器

### Task 2.4: SetupView 组件

迁移 `setup.html`：
- 首次启动向导
- 选择 provider + API Key

---

## Phase 3: 构建适配

### Task 3.1: 更新 PyInstaller spec

`build.spec` 需要：
- 新增入口 `api/main.py` 或 `main.py`
- 添加 hidden import 适配 FastAPI + uvicorn
- 添加前端构建产物目录

### Task 3.2: 更新 build.bat

- 先 `cd frontend && npm install && npm run build`
- 再 PyInstaller 打包

### Task 3.3: 更新 GitHub Actions

- 添加 Node.js setup step
- 前端构建 step
- 复制 dist/ 到打包目录

---

## 运行验证

```bash
# 后端
cd ~/deskflow
uvicorn api.main:app --host 127.0.0.1 --port 7788 --reload

# 前端（开发模式）
cd ~/deskflow/frontend
npm install
npm run dev  # 默认端口 5173，proxy 到后端 7788

# 生产构建
cd ~/deskflow/frontend
npm run build
# 产物在 frontend/dist/，由 FastAPI 静态文件路由挂载
```

---

## 不动部分（完全复用）

```
agents/         # 所有 Agent（file/window/document/excel/web_search/memory/mail）
orchestrator/   # 引擎 + 调度器 + 意图路由 + 工作流
core/           # 配置/LLM/日志/文件操作/快捷指令/定时任务/文件监控
autolearn/      # 自动学习引擎
memory/         # 记忆系统
```

## 文件清单

| 类型 | 文件 | 动作 |
|------|------|------|
| 新增 | `api/main.py` | FastAPI 应用入口 |
| 新增 | `api/routes/chat.py` | 聊天路由 |
| 新增 | `api/routes/config.py` | 配置路由 |
| 新增 | `api/routes/providers.py` | 提供商路由 |
| 新增 | `api/routes/email.py` | 邮件路由 |
| 新增 | `api/routes/autolearn.py` | 自动学习路由 |
| 新增 | `api/routes/monitor.py` | 文件监控路由 |
| 新增 | `api/routes/tasks.py` | 定时任务路由 |
| 新增 | `api/routes/shortcuts.py` | 快捷指令路由 |
| 新增 | `api/routes/logs.py` | 日志路由 |
| 新增 | `api/__init__.py` | 包标记 |
| 新增 | `frontend/package.json` | 前端依赖 |
| 新增 | `frontend/vite.config.ts` | Vite 配置 |
| 新增 | `frontend/index.html` | 入口 HTML |
| 新增 | `frontend/src/main.ts` | Vue 入口 |
| 新增 | `frontend/src/App.vue` | 根组件 |
| 新增 | `frontend/src/router/index.ts` | 路由 |
| 新增 | `frontend/src/views/ChatView.vue` | 聊天页 |
| 新增 | `frontend/src/views/SettingsView.vue` | 设置页 |
| 新增 | `frontend/src/views/SetupView.vue` | 设置向导 |
| 新增 | `frontend/src/components/...` | 子组件 |
| 修改 | `main.py` | 精简为启动入口 |
| 修改 | `build.spec` | 适配新架构 |
| 修改 | `build.bat` | 添加前端构建 |
| 修改 | `.github/workflows/build.yml` | CI 添加前端构建 |
| 删除 | `ui/` | 旧前端全部移除 |
