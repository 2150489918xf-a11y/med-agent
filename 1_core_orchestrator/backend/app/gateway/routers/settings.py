"""MedAgent settings API: model providers and per-agent bindings (config.yaml)."""

from __future__ import annotations

import logging
import os
import time
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.gateway.routers.models import _read_config, _write_config
from deerflow.config.app_config import get_app_config

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/settings", tags=["settings"])

# --- Provider templates (id -> default base_url) ---
_PROVIDER_DEFAULTS: dict[str, dict[str, Any]] = {
    "siliconflow": {
        "name": "SiliconFlow",
        "base_url": "https://api.siliconflow.cn/v1",
    },
    "openai": {
        "name": "OpenAI",
        "base_url": "https://api.openai.com/v1",
    },
    "ollama": {
        "name": "Ollama",
        "base_url": "http://localhost:11434/v1",
    },
}

_AGENT_IDS = ("lead-agent", "imaging-agent", "rag-agent")
_AGENT_DISPLAY = {
    "lead-agent": "主代理 (Lead Agent)",
    "imaging-agent": "影像代理 (Imaging Agent)",
    "rag-agent": "知识库代理 (RAG Agent)",
}
def _medagent_root(data: dict) -> dict:
    if "medagent_settings" not in data or data["medagent_settings"] is None:
        data["medagent_settings"] = {}
    return data["medagent_settings"]


def _providers_store(root: dict) -> dict:
    if "providers" not in root or root["providers"] is None:
        root["providers"] = {}
    return root["providers"]


def _agents_store(root: dict) -> dict:
    if "agents" not in root or root["agents"] is None:
        root["agents"] = {}
    return root["agents"]


def _mask_api_key(raw: str | None) -> str:
    if not raw:
        return ""
    s = str(raw).strip()
    if s.startswith("$"):
        return "********"
    if len(s) <= 6:
        return "********"
    return s[:4] + "********"


def _resolve_api_key_for_request(raw: str | None) -> str:
    if not raw:
        return ""
    s = str(raw).strip()
    if s.startswith("$"):
        env = os.getenv(s[1:], "")
        return env or ""
    return s


def _infer_provider_from_models(models_list: list, provider_id: str) -> dict[str, Any]:
    """Pick first model row that matches provider heuristics."""
    hints = {
        "siliconflow": ("siliconflow",),
        "openai": ("openai.com",),
        "ollama": ("11434", "localhost", "ollama"),
    }
    keys = hints.get(provider_id, ())
    for m in models_list:
        if not isinstance(m, dict):
            continue
        bu = (m.get("base_url") or "").lower()
        if any(k in bu for k in keys):
            return {
                "enabled": True,
                "base_url": m.get("base_url") or _PROVIDER_DEFAULTS[provider_id]["base_url"],
                "api_key": m.get("api_key") or "",
            }
    return {
        "enabled": False,
        "base_url": _PROVIDER_DEFAULTS[provider_id]["base_url"],
        "api_key": "",
    }


def _get_models_list(data: dict) -> list:
    return data.get("models") or []


def _find_model_entry(data: dict, name: str) -> dict | None:
    for m in _get_models_list(data):
        if isinstance(m, dict) and m.get("name") == name:
            return m
    return None


def _move_model_to_front(data: dict, model_name: str) -> None:
    models = _get_models_list(data)
    idx = next((i for i, m in enumerate(models) if isinstance(m, dict) and m.get("name") == model_name), None)
    if idx is None:
        raise HTTPException(status_code=400, detail=f"Model '{model_name}' not found")
    m = models.pop(idx)
    models.insert(0, m)
    data["models"] = models


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class ProviderOut(BaseModel):
    id: str
    name: str
    enabled: bool
    api_key: str
    base_url: str
    model_allowlist: str | None = None


class ProvidersListResponse(BaseModel):
    providers: list[ProviderOut]


class ProviderUpdateBody(BaseModel):
    enabled: bool | None = None
    api_key: str | None = None
    base_url: str | None = None
    model_allowlist: str | None = None


