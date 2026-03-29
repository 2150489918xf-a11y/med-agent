import { getBackendBaseURL } from "@/core/config";

function apiBase(): string {
  return getBackendBaseURL().replace(/\/$/, "");
}

export type SettingsProvider = {
  id: string;
  name: string;
  enabled: boolean;
  api_key: string;
  base_url: string;
  model_allowlist: string | null;
};

export type SettingsAgent = {
  id: string;
  name: string;
  model: string;
  temperature: number;
  system_prompt: string;
  thinking_enabled: boolean;
};

export type AvailableSettingsModel = {
  id: string;
  provider: string;
  is_vision: boolean;
};

export async function fetchSettingsProviders(): Promise<{
  providers: SettingsProvider[];
}> {
  const res = await fetch(`${apiBase()}/api/settings/providers`);
  if (!res.ok) {
    throw new Error(`providers ${res.status}`);
  }
  return res.json() as Promise<{ providers: SettingsProvider[] }>;
}

export async function updateSettingsProvider(
  providerId: string,
  body: {
    enabled?: boolean;
    api_key?: string;
    base_url?: string;
    model_allowlist?: string | null;
  },
): Promise<{ status: string; message?: string }> {
  const res = await fetch(`${apiBase()}/api/settings/providers/${providerId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    throw new Error(`update provider ${res.status}`);
  }
  return res.json() as Promise<{ status: string; message?: string }>;
}

export type TestProviderResult =
  | {
      status: "success";
      latency_ms: number;
      available_models: string[];
    }
  | { status: "error"; detail: string };

export async function testSettingsProvider(
  providerId: string,
): Promise<TestProviderResult> {
  const res = await fetch(
    `${apiBase()}/api/settings/providers/${providerId}/test`,
    { method: "POST" },
  );
  if (!res.ok) {
    throw new Error(`test ${res.status}`);
  }
  return res.json() as Promise<TestProviderResult>;
}

export async function fetchSettingsAgents(): Promise<{
  agents: SettingsAgent[];
}> {
  const res = await fetch(`${apiBase()}/api/settings/agents`);
  if (!res.ok) {
    throw new Error(`agents ${res.status}`);
  }
  return res.json() as Promise<{ agents: SettingsAgent[] }>;
}

export async function updateSettingsAgent(
  agentId: string,
  body: {
    model: string;
    temperature: number;
    system_prompt: string;
    thinking_enabled: boolean;
  },
): Promise<{ status: string; message?: string }> {
  const res = await fetch(`${apiBase()}/api/settings/agents/${agentId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    let msg = `HTTP ${res.status}`;
    try {
      const j = (await res.json()) as { detail?: unknown };
      if (typeof j.detail === "string") {
        msg = j.detail;
      }
    } catch {
      /* ignore */
    }
    throw new Error(msg);
  }
  return res.json() as Promise<{ status: string; message?: string }>;
}

export async function fetchAvailableSettingsModels(): Promise<{
  models: AvailableSettingsModel[];
}> {
  const res = await fetch(`${apiBase()}/api/settings/models/available`);
  if (!res.ok) {
    throw new Error(`available models ${res.status}`);
  }
  return res.json() as Promise<{ models: AvailableSettingsModel[] }>;
}

export async function resetSettingsAgent(agentId: string): Promise<{
  status: string;
  data: {
    model: string;
    temperature: number;
    system_prompt: string;
    thinking_enabled: boolean;
  };
}> {
  const res = await fetch(`${apiBase()}/api/settings/agents/${agentId}/reset`, {
    method: "POST",
  });
  if (!res.ok) {
    throw new Error(`reset ${res.status}`);
  }
  return res.json() as Promise<{
    status: string;
    data: {
      model: string;
      temperature: number;
      system_prompt: string;
      thinking_enabled: boolean;
    };
  }>;
}
