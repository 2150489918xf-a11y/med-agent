# 1_core_orchestrator AI Quick Handoff

This document is for coding agents taking over work inside `1_core_orchestrator/`.

> **⚠️ This project has been adapted from generic DeerFlow 2.0 to a medical multi-agent system (MedAgent).**

## 1. First Reality Checks

- This subtree is an active DeerFlow 2.0 fork adapted for **medical diagnosis scenarios**.
- The directory name is `1_core_orchestrator/` (typo was previously fixed).
- Local code is the source of truth. Upstream DeerFlow docs are only a secondary reference.
- Do not assume the monorepo root README describes this subtree's current runtime accurately.

## 2. Medical Agent Architecture

The system uses a **three-agent architecture**:

| Agent | Role | Model | Config File |
|-------|------|-------|-------------|
| **主Agent (Lead Agent)** | 调度子Agent，识别化验单，网络搜索 | `Qwen/Qwen3.5-397B-A17B` (SiliconFlow) | `agents/lead_agent/prompt.py` |
| **影像Agent (Imaging Agent)** | 调用MCP服务识别医疗影像(X光/CT/MRI) | `Qwen/Qwen3-VL-235B-A22B-Thinking` (SiliconFlow) | `subagents/builtins/imaging_agent.py` |
| **医疗知识Agent (Medical Knowledge Agent)** | 深度医疗知识检索 | 继承主Agent模型 | `subagents/builtins/medical_knowledge_agent.py` |

子Agent通过 `task` 工具调度，需要 **Ultra模式** (`subagent_enabled: true`)。

### Key Medical Adaptations Made

- **System prompt**: Rewritten in Chinese for medical scenario (`prompt.py`)
- **SOUL.md**: Disabled — `get_agent_soul()` returns empty string
- **MemoryMiddleware**: Removed from middleware chain; `memory.enabled: false` in config
- **Summarization**: Trigger/trim tokens raised to `217600`
- **Skills**: 17 original skills deleted, replaced with 3 medical skills:
  - `lab-report-analysis` — 化验单分析
  - `medical-image-consultation` — 影像咨询（委派给imaging-agent）
  - `medical-knowledge-search` — 医疗知识检索（委派给medical-knowledge-agent）
- **Subagent types**: `general-purpose`/`bash` replaced by `imaging-agent`/`medical-knowledge-agent`

## 3. What This Project Actually Runs

Local development is a four-process stack:

| Service | Port | Start Command (Windows) |
|---------|------|------------------------|
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
- `backend/config.yaml` — **运行时配置**（模型、summarization、memory、subagents等）
- `backend/app/gateway/app.py` — FastAPI gateway entrypoint
- `backend/packages/harness/deerflow/agents/lead_agent/agent.py` — lead-agent runtime assembly
- `backend/packages/harness/deerflow/agents/lead_agent/prompt.py` — **医疗系统提示词**
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
- 影像Agent hardcodes model to `qwen3-vl-235b` (VL vision model)
- 医疗知识Agent inherits parent model
- MCP imaging service is currently a **stub interface** — to be connected later

## 8. Skills

Location: `skills/public/`

| Skill | Purpose |
|-------|---------|
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
