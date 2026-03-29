"use client";

import { BotIcon, ChevronDownIcon, Loader2Icon } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { useI18n } from "@/core/i18n/hooks";
import {
  fetchAvailableSettingsModels,
  fetchSettingsAgents,
  resetSettingsAgent,
  updateSettingsAgent,
  type AvailableSettingsModel,
  type SettingsAgent,
} from "@/core/settings/api";
import { cn } from "@/lib/utils";

import { SettingsSection } from "./settings-section";

type Draft = {
  model: string;
  temperature: number;
  system_prompt: string;
  thinking_enabled: boolean;
};

function emptyDraft(a: SettingsAgent): Draft {
  return {
    model: a.model,
    temperature: a.temperature,
    system_prompt: a.system_prompt,
    thinking_enabled: a.thinking_enabled,
  };
}

const PROVIDER_ORDER = ["siliconflow", "openai", "ollama", "custom"] as const;

function providerSortKey(k: string): number {
  const i = PROVIDER_ORDER.indexOf(k as (typeof PROVIDER_ORDER)[number]);
  return i === -1 ? 999 : i;
}

function providerLabel(p: string): string {
  if (p === "siliconflow") return "SiliconFlow";
  if (p === "openai") return "OpenAI";
  if (p === "ollama") return "Ollama";
  return p;
}