class AgentOut(BaseModel):
    id: str
    name: str
    model: str
    temperature: float
    system_prompt: str
    thinking_enabled: bool


class AgentsListResponse(BaseModel):
    agents: list[AgentOut]


class AgentUpdateBody(BaseModel):
    model: str = Field(..., description="Provider model id or config model name (resolved)")
    temperature: float = Field(ge=0.0, le=2.0)
    system_prompt: str = ""
    thinking_enabled: bool = False


class AvailableModelOut(BaseModel):
    id: str
    provider: str
    is_vision: bool


class AvailableModelsResponse(BaseModel):
    models: list[AvailableModelOut]


class OkResponse(BaseModel):
    status: str = "success"
    message: str | None = None


class TestOkResponse(BaseModel):
    status: str = "success"
    latency_ms: int
    available_models: list[str]


class TestErrResponse(BaseModel):
    status: str = "error"
    detail: str


class ResetAgentResponse(BaseModel):
    status: str = "success"
    data: dict[str, Any]


# ---------------------------------------------------------------------------
# Helpers: build GET state
# ---------------------------------------------------------------------------


def _build_provider_list(yaml_data: dict) -> list[ProviderOut]:
    root = _medagent_root(yaml_data)
    store = _providers_store(root)
    models_list = _get_models_list(yaml_data)
    out: list[ProviderOut] = []
    for pid, meta in _PROVIDER_DEFAULTS.items():
        row = store.get(pid)
        if not isinstance(row, dict):
            inferred = _infer_provider_from_models(models_list, pid)
            raw_key = inferred["api_key"]
            out.append(
                ProviderOut(
                    id=pid,
                    name=meta["name"],
                    enabled=bool(inferred["enabled"] and raw_key),
                    api_key=_mask_api_key(raw_key),
                    base_url=inferred["base_url"],
                    model_allowlist=None,
                ),
            )
            continue
        raw_key = row.get("api_key", "")
        out.append(
            ProviderOut(
                id=pid,
                name=meta["name"],
                enabled=bool(row.get("enabled", False)),
                api_key=_mask_api_key(raw_key),
                base_url=row.get("base_url") or meta["base_url"],
                model_allowlist=row.get("model_allowlist") or None,
            ),
        )
    return out


def _resolve_model_name_for_agent(yaml_data: dict, agent_id: str) -> str | None:
    """Return config model `name` (yaml key) for agent."""
    models_list = _get_models_list(yaml_data)
    if not models_list:
        return None
    root = _medagent_root(yaml_data)
    astore = _agents_store(root)
    saved = astore.get(agent_id)
    if isinstance(saved, dict) and saved.get("model_name"):
        if _find_model_entry(yaml_data, saved["model_name"]):
            return saved["model_name"]
    if agent_id == "lead-agent":
        first = models_list[0]
        if isinstance(first, dict):
            return first.get("name")
    if agent_id == "imaging-agent":
        sub = (yaml_data.get("subagents") or {}).get("agents") or {}
        im = sub.get("imaging-agent") or {}
        if isinstance(im, dict) and im.get("model_name"):
            return im["model_name"]
    if agent_id == "rag-agent":
        sub = (yaml_data.get("subagents") or {}).get("agents") or {}
        rag = sub.get("medical-knowledge-agent") or {}
        if isinstance(rag, dict) and rag.get("model_name"):
            return rag["model_name"]
        if isinstance(models_list[0], dict):
            return models_list[0].get("name")
    return models_list[0].get("name") if isinstance(models_list[0], dict) else None


def _agent_temperature(yaml_data: dict, model_name: str | None) -> float:
    if not model_name:
        return 0.7
    m = _find_model_entry(yaml_data, model_name)
    if not m:
        return 0.7
    t = m.get("temperature")
    try:
        return float(t) if t is not None else 0.7
    except (TypeError, ValueError):
        return 0.7


