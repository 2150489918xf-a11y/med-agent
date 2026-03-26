# MedAgent 快速启动指南

> 面向新加入项目的开发者，5分钟内启动所有服务。

## 前提条件

| 工具 | 版本 | 安装方式 |
| ---- | ---- | -------- |
| Python | 3.12+ | https://python.org |
| uv | latest | `pip install uv` |
| Node.js | 20+ | https://nodejs.org |
| pnpm | 9+ | `npm install -g pnpm` |

> Nginx 已内置在 `docker/nginx/nginx.exe`，无需额外安装。

## 第一步：克隆仓库

```powershell
git clone https://github.com/2150489918xf-a11y/med-agent.git
cd med-agent/1_core_orchestrator
```

## 第二步：配置环境变量

在 `backend/` 目录下创建 `.env` 文件（**向项目负责人索要**，内含 API Key 不在 git 中）：

```env
# SiliconFlow API Key（必需）
SILICONFLOW_API_KEY=sk-你的真实Key

# Tavily 搜索 Key（必需，网络搜索功能）
TAVILY_API_KEY=tvly-你的真实Key

# LangSmith 追踪（可选，调试用）
LANGSMITH_TRACING=true
LANGSMITH_ENDPOINT=https://api.smith.langchain.com
LANGSMITH_API_KEY=你的LangSmith_Key
LANGSMITH_PROJECT=deerflow-new
```

## 第三步：安装依赖

```powershell
# 后端
cd backend
uv sync

# 前端
cd ../frontend
pnpm install
```

## 第四步：启动服务

需要开 **4 个终端窗口**，依次启动：

### 终端 1 — LangGraph Server（Agent 引擎，端口 2024）

```powershell
cd 1_core_orchestrator/backend
uv run python -m langgraph_cli dev --no-browser --allow-blocking --no-reload
```

### 终端 2 — Gateway API（后端网关，端口 8001）

```powershell
cd 1_core_orchestrator/backend
$env:PYTHONPATH="."; uv run python -m uvicorn app.gateway.app:app --host 0.0.0.0 --port 8001
```

### 终端 3 — Next.js Frontend（前端，端口 3000）

```powershell
cd 1_core_orchestrator/frontend
$env:SKIP_ENV_VALIDATION="1"; pnpm dev
```

### 终端 4 — Nginx 反向代理（统一入口，端口 2026）

```powershell
cd 1_core_orchestrator/docker/nginx
.\nginx.exe -c nginx.local.conf
```

## 第五步：访问

浏览器打开 **http://localhost:2026**

## 常见问题

### Q: 启动 LangGraph Server 报错 `uv trampoline`？
Windows 下不要用 `langgraph dev`，必须用 `python -m langgraph_cli dev`。

### Q: 前端页面打开但无法对话？
检查 LangGraph Server（:2024）和 Gateway（:8001）是否都已启动，以及 Nginx 是否在运行。

### Q: 如何停止 Nginx？
```powershell
cd 1_core_orchestrator/docker/nginx
.\nginx.exe -s stop
```

### Q: 前端需要改哪些代码？
参考 `AI_QUICK_HANDOFF.md` 第4节（Critical Entry Points → Frontend）。

## 项目结构速览

```
med-agent/
└── 1_core_orchestrator/
    ├── backend/              ← 后端（Python, LangGraph + FastAPI）
    │   ├── config.yaml       ← 运行时配置（模型、子Agent等）
    │   ├── .env              ← 环境变量（API Key，不在git中）
    │   └── app/gateway/      ← Gateway API 路由
    ├── frontend/             ← 前端（Next.js + React）
    │   └── src/core/models/  ← 模型相关 API/Hooks/Types
    ├── docker/nginx/         ← Nginx 反向代理
    └── AI_QUICK_HANDOFF.md   ← AI/开发者快速交接文档
```