export function AgentsSettingsPage() {
  const { t } = useI18n();
  const [agents, setAgents] = useState<SettingsAgent[]>([]);
  const [available, setAvailable] = useState<AvailableSettingsModel[]>([]);
  const [drafts, setDrafts] = useState<Record<string, Draft>>({});
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [savingId, setSavingId] = useState<string | null>(null);
  const [resettingId, setResettingId] = useState<string | null>(null);

  const visionByModelId = useMemo(() => {
    const m = new Map<string, boolean>();
    for (const row of available) {
      m.set(row.id, row.is_vision);
    }
    return m;
  }, [available]);

  const groupedAvailable = useMemo(() => {
    const by = new Map<string, AvailableSettingsModel[]>();
    for (const row of available) {
      const g = row.provider || "custom";
      const list = by.get(g) ?? [];
      list.push(row);
      by.set(g, list);
    }
    const keys = Array.from(by.keys()).sort(
      (a, b) => providerSortKey(a) - providerSortKey(b),
    );
    return keys.map((k) => ({ provider: k, models: by.get(k) ?? [] }));
  }, [available]);

  const load = useCallback(async () => {
    setLoading(true);
    setLoadError(null);
    try {
      const [a, m] = await Promise.all([
        fetchSettingsAgents(),
        fetchAvailableSettingsModels(),
      ]);
      setAgents(a.agents);
      setAvailable(m.models);
      const next: Record<string, Draft> = {};
      for (const ag of a.agents) {
        next[ag.id] = emptyDraft(ag);
      }
      setDrafts(next);
    } catch {
      setLoadError(t.settings.agentsConfig.loadError);
      setAgents([]);
      setAvailable([]);
      setDrafts({});
    } finally {
      setLoading(false);
    }
  }, [t.settings.agentsConfig.loadError]);

  useEffect(() => {
    void load();
  }, [load]);

  const setDraft = (id: string, patch: Partial<Draft>) => {
    setDrafts((d) => ({
      ...d,
      [id]: { ...d[id], ...patch },
    }));
  };

  const handleSave = async (id: string) => {
    const d = drafts[id];
    if (!d) return;
    setSavingId(id);
    try {
      await updateSettingsAgent(id, d);
      toast.success(t.settings.agentsConfig.saved);
      await load();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Save failed");
    } finally {
      setSavingId(null);
    }
  };

  const handleReset = async (id: string) => {
    setResettingId(id);
    try {
      const { data } = await resetSettingsAgent(id);
      setDrafts((prev) => ({
        ...prev,
        [id]: {
          model: data.model,
          temperature: data.temperature,
          system_prompt: data.system_prompt,
          thinking_enabled: data.thinking_enabled,
        },
      }));
      toast.success(t.settings.agentsConfig.saved);
      await load();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Reset failed");
    } finally {
      setResettingId(null);
    }
  };

  if (loading) {
    return (
      <SettingsSection
        title={t.settings.agentsConfig.title}
        description={t.settings.agentsConfig.description}
      >
        <div className="text-muted-foreground flex items-center gap-2 text-sm">
          <Loader2Icon className="size-4 animate-spin" />
          {t.common.loading}
        </div>
      </SettingsSection>
    );
  }

  if (loadError) {
    return (
      <SettingsSection
        title={t.settings.agentsConfig.title}
        description={t.settings.agentsConfig.description}
      >
        <Alert variant="destructive">
          <AlertDescription>{loadError}</AlertDescription>
        </Alert>
        <Button className="mt-4" variant="outline" onClick={() => void load()}>
          {t.settings.modelProviders.retry}
        </Button>
      </SettingsSection>
    );
  }

  return (
    <SettingsSection
      title={t.settings.agentsConfig.title}
      description={t.settings.agentsConfig.description}
    >
      <div className="space-y-2">
        {agents.map((ag) => {
          const d = drafts[ag.id];
          if (!d) return null;
          const isVision =
            ag.id === "imaging-agent"
              ? (visionByModelId.get(d.model) ?? false)
              : true;
          const showVisionWarn = ag.id === "imaging-agent" && !isVision;

          return (
            <Collapsible
              key={ag.id}
              defaultOpen={ag.id === "lead-agent"}
              className="rounded-lg border bg-card"
            >
              <CollapsibleTrigger
                className={cn(
                  "group flex w-full items-center gap-3 px-4 py-3 text-left text-sm font-medium",
                  "hover:bg-muted/50 data-[state=open]:border-b",
                )}
              >
                <BotIcon className="text-muted-foreground size-4 shrink-0" />
                <span className="flex-1">{ag.name}</span>
                <ChevronDownIcon className="text-muted-foreground size-4 shrink-0 transition-transform group-data-[state=open]:rotate-180" />
              </CollapsibleTrigger>
              <CollapsibleContent className="space-y-4 px-4 pb-4 pt-2">
                {showVisionWarn && (
                  <Alert variant="destructive">
                    <AlertDescription>
                      {t.settings.agentsConfig.visionWarning}
                    </AlertDescription>
                  </Alert>
                )}
                <div className="space-y-2">
                  <span className="text-muted-foreground text-xs font-medium">
                    {t.settings.agentsConfig.model}
                  </span>
                  <Select
                    value={d.model}
                    onValueChange={(v) => setDraft(ag.id, { model: v })}
                  >
                    <SelectTrigger className="w-full min-w-0 max-w-full">
                      <SelectValue placeholder={d.model} />
                    </SelectTrigger>
                    <SelectContent
                      position="popper"
                      className="w-[var(--radix-select-trigger-width)] max-w-[min(100vw-2rem,32rem)]"
                    >
                      {!available.some((m) => m.id === d.model) && d.model ? (
                        <SelectGroup>
                          <SelectLabel>{t.common.custom}</SelectLabel>
                          <SelectItem value={d.model}>{d.model}</SelectItem>
                        </SelectGroup>
                      ) : null}
                      {groupedAvailable.map(({ provider, models }) => (
                        <SelectGroup key={provider}>
                          <SelectLabel>{providerLabel(provider)}</SelectLabel>
                          {models.map((m) => (
                            <SelectItem key={`${provider}-${m.id}`} value={m.id}>
                              {m.id}
                              {m.is_vision
                                ? ` · ${t.settings.agentsConfig.visionBadge}`
                                : ""}
                            </SelectItem>
                          ))}
                        </SelectGroup>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <span className="text-muted-foreground text-xs font-medium">
                    {t.settings.agentsConfig.temperature}
                  </span>
                  <Input
                    type="number"
                    min={0}
                    max={2}
                    step={0.05}
                    value={d.temperature}
                    onChange={(e) =>
                      setDraft(ag.id, {
                        temperature: Number.parseFloat(e.target.value) || 0,
                      })
                    }
                  />
                </div>
                <div className="space-y-2">
                  <span className="text-muted-foreground text-xs font-medium">
                    {t.settings.agentsConfig.systemPrompt}
                  </span>
                  <Textarea
                    value={d.system_prompt}
                    onChange={(e) =>
                      setDraft(ag.id, { system_prompt: e.target.value })
                    }
                    rows={4}
                    className="min-h-0 resize-y"
                  />
                </div>
                <div className="flex items-center justify-between gap-4">
                  <span className="text-sm">
                    {t.settings.agentsConfig.thinkingMode}
                  </span>
                  <Switch
                    checked={d.thinking_enabled}
                    onCheckedChange={(v) =>
                      setDraft(ag.id, { thinking_enabled: v })
                    }
                  />
                </div>
                <div className="flex flex-wrap gap-2 pt-2">
                  <Button
                    type="button"
                    variant="outline"
                    disabled={resettingId === ag.id}
                    onClick={() => void handleReset(ag.id)}
                  >
                    {resettingId === ag.id ? (
                      <>
                        <Loader2Icon className="size-4 animate-spin" />
                        {t.settings.agentsConfig.resetting}
                      </>
                    ) : (
                      t.settings.agentsConfig.reset
                    )}
                  </Button>
                  <Button
                    type="button"
                    disabled={savingId === ag.id}
                    onClick={() => void handleSave(ag.id)}
                  >
                    {savingId === ag.id ? (
                      <>
                        <Loader2Icon className="size-4 animate-spin" />
                        {t.common.loading}
                      </>
                    ) : (
                      t.settings.agentsConfig.save
                    )}
                  </Button>
                </div>
              </CollapsibleContent>
            </Collapsible>
          );
        })}
      </div>
    </SettingsSection>
  );
}