def _build_agents_list(yaml_data: dict) -> list[AgentOut]:
    root = _medagent_root(yaml_data)
    astore = _agents_store(root)
    result: list[AgentOut] = []
    for aid in _AGENT_IDS:
        mname = _resolve_model_name_for_agent(yaml_data, aid)
        mrow = _find_model_entry(yaml_data, mname) if mname else None
        provider_id = (mrow or {}).get("model") or ""
        ast = astore.get(aid) if isinstance(astore.get(aid), dict) else {}
        result.append(
            AgentOut(
                id=aid,
                name=_AGENT_DISPLAY[aid],
                model=str(provider_id),
                temperature=_agent_temperature(yaml_data, mname),
                system_prompt=str(ast.get("system_prompt") or ""),
                thinking_enabled=bool(ast.get("thinking_enabled", True if aid == "lead-agent" else False)),
            ),
        )
    return result


def _match_model_row(body_model: str, yaml_data: dict) -> dict | None:
    """Resolve AgentUpdateBody.model to a models[] entry (by config name or provider model id)."""
    for m in _get_models_list(yaml_data):
        if not isinstance(m, dict):
            continue
        if m.get("name") == body_model or m.get("model") == body_model:
            return m
    return None


# ---------------------------------------------------------------------------
# Routes: providers
# ---------------------------------------------------------------------------


@router.get("/providers", response_model=ProvidersListResponse)
async def list_providers() -> ProvidersListResponse:
    _, data = _read_config()
    return ProvidersListResponse(providers=_build_provider_list(data))


@router.put("/providers/{provider_id}", response_model=OkResponse)
async def update_provider(provider_id: str, body: ProviderUpdateBody) -> OkResponse:
    if provider_id not in _PROVIDER_DEFAULTS:
        raise HTTPException(status_code=404, detail="Unknown provider")
    yaml, data = _read_config()
    root = _medagent_root(data)
    store = _providers_store(root)
    if provider_id not in store or not isinstance(store[provider_id], dict):
        store[provider_id] = {
            "enabled": False,
            "base_url": _PROVIDER_DEFAULTS[provider_id]["base_url"],
            "api_key": "",
        }
    row = store[provider_id]
    if body.enabled is not None:
        row["enabled"] = body.enabled
    if body.base_url is not None:
        row["base_url"] = body.base_url.strip()
    if body.model_allowlist is not None and provider_id == "ollama":
        row["model_allowlist"] = body.model_allowlist
    if body.api_key is not None:
        ak = body.api_key.strip()
        if "****" not in ak:
            row["api_key"] = ak
    # Apply to all models that belong to this provider (by URL hint)
    base = row.get("base_url") or _PROVIDER_DEFAULTS[provider_id]["base_url"]
    raw_key = row.get("api_key") or ""
    models_list = _get_models_list(data)
    hints = {
        "siliconflow": ("siliconflow",),
        "openai": ("openai.com",),
        "ollama": ("11434", "localhost", "ollama"),
    }
    keys = hints.get(provider_id, ())
    for m in models_list:
        if not isinstance(m, dict):
            continue
        bu = (m.get("base_url") or "").lower()
        if any(k in bu for k in keys):
            m["base_url"] = base
            if raw_key and "****" not in str(raw_key):
                m["api_key"] = raw_key
    _write_config(yaml, data)
    return OkResponse(message=f"{_PROVIDER_DEFAULTS[provider_id]['name']} 配置已更新")


