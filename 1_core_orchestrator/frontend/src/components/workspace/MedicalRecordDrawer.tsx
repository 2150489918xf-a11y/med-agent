"use client";

import { FileText, RefreshCw } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { getBackendBaseURL } from "@/core/config";
import { cn } from "@/lib/utils";

import { MedicalRecordCard, type MedicalRecordData } from "./MedicalRecordCard";

interface MedicalRecordDialogProps {
  threadId: string;
  open: boolean;
  onClose: () => void;
}

export function MedicalRecordDialog({
  threadId,
  open,
  onClose,
}: MedicalRecordDialogProps) {
  const [data, setData] = useState<MedicalRecordData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchRecord = useCallback(async () => {
    if (!threadId) return;

    setLoading(true);
    setError(null);
    try {
      const response = await fetch(
        `${getBackendBaseURL()}/api/threads/${threadId}/medical-record`,
      );
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      const json = (await response.json()) as MedicalRecordData;
      setData(json);
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : "加载失败";
      setError(message);
    } finally {
      setLoading(false);
    }
  }, [threadId]);

  useEffect(() => {
    if (open) {
      void fetchRecord();
    }
  }, [fetchRecord, open]);

  return (
    <Dialog open={open} onOpenChange={(nextOpen) => !nextOpen && onClose()}>
      <DialogContent
        className="max-h-[92vh] overflow-hidden border-none bg-transparent p-0 shadow-none sm:max-w-6xl"
        aria-describedby="medical-record-dialog-description"
        showCloseButton={false}
      >
        <div className="overflow-hidden rounded-[32px] border border-cyan-200/70 bg-[radial-gradient(circle_at_top_left,rgba(34,211,238,0.14),transparent_40%),linear-gradient(180deg,rgba(248,250,252,0.96),rgba(255,255,255,0.94))] shadow-[0_32px_96px_rgba(15,23,42,0.22)]">
          <DialogHeader className="border-b border-cyan-100 px-5 py-5 text-left sm:px-6">
            <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
              <div className="max-w-2xl">
                <div className="flex items-center gap-3">
                  <div className="flex size-11 items-center justify-center rounded-2xl bg-cyan-600 text-white shadow-[0_12px_24px_rgba(8,145,178,0.28)]">
                    <FileText className="size-5" />
                  </div>
                  <div>
                    <DialogTitle className="text-xl tracking-tight text-slate-950">
                      我的病历页
                    </DialogTitle>
                    <DialogDescription
                      id="medical-record-dialog-description"
                      className="mt-1 text-sm leading-6 text-slate-600"
                    >
                      这里会弹出完整病例页面。可以直接修改信息、查看上传原图，并在识别完成后核对摘要。
                    </DialogDescription>
                    {data?.guidance ? (
                      <div className="mt-3 flex flex-wrap gap-2">
                        <span
                          className={cn(
                            "rounded-full px-3 py-1 text-xs font-semibold",
                            data.guidance.ready_for_ai_summary
                              ? "bg-emerald-100 text-emerald-700"
                              : "bg-amber-100 text-amber-700",
                          )}
                        >
                          {data.guidance.ready_for_ai_summary ? "资料较完整" : "仍在补充中"}
                        </span>
                        <span className="text-xs leading-6 text-slate-500">
                          {data.guidance.status_text}
                        </span>
                      </div>
                    ) : null}
                  </div>
                </div>
              </div>
              <button
                type="button"
                onClick={() => void fetchRecord()}
                disabled={loading}
                className="min-h-11 cursor-pointer rounded-full border border-cyan-200 bg-white/90 px-4 py-2 text-sm font-medium text-cyan-800 transition-colors hover:border-cyan-300 hover:bg-cyan-50 disabled:cursor-not-allowed disabled:opacity-60"
              >
                <span className="inline-flex items-center gap-2">
                  <RefreshCw className={cn("size-4", loading && "animate-spin")} />
                  重新加载
                </span>
              </button>
            </div>
          </DialogHeader>

          <div className="max-h-[calc(92vh-112px)] overflow-y-auto px-3 py-3 sm:px-4 sm:py-4">
            {loading && !data ? (
              <div className="flex min-h-60 items-center justify-center rounded-[28px] border border-dashed border-cyan-200 bg-white/70 text-sm text-slate-500">
                <span className="inline-flex items-center gap-2">
                  <RefreshCw className="size-4 animate-spin" />
                  正在加载病例页...
                </span>
              </div>
            ) : null}

            {error ? (
              <div className="flex min-h-60 flex-col items-center justify-center rounded-[28px] border border-rose-200 bg-rose-50 px-6 text-center">
                <p className="text-base font-semibold text-rose-700">病例页加载失败</p>
                <p className="mt-2 text-sm leading-6 text-rose-600">{error}</p>
                <button
                  type="button"
                  onClick={() => void fetchRecord()}
                  className="mt-4 min-h-11 cursor-pointer rounded-full bg-rose-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-rose-700"
                >
                  重试
                </button>
              </div>
            ) : null}

            {!loading && !error && data ? (
              <MedicalRecordCard data={data} mode="dialog" onRefresh={fetchRecord} />
            ) : null}

            {!loading && !error && !data ? (
              <div className="flex min-h-60 items-center justify-center rounded-[28px] border border-dashed border-cyan-200 bg-white/70 px-6 text-center text-sm leading-6 text-slate-500">
                当前还没有病历信息。先在聊天里告诉 AI 您的症状，或直接上传检查资料，病例页就会自动生成。
              </div>
            ) : null}
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}