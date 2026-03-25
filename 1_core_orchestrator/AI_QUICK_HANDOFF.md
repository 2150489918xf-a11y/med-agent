# 1_core_orchestrator AI Quick Handoff

This document is for coding agents taking over work inside `1_core_orchestrator/`.

> **⚠️ This project has been adapted from generic DeerFlow 2.0 to a medical multi-agent system (MedAgent).**

## 1. First Reality Checks

- This subtree is an active DeerFlow 2.0 fork adapted for **medical diagnosis scenarios**.
- The directory name is `1_core_orchestrator/` (typo was previously fixed).
- Local code is the source of truth. Upstream DeerFlow docs are only a secondary reference.
- Do not assume the monorepo root README describes this subtree's current runtime accurately.

## 2. Medical Agent Architecture

The system uses a **three-agent + one-auxiliary architecture**:

| Agent | Role | Model | Config File |
| ----- | ---- | ----- | ----------- |
| **主Agent (Lead Agent)** | 调度子Agent，识别化验单，网络搜索 | `Qwen/Qwen3.5-397B-A17B` | `agents/lead_agent/prompt.py` |
| **影像Agent (Imaging Agent)** | 接收文件路径，调MCP服务分析医疗影像 | `Qwen/Qwen3-VL-235B-A22B-Thinking` | `subagents/builtins/imaging_agent.py` |
| **医疗知识Agent** | 深度医疗知识检索 | 继承主Agent模型 | `subagents/builtins/medical_knowledge_agent.py` |
| **辅助模型** | 标题生成等低成本任务 | `Qwen/Qwen3-8B` | `config.yaml` title section |

子Agent通过 `task` 工具调度，需要 **Ultra模式** (`subagent_enabled: true`)。

### 多模态图片处理架构（P0-P3 四阶段）

当前已实施 **P0+P1**，采用"纯文本调度管道"模式：

```
用户上传影像 → 主Agent提取文件路径(纯文本) → task工具委派给影像Agent
                                              → 影像Agent调MCP服务(存根)
                                              → 返回结构化文本报告
                                              → 主Agent综合回复用户
```

**核心原则：主Agent对话中不出现Base64编码，图片分析由子Agent在隔离上下文中完成。**

| 阶段 | 状态 | 内容 |
| ---- | ---- | ---- |
| P0 紧急止血 | ✅ 已完成 | ViewImageMiddleware 和 view_image_tool 已注释停用 |
| P1 纯文本管道 | ✅ 已完成 | 主Agent提示词增加 `<image_handling_protocol>`，影像Agent接收路径+返回结构化报告 |
| P2 前置视觉网关 | 🔲 未实施 | CLIP分类器、CV增强、OCR |
| P3 视觉兜底 | 🔲 未实施 | 条件式视觉注入+阅后即焚 |

### P0/P3 代码注释标记说明

所有被停用的视觉代码均保留并用以下标记注释：
- `[P0-DISABLED]` — 标识该代码在P0阶段被停用的原因
- `[P3-REACTIVATE]` — 标识P3阶段恢复该代码时的操作步骤
- `[P3-NOTE]` — 标识为P3阶段预留的配置

涉及文件：
- `agents/lead_agent/agent.py` — ViewImageMiddleware import + 条件加载
- `tools/tools.py` — view_image_tool import + 条件添加
- `tools/builtins/__init__.py` — view_image_tool 导出
- `tests/test_lead_agent_model_resolution.py` — ViewImageMiddleware 断言

### Key Medical Adaptations Made

- **System prompt**: Rewritten in Chinese for medical scenario (`prompt.py`)
- **Image handling protocol**: 主Agent提示词中包含 `<image_handling_protocol>` 定义图片处理三级优先级
- **SOUL.md**: Disabled — `get_agent_soul()` returns empty string
- **MemoryMiddleware**: Removed from middleware chain; `memory.enabled: false` in config
- **ViewImageMiddleware**: `[P0-DISABLED]` — 注释停用，防止Base64注入对话上下文
- **view_image_tool**: `[P0-DISABLED]` — 配合ViewImageMiddleware停用
- **Summarization**: Trigger/trim tokens raised to `217600`
- **Title generation**: 使用 `Qwen3-8B` 轻量模型，避免主模型浪费Token
- **Skills**: 17 original skills deleted, replaced with 3 medical skills
- **Subagent types**: `general-purpose`/`bash` replaced by `imaging-agent`/`medical-knowledge-agent`

## 3. What This Project Actually Runs

Local development is a four-process stack:

| Service | Port | Start Command (Windows) |
| ------- | ---- | ----------------------- |
| LangGraph server | `:2024` | `uv run python -m langgraph_cli dev --no-browser --allow-blocking --no-reload` |
| Gateway API | `:8001` | `$env:PYTHONPATH="."; uv run python -m uvicorn app.gateway.app:app --host 0.0.0.0 --port 8001` |
| Next.js frontend | `:3000` | `$env:SKIP_ENV_VALIDATION="1"; pnpm dev` |
| Nginx reverse proxy | `:2026` | `.\nginx.exe -c nginx.local.conf` (from `docker/nginx/`) |

Unified local entrypoint: **http://localhost:2026**

> **Windows Note**: `langgraph dev` and `uvicorn` have a `uv trampoline` bug on Windows. Use `python -m` variants above.

Nginx routing shape:

- `/api/langgraph/*` → LangGraph (rewritten before proxying)
- `/api/*` → Gateway
- `/` → Frontend

## 4. Critical Entry Points

### Backend