@router.post("/providers/{provider_id}/test")
async def test_provider(provider_id: str):
    if provider_id not in _PROVIDER_DEFAULTS:
        raise HTTPException(status_code=404, detail="Unknown provider")
    _, data = _read_config()
    root = _medagent_root(data)
    store = _providers_store(root)
    row = store.get(provider_id)
    if not isinstance(row, dict):
        row = _infer_provider_from_models(_get_models_list(data), provider_id)
    base_url = (row.get("base_url") or _PROVIDER_DEFAULTS[provider_id]["base_url"]).rstrip("/")
    raw_key = row.get("api_key") or ""
    api_key = _resolve_api_key_for_request(raw_key)
    url = f"{base_url}/models"
    if provider_id == "ollama" and not api_key:
        headers: dict[str, str] = {}
    else:
        if not api_key:
            return TestErrResponse(detail="未配置 API Key 或环境变量为空")
        headers = {"Authorization": f"Bearer {api_key}"}
    started = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            r = await client.get(url, headers=headers)
        latency_ms = int((time.perf_counter() - started) * 1000)
        if r.status_code >= 400:
            return TestErrResponse(detail=r.text[:500] or f"HTTP {r.status_code}")
        payload = r.json()
        ids: list[str] = []
        if isinstance(payload, dict) and "data" in payload:
            for item in payload.get("data") or []:
                if isinstance(item, dict) and item.get("id"):
                    ids.append(str(item["id"]))
        elif isinstance(payload, dict) and "models" in payload:
            for item in payload.get("models") or []:
                if isinstance(item, dict):
                    mid = item.get("id") or item.get("name")
                    if mid:
                        ids.append(str(mid))
        return TestOkResponse(latency_ms=latency_ms, available_models=ids[:50])
    except Exception as e:
        logger.exception("Provider test failed")
        return TestErrResponse(detail=str(e)[:500])


# ---------------------------------------------------------------------------
# Routes: agents
# ---------------------------------------------------------------------------


@router.get("/agents", response_model=AgentsListResponse)
async def list_agents() -> AgentsListResponse:
    _, data = _read_config()
    return AgentsListResponse(agents=_build_agents_list(data))


@router.put("/agents/{agent_id}", response_model=OkResponse)
async def update_agent(agent_id: str, body: AgentUpdateBody) -> OkResponse:
    if agent_id not in _AGENT_IDS:
        raise HTTPException(status_code=404, detail="Unknown agent")
    yaml, data = _read_config()
    mrow = _match_model_row(body.model, data)
    if not mrow:
        raise HTTPException(status_code=400, detail="找不到匹配的模型，请从可用列表选择或输入正确的模型 ID")
    mname = mrow.get("name")
    if not mname:
        raise HTTPException(status_code=400, detail="Invalid model entry")

    root = _medagent_root(data)
    astore = _agents_store(root)
    if agent_id not in astore or not isinstance(astore[agent_id], dict):
        astore[agent_id] = {}
    astore[agent_id]["model_name"] = mname
    astore[agent_id]["system_prompt"] = body.system_prompt
    astore[agent_id]["thinking_enabled"] = body.thinking_enabled

    mrow["temperature"] = body.temperature

    if agent_id == "lead-agent":
        _move_model_to_front(data, str(mname))
    elif agent_id == "imaging-agent":
        if "subagents" not in data:
            data["subagents"] = {}
        if "agents" not in data["subagents"] or data["subagents"]["agents"] is None:
            data["subagents"]["agents"] = {}
        agents_sub = data["subagents"]["agents"]
        if "imaging-agent" not in agents_sub or not isinstance(agents_sub["imaging-agent"], dict):
            agents_sub["imaging-agent"] = {}
        agents_sub["imaging-agent"]["model_name"] = mname
    elif agent_id == "rag-agent":
        if "subagents" not in data:
            data["subagents"] = {}
        if "agents" not in data["subagents"] or data["subagents"]["agents"] is None:
            data["subagents"]["agents"] = {}
        agents_sub = data["subagents"]["agents"]
        if "medical-knowledge-agent" not in agents_sub or not isinstance(
            agents_sub["medical-knowledge-agent"], dict
        ):
            agents_sub["medical-knowledge-agent"] = {}
        agents_sub["medical-knowledge-agent"]["model_name"] = mname

    _write_config(yaml, data)
    return OkResponse(message="Agent 配置已更新")


