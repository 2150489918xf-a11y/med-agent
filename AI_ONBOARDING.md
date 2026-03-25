# MedAgent AI Onboarding

This document is for coding agents, not human end users. Its purpose is to help a new AI quickly orient itself in this repository, avoid the wrong subtree, and find the real runtime code before changing anything.

## 1. Repo Reality

This repository is a monorepo with three intended modules:

1. `1_core_orchestrator/` — active DeerFlow-based orchestrator.
2. `2_mcp_ragflow_lite/` — active lightweight RAG / retrieval service.
3. `3_mcp_medical_vision/` — currently empty in this checkout.

Important reality checks:

- The root `README.md` describes a three-service architecture, but only the first two services have real code here.
- `3_mcp_medical_vision/` is empty. Do not assume the root README reflects implemented code in that subtree.
- `2_mcp_ragflow_lite/ragflow/ragflow/` is a full upstream RAGFlow tree stored inside the repository. Treat it as a separate codebase, not as the default runtime path for Lite-service issues.
- Many upstream DeerFlow docs refer to `deer-flow/` as the repo root. In this monorepo, that usually maps to `1_core_orchestrator/`.

## 2. Active Vs Reference Codepaths

### Active codepaths

Start here unless the task explicitly says otherwise:

- `1_core_orchestrator/`
- `2_mcp_ragflow_lite/`

### Reference / easy-to-edit-by-mistake codepaths

Treat these carefully:

- `2_mcp_ragflow_lite/ragflow/ragflow/` — upstream full RAGFlow tree.
- runtime artifacts such as `.next/`, `node_modules/`, `.venv/`, `.pytest_cache/`, `__pycache__/`, `logs/`, generated thread data.
- deployment helpers or bundled binaries that are not the primary app logic.

Routing heuristic:

- Agent flow, LangGraph, sandbox, memory, subagents, uploads, artifacts, frontend chat, skills, MCP wiring: `1_core_orchestrator/`.
- KB CRUD, indexing, retrieval, GraphRAG, CRAG, Elasticsearch-backed APIs: `2_mcp_ragflow_lite/`.
- Full upstream RAGFlow platform changes: only if the task explicitly targets `2_mcp_ragflow_lite/ragflow/ragflow/`.

## 3. Repository Map

### Root

- `README.md` — overall project overview.
- `AGENTS.md` — routing rules for future agents.
- `AI_ONBOARDING.md` — this handoff document.

### `1_core_orchestrator/`

This is the active orchestrator service.

- `README.md`, `README_zh.md`, `README_ja.md` — DeerFlow-facing docs.
- `Makefile` — primary local and Docker commands.
- `config.yaml` — active runtime config, may contain sensitive values.
- `config.example.yaml` — safe template.
- `extensions_config.json` — MCP / skill registry, currently empty.
- `extensions_config.example.json` — safe template.
- `.env`, `.env.example` — environment variables.
- `backend/` — LangGraph + FastAPI backend.
- `frontend/` — Next.js frontend.
- `scripts/` — startup helpers and MCP stub.
- `docker/` — compose and nginx config.
- `skills/` — DeerFlow skill files.

### `2_mcp_ragflow_lite/`

This is the active lightweight retrieval service.

- `README.md` — architecture and API overview.
- `api/` — FastAPI Lite service.
- `common/` — logging, registry, path helpers.
- `rag/` — retrieval, config loading, GraphRAG, CRAG.
- `deepdoc/` — parsing / OCR / layout logic.
- `conf/` — runtime config and Elasticsearch metadata.
- `scripts/build_index.py` — offline ingestion entrypoint.
- `tests/` — Lite-service tests.
- `ragflow/ragflow/` — nested upstream full RAGFlow repository.

### `3_mcp_medical_vision/`

- Empty in this checkout.

## 4. Critical Entry Points

### Orchestrator runtime

- `1_core_orchestrator/backend/langgraph.json`
  - LangGraph entrypoint.
  - Registers `lead_agent` via `deerflow.agents:make_lead_agent`.
  - Uses `../.env`.

- `1_core_orchestrator/backend/app/gateway/app.py`
  - FastAPI Gateway entrypoint.
  - Mounts routers for models, MCP, memory, skills, uploads, artifacts, agents, suggestions, and channels.

