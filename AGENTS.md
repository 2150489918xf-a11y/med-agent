# MedAgent AI Working Guide

This repository is a monorepo. Before making changes, identify the correct subtree first.

## Read This First

- Read `AI_ONBOARDING.md` at the repository root before non-trivial work.
- If touching `1_core_orchestrator/backend/`, also read `1_core_orchestrator/backend/AGENTS.md` and `1_core_orchestrator/backend/CLAUDE.md`.
- If touching `1_core_orchestrator/frontend/`, also read `1_core_orchestrator/frontend/AGENTS.md` and `1_core_orchestrator/frontend/CLAUDE.md`.
- If touching `2_mcp_ragflow_lite/ragflow/ragflow/`, also read `2_mcp_ragflow_lite/ragflow/ragflow/AGENTS.md` and `2_mcp_ragflow_lite/ragflow/ragflow/CLAUDE.md`.

## Repository Reality

- `1_core_orchestrator/` is the active DeerFlow-based orchestrator. Many upstream docs say `deer-flow/`; in this repo that usually means `1_core_orchestrator/`.
- `2_mcp_ragflow_lite/` is an active lightweight RAG service with its own FastAPI app, indexing pipeline, and tests.
- `2_mcp_ragflow_lite/ragflow/ragflow/` is a full upstream RAGFlow tree kept inside the repo. Treat it as a separate codebase, not the default runtime path for Lite-service issues.
- `3_mcp_medical_vision/` is currently empty in this checkout. Do not assume the root `README.md` reflects implemented code there.

## High-Risk Pitfalls

- Do not trust architecture claims until you verify actual files and configs.
- `1_core_orchestrator/extensions_config.json` is currently empty, so MCP services are not wired by default.
- `1_core_orchestrator/scripts/medical_mcp_server.py` is a stub/skeleton, not a full production medical vision service.
- Runtime config files may contain secrets. Treat `1_core_orchestrator/config.yaml`, `.env` files, and `2_mcp_ragflow_lite/conf/service_conf.yaml` as sensitive.
- In `1_core_orchestrator/backend`, the harness/app boundary is strict: code under `packages/harness/deerflow/` must not import from `app/`.

## Routing Heuristic

- Chat UI, LangGraph agent flow, sandbox, memory, subagents, MCP integration, uploads, artifacts: work in `1_core_orchestrator/`.
- Knowledge base CRUD, indexing, GraphRAG, CRAG, retrieval APIs, Elasticsearch schema: work in `2_mcp_ragflow_lite/`.
- Full upstream RAGFlow platform work only when the task explicitly targets `2_mcp_ragflow_lite/ragflow/ragflow/`.

## Validation Defaults

- For `1_core_orchestrator/backend`: use backend `Makefile` commands and relevant pytest targets.
- For `1_core_orchestrator/frontend`: use `pnpm lint`, `pnpm typecheck`, and `pnpm build` when relevant.
- For `2_mcp_ragflow_lite/`: use its pytest suite and service-specific startup assumptions from `README.md`.

## Source Of Truth

- Use `AI_ONBOARDING.md` as the root-level AI handoff document.
- Treat local code and config files as more authoritative than marketing or upstream-facing README language.