- `backend/langgraph.json` — registers `lead_agent` as `deerflow.agents:make_lead_agent`
- `backend/config.yaml` — **运行时配置**（模型、summarization、memory、subagents、title等）
- `backend/.env` — **环境变量**（API Key、LangSmith追踪配置）
- `backend/app/gateway/app.py` — FastAPI gateway entrypoint
- `backend/packages/harness/deerflow/agents/lead_agent/agent.py` — lead-agent runtime assembly
- `backend/packages/harness/deerflow/agents/lead_agent/prompt.py` — **医疗系统提示词**（含图片处理协议）
- `backend/packages/harness/deerflow/subagents/builtins/` — 影像Agent和医疗知识Agent配置
- `backend/packages/harness/deerflow/tools/builtins/task_tool.py` — 子Agent调度工具

### Frontend

- `frontend/src/app/workspace/chats/[thread_id]/page.tsx` — chat page
- `frontend/src/core/threads/hooks.ts` — thread creation, streaming, uploads
- `frontend/src/core/api/api-client.ts` — LangGraph SDK client singleton
- `frontend/src/core/config/index.ts` — backend/LangGraph URL resolution

## 5. Backend Boundary You Must Respect

- Harness: `backend/packages/harness/deerflow/`
- App: `backend/app/`
- **`app.*` may import `deerflow.*`; `deerflow.*` must NOT import `app.*`**
- Enforced by `backend/tests/test_harness_boundary.py`

## 6. Config Model

Config file: `backend/config.yaml` (copied from `config.example.yaml`)

Current medical settings:

```yaml
models:
  - name: qwen3.5-397b          # 主Agent, supports_thinking: true
  - name: qwen3-vl-235b         # 影像Agent, supports_vision: true
  - name: qwen3-8b              # 辅助模型 (标题生成等)

title:
  model_name: qwen3-8b          # 轻量模型生成标题，避免主模型浪费Token

summarization:
  trigger: tokens 217600
  trim_tokens_to_summarize: 217600

memory:
  enabled: false
  injection_enabled: false

subagents:
  timeout_seconds: 900
  agents:
    imaging-agent: { timeout_seconds: 1800 }
    medical-knowledge-agent: { timeout_seconds: 900 }
```

> **Ultra模式前提**: 模型必须设 `supports_thinking: true`，且 `subagents` 配置已启用。否则前端会强制锁定为Flash模式。

## 7. Subagent Model

Key files:

- `backend/packages/harness/deerflow/subagents/builtins/imaging_agent.py`
- `backend/packages/harness/deerflow/subagents/builtins/medical_knowledge_agent.py`
- `backend/packages/harness/deerflow/subagents/executor.py`
- `backend/packages/harness/deerflow/tools/builtins/task_tool.py`

Task tool `subagent_type` accepts: `"imaging-agent"` | `"medical-knowledge-agent"`

Important facts:

- `MAX_CONCURRENT_SUBAGENTS` is `3`
- 影像Agent使用 `qwen3-vl-235b` (VL视觉模型，`[P3-NOTE]` 标记为未来视觉兜底预留)
- 影像Agent当前为**纯文本管道**：接收路径 → 调MCP → 返回结构化报告
- 医疗知识Agent inherits parent model
- MCP imaging service is currently a **stub interface** — to be connected later

## 8. Skills

Location: `skills/public/`

| Skill | Purpose |
| ----- | ------- |
| `lab-report-analysis` | 化验单识别与分析指南 |
| `medical-image-consultation` | 影像分析委派给imaging-agent的工作流 |
| `medical-knowledge-search` | 网络搜索不足时委派给medical-knowledge-agent |

Skills are discovered recursively from `skills/public/` and `skills/custom/`.

## 9. Sandbox and File System Model

- Agent-visible virtual root: `/mnt/user-data`
- Per-thread host data: `.deer-flow/threads/{thread_id}/user-data/`
- Standard directories: `workspace/`, `uploads/`, `outputs/`
- Do not confuse sandbox virtual paths with host filesystem paths

## 10. Startup and Validation Commands

### Backend (from `backend/`)

- `make install` — install dependencies
- `make dev` — start LangGraph server (Linux/macOS only)
- `make gateway` — start Gateway API (Linux/macOS only)
- `make test` — run tests
- `make lint` / `make format` — code quality

### Frontend (from `frontend/`)

- `pnpm install` — install dependencies
- `pnpm dev` — start dev server
- `pnpm lint` / `pnpm typecheck` / `pnpm build`

### Nginx (from `docker/nginx/`)

- `.\nginx.exe -c nginx.local.conf` — start reverse proxy
- `.\nginx.exe -s stop` — stop

## 11. High-Risk Mistakes To Avoid

- Do not break the harness/app import boundary
- Do not assume MCP imaging service is active — it's a stub interface
- Do not re-enable MemoryMiddleware or SOUL.md — they are intentionally disabled for medical scenario
- **Do not re-enable ViewImageMiddleware without P3阶段的条件判断和阅后即焚机制** — 直接启用会导致Base64注入污染上下文
- Do not assume frontend talks directly to ports `2024`/`8001` — nginx proxy (`:2026`) is the default path
- Do not add non-medical skills to `skills/public/` without explicit request
- Do not set `supports_thinking: false` on the main model — it will lock out Ultra/Pro modes
- On Windows, do not use `langgraph dev` or `uvicorn` directly — use `python -m` variants

## 12. Minimal Takeover Checklist

Before making non-trivial changes:

1. Read this document and `backend/CLAUDE.md`
2. Confirm `backend/config.yaml` has correct model configs and subagents enabled
3. Decide whether the change belongs to harness, app, frontend, or root orchestration
4. Check whether config resolution affects the change
5. Verify nginx proxy behavior matters for the issue
6. Run the narrowest relevant validation command first
7. Check `[P0-DISABLED]` / `[P3-REACTIVATE]` markers before touching vision-related code
