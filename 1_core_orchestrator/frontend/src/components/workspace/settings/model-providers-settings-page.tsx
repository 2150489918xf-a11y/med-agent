"use client";

import { ChevronDownIcon, Loader2Icon, ServerIcon } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { useI18n } from "@/core/i18n/hooks";
import {
  fetchSettingsProviders,
  testSettingsProvider,
  updateSettingsProvider,
  type SettingsProvider,
} from "@/core/settings/api";
import { cn } from "@/lib/utils";

import { SettingsSection } from "./settings-section";

type Draft = {
  enabled: boolean;
  base_url: string;
  api_key: string;
  model_allowlist: string;
};

function emptyDraft(p: SettingsProvider): Draft {
  return {
    enabled: p.enabled,
    base_url: p.base_url,
    api_key: p.api_key,
    model_allowlist: p.model_allowlist ?? "",
  };
}

export function ModelProvidersSettingsPage() {
  const { t } = useI18n();
  const [providers, setProviders] = useState<SettingsProvider[]>([]);
  const [drafts, setDrafts] = useState<Record<string, Draft>>({});
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [savingId, setSavingId] = useState<string | null>(null);
  const [testingId, setTestingId] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setLoadError(null);
    try {
      const { providers: list } = await fetchSettingsProviders();
      setProviders(list);
      const next: Record<string, Draft> = {};
      for (const p of list) {
        next[p.id] = emptyDraft(p);
      }
      setDrafts(next);
    } catch {
      setLoadError(t.settings.modelProviders.loadError);
      setProviders([]);
      setDrafts({});
    } finally {
      setLoading(false);
    }
  }, [t.settings.modelProviders.loadError]);

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
      await updateSettingsProvider(id, {
        enabled: d.enabled,
        base_url: d.base_url,
        api_key: d.api_key,
        model_allowlist: id === "ollama" ? d.model_allowlist || null : undefined,
      });
      toast.success(t.common.save);
      await load();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Save failed");
    } finally {
      setSavingId(null);
    }
  };

  const handleTest = async (id: string) => {
    setTestingId(id);
    try {
      const r = await testSettingsProvider(id);
      if (r.status === "success") {
        toast.success(
          `${t.settings.modelProviders.testSuccess} · ${r.latency_ms}ms · ${t.settings.modelProviders.modelsReturned}: ${r.available_models.length}`,
        );
      } else {
        toast.error(`${t.settings.modelProviders.testError}: ${r.detail}`);
      }
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Test failed");
    } finally {
      setTestingId(null);
    }
  };

  if (loading) {
    return (
      <SettingsSection
        title={t.settings.modelProviders.title}
        description={t.settings.modelProviders.description}
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
        title={t.settings.modelProviders.title}
        description={t.settings.modelProviders.description}
      >
        <Alert variant="destructive">
          <AlertTitle>{t.settings.modelProviders.testError}</AlertTitle>
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
      title={t.settings.modelProviders.title}
      description={t.settings.modelProviders.description}
    >
      <div className="space-y-2">
        {providers.map((p) => {
          const d = drafts[p.id];
          if (!d) return null;
          return (
            <Collapsible
              key={p.id}
              defaultOpen={p.id === "siliconflow"}
              className="rounded-lg border bg-card"
            >
              <CollapsibleTrigger
                className={cn(
                  "group flex w-full items-center gap-3 px-4 py-3 text-left text-sm font-medium",
                  "hover:bg-muted/50 data-[state=open]:border-b",
                )}
              >
                <ServerIcon className="text-muted-foreground size-4 shrink-0" />
                <span className="flex-1">{p.name}</span>
                <ChevronDownIcon className="text-muted-foreground size-4 shrink-0 transition-transform group-data-[state=open]:rotate-180" />
              </CollapsibleTrigger>
              <CollapsibleContent className="space-y-4 px-4 pb-4 pt-2">
                <div className="flex items-center justify-between gap-4">
                  <span className="text-sm">{t.settings.modelProviders.enabled}</span>
                  <Switch
                    checked={d.enabled}
                    onCheckedChange={(v) => setDraft(p.id, { enabled: v })}
                  />
                </div>
                <div className="space-y-2">
                  <span className="text-muted-foreground text-xs font-medium">
                    {t.settings.modelProviders.baseUrl}
                  </span>
                  <Input
                    value={d.base_url}
                    onChange={(e) => setDraft(p.id, { base_url: e.target.value })}
                    autoComplete="off"
                  />
                </div>
                <div className="space-y-2">
                  <span className="text-muted-foreground text-xs font-medium">
                    {t.settings.modelProviders.apiKey}
                  </span>
                  <Input
                    type="password"
                    value={d.api_key}
                    onChange={(e) => setDraft(p.id, { api_key: e.target.value })}
                    placeholder="••••••••"
                    autoComplete="off"
                  />
                  <p className="text-muted-foreground text-xs">
                    {t.settings.modelProviders.apiKeyHint}
                  </p>
                </div>
                {p.id === "ollama" && (
                  <div className="space-y-2">
                    <span className="text-muted-foreground text-xs font-medium">
                      {t.settings.modelProviders.allowlist}
                    </span>
                    <Textarea
                      value={d.model_allowlist}
                      onChange={(e) =>
                        setDraft(p.id, { model_allowlist: e.target.value })
                      }
                      rows={3}
                      className="min-h-0 resize-y"
                    />
                    <p className="text-muted-foreground text-xs">
                      {t.settings.modelProviders.allowlistHint}
                    </p>
                  </div>
                )}
                <div className="flex flex-wrap gap-2 pt-2">
                  <Button
                    type="button"
                    variant="outline"
                    disabled={testingId === p.id}
                    onClick={() => void handleTest(p.id)}
                  >
                    {testingId === p.id ? (
                      <>
                        <Loader2Icon className="size-4 animate-spin" />
                        {t.settings.modelProviders.testing}
                      </>
                    ) : (
                      t.settings.modelProviders.testConnection
                    )}
                  </Button>
                  <Button
                    type="button"
                    disabled={savingId === p.id}
                    onClick={() => void handleSave(p.id)}
                  >
                    {savingId === p.id ? (
                      <>
                        <Loader2Icon className="size-4 animate-spin" />
                        {t.common.loading}
                      </>
                    ) : (
                      t.settings.modelProviders.save
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