@router.get("/models/available", response_model=AvailableModelsResponse)
async def list_available_models() -> AvailableModelsResponse:
    try:
        cfg = get_app_config()
    except Exception:
        _, raw = _read_config()
        out: list[AvailableModelOut] = []
        for m in _get_models_list(raw):
            if not isinstance(m, dict):
                continue
            pid = "custom"
            bu = (m.get("base_url") or "").lower()
            if "siliconflow" in bu:
                pid = "siliconflow"
            elif "openai" in bu:
                pid = "openai"
            elif "11434" in bu or "ollama" in bu:
                pid = "ollama"
            out.append(
                AvailableModelOut(
                    id=str(m.get("model") or m.get("name")),
                    provider=pid,
                    is_vision=bool(m.get("supports_vision")),
                ),
            )
        return AvailableModelsResponse(models=out)

    out2: list[AvailableModelOut] = []
    for m in cfg.models:
        bu = (getattr(m, "base_url", None) or "").lower()
        pid = "custom"
        if "siliconflow" in bu:
            pid = "siliconflow"
        elif "openai" in bu:
            pid = "openai"
        elif "11434" in bu or "ollama" in bu:
            pid = "ollama"
        out2.append(
            AvailableModelOut(
                id=str(m.model),
                provider=pid,
                is_vision=bool(m.supports_vision),
            ),
        )
    return AvailableModelsResponse(models=out2)


@router.post("/agents/{agent_id}/reset", response_model=ResetAgentResponse)
async def reset_agent(agent_id: str) -> ResetAgentResponse:
    if agent_id not in _AGENT_IDS:
        raise HTTPException(status_code=404, detail="Unknown agent")
    yaml, data = _read_config()
    models_list = _get_models_list(data)
    if not models_list or not isinstance(models_list[0], dict):
        raise HTTPException(status_code=400, detail="No models configured")

    # Defaults: lead -> first model; imaging -> first vision model or qwen3-vl pattern; rag -> first small or first
    first_name = models_list[0].get("name")
    vision_name = None
    for m in models_list:
        if isinstance(m, dict) and m.get("supports_vision"):
            vision_name = m.get("name")
            break
    if not vision_name:
        for m in models_list:
            if isinstance(m, dict) and "vl" in str(m.get("name", "")).lower():
                vision_name = m.get("name")
                break
    vision_name = vision_name or first_name

    root = _medagent_root(data)
    astore = _agents_store(root)
    if agent_id == "lead-agent":
        astore["lead-agent"] = {
            "model_name": first_name,
            "system_prompt": "",
            "thinking_enabled": True,
        }
        _move_model_to_front(data, str(first_name))
        m = _find_model_entry(data, str(first_name))
        if m:
            m["temperature"] = 0.7
    elif agent_id == "imaging-agent":
        astore["imaging-agent"] = {
            "model_name": vision_name,
            "system_prompt": "",
            "thinking_enabled": False,
        }
        if "subagents" not in data:
            data["subagents"] = {"agents": {}}
        if "agents" not in data["subagents"]:
            data["subagents"]["agents"] = {}
        if "imaging-agent" not in data["subagents"]["agents"]:
            data["subagents"]["agents"]["imaging-agent"] = {}
        data["subagents"]["agents"]["imaging-agent"]["model_name"] = vision_name
        m = _find_model_entry(data, str(vision_name))
        if m:
            m["temperature"] = 0.1
    else:
        rag_name = first_name
        for m in models_list:
            if isinstance(m, dict) and m.get("name") and "8b" in str(m.get("name")).lower():
                rag_name = m.get("name")
                break
        astore["rag-agent"] = {
            "model_name": rag_name,
            "system_prompt": "",
            "thinking_enabled": False,
        }
        if "subagents" not in data:
            data["subagents"] = {"agents": {}}
        if "agents" not in data["subagents"]:
            data["subagents"]["agents"] = {}
        if "medical-knowledge-agent" not in data["subagents"]["agents"]:
            data["subagents"]["agents"]["medical-knowledge-agent"] = {}
        data["subagents"]["agents"]["medical-knowledge-agent"]["model_name"] = rag_name
        m = _find_model_entry(data, str(rag_name))
        if m:
            m["temperature"] = 0.3

    _write_config(yaml, data)
    _, fresh = _read_config()
    agents = _build_agents_list(fresh)
    found = next((a for a in agents if a.id == agent_id), None)
    if not found:
        raise HTTPException(status_code=500, detail="Reset failed")
    return ResetAgentResponse(
        data={
            "model": found.model,
            "temperature": found.temperature,
            "system_prompt": found.system_prompt,
            "thinking_enabled": found.thinking_enabled,
        },
    )