- `1_core_orchestrator/scripts/serve.sh`
  - Best single file for understanding full local startup.
  - Starts LangGraph, Gateway, Frontend, and Nginx.

- `1_core_orchestrator/docker/nginx/nginx.local.conf`
  - Reverse proxy routing.

### Orchestrator core hot path

- `1_core_orchestrator/backend/packages/harness/deerflow/agents/lead_agent/agent.py`
  - Main runtime assembly path.
  - Builds middleware chain, resolves model, plan mode, subagent mode, and tool set.

- `1_core_orchestrator/backend/packages/harness/deerflow/config/app_config.py`
  - Config resolution and reload logic.

- `1_core_orchestrator/backend/packages/harness/deerflow/config/extensions_config.py`
  - MCP / skills config loader.

- `1_core_orchestrator/backend/packages/harness/deerflow/skills/loader.py`
  - Skill discovery and enabled-state handling.

- `1_core_orchestrator/backend/packages/harness/deerflow/mcp/tools.py`
  - MCP tool discovery and initialization.

- `1_core_orchestrator/backend/packages/harness/deerflow/sandbox/tools.py`
  - Sandbox tool implementations and virtual-path mapping.

### Frontend hot path

- `1_core_orchestrator/frontend/src/app/workspace/chats/[thread_id]/page.tsx`
  - Main chat page wiring.

- `1_core_orchestrator/frontend/src/core/threads/hooks.ts`
  - Frontend request / stream lifecycle.

### RAGFlow Lite runtime

- `2_mcp_ragflow_lite/api/app.py`
  - FastAPI entrypoint.

- `2_mcp_ragflow_lite/api/deps.py`
  - Singletons for ES, embeddings, GraphRAG, CRAG, reranker, query enhancer.

- `2_mcp_ragflow_lite/api/routes/tool.py`
  - Agent-facing retrieval tool endpoint.

- `2_mcp_ragflow_lite/api/routes/search.py`
  - Main retrieval API.

- `2_mcp_ragflow_lite/rag/settings.py`
  - `conf/service_conf.yaml` loader and validation.

- `2_mcp_ragflow_lite/scripts/build_index.py`
  - Offline ingestion and graph build pipeline.

- `2_mcp_ragflow_lite/ragflow/ragflow/mcp/server/server.py`
  - Nested upstream MCP server wrapper.
  - Relevant only when the task explicitly involves the upstream RAGFlow MCP server layer.

## 5. Runtime Architecture

### `1_core_orchestrator`

Observed runtime shape:

- Nginx on `:2026`
- LangGraph on `:2024`
- Gateway API on `:8001`
- Frontend on `:3000`

Routing shape:

- `/api/langgraph/*` → LangGraph server
- `/api/*` → Gateway API
- `/` → Next.js frontend

This mirrors standard DeerFlow layering:

- LangGraph owns thread execution and streaming.
- Gateway owns models, skills, MCP config, uploads, artifacts, memory, and related management APIs.
- Frontend talks across both layers through Nginx routing.

### `2_mcp_ragflow_lite`

Observed runtime shape:

- FastAPI service on `:9380`
- Elasticsearch dependency via `docker-compose.yml`

The Lite service is not just a thin wrapper. It contains its own retrieval pipeline, config schema, indexing script, tests, and plugin registry.

## 6. Integration Status

- `1_core_orchestrator/extensions_config.json` is currently empty, so MCP services are not wired by default.
- `1_core_orchestrator/scripts/medical_mcp_server.py` exists, but it is only a skeleton / stub, not a full production medical vision service.
- `1_core_orchestrator` contains medical customizations already checked in, such as a medical guardrail provider and medical subagent definitions.
- `2_mcp_ragflow_lite` is the concrete retrieval implementation currently present in the repo.
- The root-level architecture still implies additional external services that are not fully implemented in this checkout.

## 7. Hard Boundaries And Rules

### Harness vs app boundary

Inside `1_core_orchestrator/backend`, the boundary is strict:

- Code under `packages/harness/deerflow/` must not import from `app/`.

This is an important architectural rule. Treat it as enforced, not advisory.

### Config sensitivity

Treat these as sensitive:

- `1_core_orchestrator/config.yaml`
- `1_core_orchestrator/.env`
- `2_mcp_ragflow_lite/conf/service_conf.yaml`

Prefer templates when documenting or editing shape:

