"""Tests for /api/settings (providers + agents)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import yaml
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.gateway.routers import settings as settings_router


def _minimal_config() -> dict:
    return {
        "config_version": 1,
        "sandbox": {"use": "deerflow.sandbox.local:LocalSandboxProvider"},
        "models": [
            {
                "name": "alpha",
                "display_name": "Alpha",
                "model": "gpt-4o-mini",
                "use": "langchain_openai:ChatOpenAI",
                "base_url": "https://api.openai.com/v1",
                "api_key": "secret-openai-key",
                "temperature": 0.7,
                "supports_vision": False,
            },
            {
                "name": "beta",
                "display_name": "Beta",
                "model": "Qwen/Qwen3-8B",
                "use": "langchain_openai:ChatOpenAI",
                "base_url": "https://api.siliconflow.cn/v1",
                "api_key": "secret-silicon-key",
                "temperature": 0.5,
                "supports_vision": False,
            },
            {
                "name": "vision-m",
                "display_name": "Vision",
                "model": "Qwen/Qwen3-VL-8B-Instruct",
                "use": "langchain_openai:ChatOpenAI",
                "base_url": "https://api.siliconflow.cn/v1",
                "api_key": "secret-silicon-key",
                "temperature": 0.1,
                "supports_vision": True,
            },
        ],
        "subagents": {
            "agents": {
                "imaging-agent": {"model_name": "vision-m"},
                "medical-knowledge-agent": {},
            },
        },
    }


def _write_config(path: Path, data: dict) -> None:
    path.write_text(yaml.dump(data, allow_unicode=True, default_flow_style=False), encoding="utf-8")


def _client(tmp_path: Path, monkeypatch) -> TestClient:
    cfg_path = tmp_path / "config.yaml"
    _write_config(cfg_path, _minimal_config())

    monkeypatch.setattr(
        "app.gateway.routers.models._get_config_path",
        lambda: cfg_path,
    )

    app = FastAPI()
    app.include_router(settings_router.router)
    return TestClient(app)


def test_list_providers_masks_api_keys(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    r = client.get("/api/settings/providers")
    assert r.status_code == 200
    body = r.json()
    assert "providers" in body
    by_id = {p["id"]: p for p in body["providers"]}
    assert "****" in by_id["openai"]["api_key"] or by_id["openai"]["api_key"] == "********"
    assert by_id["openai"]["api_key"] != "secret-openai-key"


def test_put_provider_skips_api_key_when_masked(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    r = client.put(
        "/api/settings/providers/openai",
        json={"api_key": "sk-1234********", "enabled": True},
    )
    assert r.status_code == 200
    data = yaml.safe_load((tmp_path / "config.yaml").read_text(encoding="utf-8"))
    m0 = next(m for m in data["models"] if m["name"] == "alpha")
    assert m0["api_key"] == "secret-openai-key"


def test_put_provider_updates_key_when_clear(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    r = client.put(
        "/api/settings/providers/openai",
        json={"api_key": "new-openai-secret", "enabled": True},
    )
    assert r.status_code == 200
    data = yaml.safe_load((tmp_path / "config.yaml").read_text(encoding="utf-8"))
    m0 = next(m for m in data["models"] if m["name"] == "alpha")
    assert m0["api_key"] == "new-openai-secret"
    root = data.get("medagent_settings", {})
    assert root["providers"]["openai"]["api_key"] == "new-openai-secret"


def test_put_lead_agent_reorders_models(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    r = client.put(
        "/api/settings/agents/lead-agent",
        json={
            "model": "beta",
            "temperature": 0.2,
            "system_prompt": "hello",
            "thinking_enabled": True,
        },
    )
    assert r.status_code == 200
    data = yaml.safe_load((tmp_path / "config.yaml").read_text(encoding="utf-8"))
    assert data["models"][0]["name"] == "beta"
    assert data["models"][0]["temperature"] == 0.2
    assert data["medagent_settings"]["agents"]["lead-agent"]["model_name"] == "beta"


def test_put_imaging_updates_subagent(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    r = client.put(
        "/api/settings/agents/imaging-agent",
        json={
            "model": "vision-m",
            "temperature": 0.15,
            "system_prompt": "",
            "thinking_enabled": False,
        },
    )
    assert r.status_code == 200
    data = yaml.safe_load((tmp_path / "config.yaml").read_text(encoding="utf-8"))
    assert data["subagents"]["agents"]["imaging-agent"]["model_name"] == "vision-m"


def test_list_agents(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    r = client.get("/api/settings/agents")
    assert r.status_code == 200
    agents = {a["id"]: a for a in r.json()["agents"]}
    assert agents["lead-agent"]["model"] == "gpt-4o-mini"
    assert agents["imaging-agent"]["model"] == "Qwen/Qwen3-VL-8B-Instruct"


def test_available_models_fallback_when_get_app_config_fails(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    with patch.object(settings_router, "get_app_config", side_effect=RuntimeError("no cfg")):
        r = client.get("/api/settings/models/available")
    assert r.status_code == 200
    ids = {m["id"] for m in r.json()["models"]}
    assert "gpt-4o-mini" in ids
    assert "Qwen/Qwen3-8B" in ids


def test_test_provider_openai_errors_without_key(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    # Clear openai provider key in yaml
    cfg_path = tmp_path / "config.yaml"
    data = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    for m in data["models"]:
        if "openai.com" in (m.get("base_url") or ""):
            m["api_key"] = ""
    _write_config(cfg_path, data)
    r = client.post("/api/settings/providers/openai/test")
    assert r.status_code == 200
    j = r.json()
    assert j["status"] == "error"


@patch("app.gateway.routers.settings.httpx.AsyncClient")
def test_test_provider_success(mock_aclass, tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = ""
    mock_resp.json.return_value = {"data": [{"id": "m1"}, {"id": "m2"}]}

    mock_inst = MagicMock()
    mock_inst.get = AsyncMock(return_value=mock_resp)
    mock_ctx = MagicMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_inst)
    mock_ctx.__aexit__ = AsyncMock(return_value=None)
    mock_aclass.return_value = mock_ctx

    r = client.post("/api/settings/providers/siliconflow/test")
    assert r.status_code == 200
    j = r.json()
    assert j["status"] == "success"
    assert j["latency_ms"] >= 0
    assert "m1" in j["available_models"]