- `1_core_orchestrator/config.example.yaml`
- `1_core_orchestrator/extensions_config.example.json`
- `1_core_orchestrator/.env.example`

### Doc trust model

- Local code and config are more authoritative than README claims.
- If a README conflicts with actual files, trust the actual files.
- Root README is useful for intent, but not always for current implementation reality.

### Documentation sync rule

Inside `1_core_orchestrator/backend`, local guidance explicitly requires documentation updates after code changes.

If you modify backend code there, also check whether these need updates:

- `1_core_orchestrator/backend/README.md`
- `1_core_orchestrator/backend/CLAUDE.md`

Treat this as a local development rule, not an optional cleanup step.

## 8. Config Resolution And Path Model

### Orchestrator config resolution

For `1_core_orchestrator`, future agents should verify config resolution before editing behavior.

Important files:

- `1_core_orchestrator/backend/packages/harness/deerflow/config/app_config.py`
- `1_core_orchestrator/backend/packages/harness/deerflow/config/extensions_config.py`

Important realities:

- `config.yaml` lives at the `1_core_orchestrator/` root, not only under `backend/`.
- `extensions_config.json` also lives at the `1_core_orchestrator/` root.
- `extensions_config.json` is optional in loader logic, but if present, it controls MCP server and skill enablement.
- `extensions_config.json` currently contains no active MCP server wiring.

### Thread-local path model in orchestrator

For thread isolation, the orchestrator uses a per-thread filesystem layout managed by `1_core_orchestrator/backend/packages/harness/deerflow/config/paths.py`.

Key host-side layout:

- `{base_dir}/threads/{thread_id}/user-data/workspace/`
- `{base_dir}/threads/{thread_id}/user-data/uploads/`
- `{base_dir}/threads/{thread_id}/user-data/outputs/`

Key sandbox-visible virtual paths:

- `/mnt/user-data/workspace`
- `/mnt/user-data/uploads`
- `/mnt/user-data/outputs`

Why this matters:

- If a task mentions uploaded files, artifacts, generated reports, or sandbox file access, inspect this path model first.
- Do not assume direct host paths in agent prompts or tool output. The runtime often maps host paths to sandbox-visible virtual paths.

### RAGFlow Lite config model

For `2_mcp_ragflow_lite`, the main config is `2_mcp_ragflow_lite/conf/service_conf.yaml`, loaded through `2_mcp_ragflow_lite/rag/settings.py`.

Important realities:

- The config is validated by Pydantic at startup.
- Misconfigured or missing required keys should fail fast.
- The file may contain live service credentials, so do not expose it casually.

## 9. Startup Commands And Working Directories

### `1_core_orchestrator`

Primary command roots:

- repo root for repo-wide context
- `1_core_orchestrator/` for orchestrator-level startup commands
- `1_core_orchestrator/backend/` for backend-focused commands
- `1_core_orchestrator/frontend/` for frontend-focused commands

Most useful startup files and commands:

- `1_core_orchestrator/Makefile`
- `1_core_orchestrator/scripts/serve.sh`
- `1_core_orchestrator/docker/docker-compose.yaml`

High-value commands to inspect or run when needed:

- `make dev`
- `make docker-init`
- `make docker-start`

### `1_core_orchestrator/backend`

Important command root:

- `1_core_orchestrator/backend/`

Important file:

- `1_core_orchestrator/backend/Makefile`

Useful command patterns:

- backend dev server / LangGraph startup
- gateway startup
- lint / test / format targets

### `1_core_orchestrator/frontend`

Important command root:

- `1_core_orchestrator/frontend/`

Important files:

- `1_core_orchestrator/frontend/package.json`
- `1_core_orchestrator/frontend/Makefile`

Useful command patterns:

- `pnpm dev`
- `pnpm lint`
- `pnpm typecheck`
- `pnpm build`

### `2_mcp_ragflow_lite`

Important command root:

- `2_mcp_ragflow_lite/`

Important files:

- `2_mcp_ragflow_lite/README.md`
- `2_mcp_ragflow_lite/docker-compose.yml`
- `2_mcp_ragflow_lite/scripts/build_index.py`

Useful command patterns:

- start Elasticsearch via Docker Compose
- run the FastAPI app
- run pytest suite
- run `scripts/build_index.py` for offline index creation

## 10. Validation Defaults

### Orchestrator backend

Default validation sources:

- `1_core_orchestrator/backend/Makefile`
- backend pytest suite

Typical validation expectations:

- lint passes
- relevant pytest targets pass
- no harness/app boundary violation

### Orchestrator frontend

Default validation sequence:

- `pnpm lint`
- `pnpm typecheck`
- `pnpm build`

### RAGFlow Lite

Default validation sources:

- `2_mcp_ragflow_lite/tests/`
- service startup assumptions in `2_mcp_ragflow_lite/README.md`

Important note:

- The nested upstream RAGFlow tree has its own heavy workflows and is not the default validation target for ordinary Lite-service changes.

## 11. High-Risk Pitfalls

These are the most likely ways a future AI will go wrong.

1. Editing the wrong subtree.
   - `2_mcp_ragflow_lite/` and `2_mcp_ragflow_lite/ragflow/ragflow/` are not the same codebase.

2. Trusting README architecture over actual implementation.
   - The root README describes services and scripts that are not fully present in this checkout.

3. Assuming MCP services are live.
   - `1_core_orchestrator/extensions_config.json` is empty.

4. Assuming medical vision code exists in `3_mcp_medical_vision/`.
   - It does not in this checkout.

5. Breaking the harness/app boundary in orchestrator backend.
   - Keep `packages/harness/deerflow/` independent from `app/`.

6. Reading or leaking sensitive config.
   - Prefer example files unless the task explicitly requires actual runtime config inspection.

7. Ignoring thread-local file mapping.
   - Uploaded and generated files often appear through `/mnt/user-data/*` virtual paths, not raw host paths.

8. Confusing “stub exists” with “service is production-ready”.
   - `1_core_orchestrator/scripts/medical_mcp_server.py` is a skeleton, not proof of a complete deployed service.

## 12. Recommended Reading Order

### For repo-level orientation

1. `AGENTS.md`
2. `AI_ONBOARDING.md`
3. `README.md`

### For orchestrator work

1. `1_core_orchestrator/README_zh.md` or `1_core_orchestrator/README.md`
2. `1_core_orchestrator/backend/AGENTS.md`
3. `1_core_orchestrator/backend/CLAUDE.md`
4. `1_core_orchestrator/backend/README.md`
5. `1_core_orchestrator/backend/langgraph.json`
6. `1_core_orchestrator/backend/packages/harness/deerflow/agents/lead_agent/agent.py`
7. `1_core_orchestrator/backend/app/gateway/app.py`
8. `1_core_orchestrator/frontend/AGENTS.md` if frontend is involved
9. `1_core_orchestrator/frontend/src/core/threads/hooks.ts` if chat flow is involved

### For RAGFlow Lite work

1. `2_mcp_ragflow_lite/README.md`
2. `2_mcp_ragflow_lite/api/app.py`
3. `2_mcp_ragflow_lite/api/deps.py`
4. `2_mcp_ragflow_lite/api/routes/tool.py`
5. `2_mcp_ragflow_lite/rag/settings.py`
6. `2_mcp_ragflow_lite/scripts/build_index.py`

### For upstream RAGFlow work

Only then read:

- `2_mcp_ragflow_lite/ragflow/ragflow/AGENTS.md`
- `2_mcp_ragflow_lite/ragflow/ragflow/CLAUDE.md`

## 13. Pre-Change Checklist For Future AI

Before editing code, verify all of the following:

- Which subtree owns the task?
- Am I in active code or in a nested reference/upstream tree?
- Which AGENTS / CLAUDE documents apply to the files I will touch?
- Are there sensitive config files involved?
- Is the requested integration actually wired in this checkout, or only described in docs?
- What validation commands apply to this subtree?

If there is any mismatch between documentation and code, document the mismatch and follow the code.

## 14. External Framework Context

This repo uses patterns from LangGraph, MCP, and DeerFlow.

Practical guidance for code navigation:

- LangGraph: focus on where the graph is assembled and compiled. In this repo, `langgraph.json` plus `make_lead_agent` define the effective runtime entry.
- MCP: think in host/client/server layers. Look for where the orchestrator loads MCP server definitions, constructs clients, and exposes tools.
- DeerFlow: treat `/api/langgraph/*` and `/api/*` as separate runtime layers. LangGraph handles execution flow; Gateway handles management APIs and supporting services.

Use these concepts for navigation, but always prefer local code over generic framework assumptions.
