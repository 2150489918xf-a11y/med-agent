import { CheckIcon, XIcon, ScanLineIcon, PlusIcon, MessageSquareIcon, Loader2Icon } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";

import {
  Artifact,
  ArtifactContent,
  ArtifactHeader,
  ArtifactTitle,
  ArtifactActions,
  ArtifactAction,
} from "@/components/ai-elements/artifact";
import { useQueryClient } from "@tanstack/react-query";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Textarea } from "@/components/ui/textarea";
import { usePendingImagingReports, submitImagingReview, type ImagingReport } from "@/core/imaging/api";
import { useI18n } from "@/core/i18n/hooks";
import { listUploadedFiles } from "@/core/uploads/api";
import { cn } from "@/lib/utils";

export function ImagingReviewPanel({
  className,
  threadId,
  report,
  onClose,
}: {
  className?: string;
  threadId: string;
  report: ImagingReport;
  onClose?: () => void;
}) {
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const [isSubmitting, setIsSubmitting] = useState(false);

  // For now, we just pass the AI result back as the doctor result
  // In the real implementation, this will be editable
  const [doctorResult, setDoctorResult] = useState(report.ai_result || {});
  const [doctorComment, setDoctorComment] = useState("");
  const [conclusion, setConclusion] = useState<"normal" | "abnormal" | "pending">("pending");

  const handleSubmit = useCallback(async () => {
    setIsSubmitting(true);
    try {
      const finalResult = {
        ...doctorResult,
        doctor_comment: doctorComment,
        conclusion: conclusion,
      };
      await submitImagingReview(threadId, report.report_id, finalResult);
      await queryClient.invalidateQueries({ queryKey: ["imaging_reports", threadId, "pending_review"] });
      toast.success("审核结果已提交");
      onClose?.();
    } catch (error) {
      console.error("Failed to submit review:", error);
      toast.error("提交失败，请重试");
    } finally {
      setIsSubmitting(false);
    }
  }, [threadId, report.report_id, doctorResult, doctorComment, conclusion, onClose]);

  // Safely extract data from the AI result
  const summary = report.ai_result?.summary || {};
  const findings = report.ai_result?.findings || [];
  const densenetProbs = report.ai_result?.densenet_probs || {};

  // Fetch the actual image URL
  const [imageUrl, setImageUrl] = useState<string | null>(null);
  const [imgSize, setImgSize] = useState({ width: 0, height: 0 });

  useEffect(() => {
    async function fetchImage() {
      try {
        const res = await listUploadedFiles(threadId);
        // Try to match by filename (the absolute path from the backend)
        const filename = report.image_path.split(/[/\\]/).pop();
        const file = res.files.find((f) => f.filename === filename);
        if (file) {
          setImageUrl(file.artifact_url);
        } else {
          console.warn("Could not find matching uploaded file for", filename);
        }
      } catch (err) {
        console.error("Failed to list files for image", err);
      }
    }
    fetchImage();
  }, [threadId, report.image_path]);

  return (
    <Artifact className={cn("flex flex-col bg-background", className)}>
      <ArtifactHeader className="px-3 border-b border-border/50 shrink-0">
        <div className="flex items-center gap-2 text-foreground">
          <ScanLineIcon className="w-4 h-4 text-primary" />
          <ArtifactTitle className="font-medium text-sm">影像审核台</ArtifactTitle>
          <span className="ml-2 px-2 py-0.5 text-[10px] font-medium bg-amber-500/10 text-amber-500 border border-amber-500/20 rounded-full">
            待审核
          </span>
        </div>
        
        <div className="flex items-center gap-2">
          <ArtifactActions>
            <ArtifactAction
              icon={XIcon}
              label={t.common.close}
              onClick={() => onClose?.()}
              tooltip={t.common.close}
            />
          </ArtifactActions>
        </div>
      </ArtifactHeader>

      <ArtifactContent className="flex-1 overflow-y-auto p-4 space-y-6 bg-background">
        {/* 1. CHEST X-RAY with BBOX OVERLAY */}
        <div className="w-full aspect-square bg-[#1a1a1a] rounded-lg border border-border/50 flex flex-col items-center justify-center text-muted-foreground relative overflow-hidden group">
          {imageUrl ? (
            <>
              <img 
                src={imageUrl} 
                alt="X-Ray" 
                className="absolute inset-0 w-full h-full object-contain"
                onLoad={(e) => {
                  const { naturalWidth, naturalHeight } = e.currentTarget;
                  setImgSize({ width: naturalWidth, height: naturalHeight });
                }}
              />
              {imgSize.width > 0 && findings.length > 0 && (
                <svg 
                  className="absolute inset-0 w-full h-full pointer-events-none"
                  viewBox={`0 0 ${imgSize.width} ${imgSize.height}`}
                  preserveAspectRatio="xMidYMid meet"
                >
                  {findings.map((finding: any, index: number) => {
                    const [x1, y1, x2, y2] = finding.bbox;
                    const displayId = finding.id ? finding.id.substring(0, 4) : index + 1;
                    return (
                      <g key={finding.id || index}>
                        <rect 
                          x={x1} 
                          y={y1} 
                          width={x2 - x1} 
                          height={y2 - y1}
                          fill="rgba(20, 184, 166, 0.1)"
                          stroke="rgba(20, 184, 166, 0.8)"
                          strokeWidth={Math.max(2, imgSize.width * 0.003)}
                          strokeDasharray="8,4"
                        />
                        <rect 
                          x={x1} 
                          y={y1 - (imgSize.height * 0.04)} 
                          width={imgSize.width * 0.35} 
                          height={imgSize.height * 0.04}
                          fill="rgba(20, 184, 166, 0.8)"
                        />
                        <text 
                          x={x1 + (imgSize.width * 0.01)} 
                          y={y1 - (imgSize.height * 0.01)} 
                          fill="white" 
                          fontSize={imgSize.height * 0.025}
                          fontFamily="monospace"
                        >
                          #{displayId}: {(finding.confidence * 100).toFixed(1)}% {finding.disease}
                        </text>
                      </g>
                    );
                  })}
                </svg>
              )}
            </>
          ) : (
            <div className="flex flex-col items-center justify-center opacity-50">
              <Loader2Icon className="w-8 h-8 mb-2 animate-spin text-muted-foreground" />
              <p className="text-sm">加载影像中...</p>
            </div>
          )}
        </div>

        {/* 2. FINDINGS CARDS */}
        <div className="space-y-3">
          {findings.map((finding: any, index: number) => {
            const displayId = finding.id ? finding.id.substring(0, 4) : index + 1;
            return (
            <div key={finding.id || index} className="bg-[#333338] rounded-xl border border-white/5 p-4 shadow-sm">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-teal-500 shrink-0" />
                  <h4 className="font-medium text-sm text-foreground">病灶 #{displayId} · {finding.disease}</h4>
                </div>
                <Badge variant="outline" className="text-xs font-mono font-normal border-white/10 text-muted-foreground whitespace-nowrap">
                  {(finding.confidence * 100).toFixed(1)}%
                </Badge>
              </div>
              
              <Progress value={finding.confidence * 100} className="h-1 mb-3 [&>div]:bg-teal-500" />
              
              <p className="text-xs text-muted-foreground mb-4">位置: {finding.location_cn || finding.location}</p>
              
              <div className="flex items-center gap-2">
                <div className="relative flex-1">
                  <MessageSquareIcon className="absolute left-2.5 top-2.5 w-3.5 h-3.5 text-muted-foreground" />
                  <input 
                    type="text" 
                    placeholder="添加医生批注..." 
                    className="w-full bg-background border border-white/10 rounded-md text-xs py-2 pl-8 pr-2 focus:outline-none focus:border-primary/50 text-foreground transition-colors placeholder:text-muted-foreground/50"
                  />
                </div>
                <Button size="icon-sm" variant="outline" className="shrink-0 border-teal-500/30 text-teal-400 hover:bg-teal-500/10 hover:text-teal-300 transition-colors">
                  <CheckIcon className="w-4 h-4" />
                </Button>
                <Button size="icon-sm" variant="outline" className="shrink-0 border-red-500/30 text-red-500 hover:bg-red-500/10 hover:text-red-400 transition-colors">
                  <XIcon className="w-4 h-4" />
                </Button>
              </div>
            </div>
          )})}
          
          <Button variant="outline" className="w-full border-dashed border-white/10 text-muted-foreground hover:text-foreground hover:border-white/20 hover:bg-white/5 text-xs py-6">
            <PlusIcon className="w-4 h-4 mr-2" />
            新增病灶
          </Button>
        </div>

        {/* 3. DENSENET PROBABILITIES */}
        {Object.keys(densenetProbs).length > 0 && (
          <div className="space-y-4">
            <h3 className="text-xs font-medium text-muted-foreground tracking-wider uppercase">疾病概率分布</h3>
            <div className="space-y-3">
              {Object.entries(densenetProbs).map(([disease, prob]: [string, any], index) => {
                const percentage = (prob * 100);
                const colors = [
                  "bg-indigo-500", "bg-teal-500", "bg-amber-500", "bg-purple-500", "bg-red-500"
                ];
                const colorClass = colors[index % colors.length];
                
                return (
                  <div key={disease} className="space-y-1.5">
                    <div className="flex justify-between text-xs font-mono">
                      <span className="text-foreground">{disease}</span>
                      <span className="text-muted-foreground">{percentage.toFixed(1)}%</span>
                    </div>
                    <Progress value={percentage} className={`h-1 [&>div]:${colorClass}`} />
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* 4. DOCTOR INPUT */}
        <div className="space-y-3 pt-2">
          <h3 className="text-xs font-medium text-muted-foreground tracking-wider uppercase">诊断意见</h3>
          <Textarea 
            placeholder="输入最终影像学诊断意见..." 
            value={doctorComment}
            onChange={(e) => setDoctorComment(e.target.value)}
            className="min-h-[100px] resize-none bg-[#333338] border-white/5 text-sm focus-visible:ring-1 focus-visible:ring-primary/50"
          />
          <div className="flex gap-2 p-1 bg-[#333338] rounded-lg border border-white/5 w-fit">
            {(["normal", "abnormal", "pending"] as const).map((opt) => (
              <button
                key={opt}
                onClick={() => setConclusion(opt)}
                className={cn(
                  "px-4 py-1.5 text-xs font-medium rounded-md transition-all",
                  conclusion === opt 
                    ? "bg-muted shadow-sm text-foreground" 
                    : "text-muted-foreground hover:text-foreground hover:bg-white/5"
                )}
              >
                {opt === "normal" ? "正常" : opt === "abnormal" ? "异常" : "待定"}
              </button>
            ))}
          </div>
        </div>
      </ArtifactContent>

      <div className="p-4 border-t border-border/50 flex justify-end gap-3 shrink-0 bg-background/50 backdrop-blur-sm">
        <Button variant="outline" size="sm" onClick={() => toast.info("草稿已保存")}>
          保存草稿
        </Button>
        <Button 
          size="sm" 
          onClick={handleSubmit} 
          disabled={isSubmitting}
          className="bg-primary hover:bg-primary/90 text-primary-foreground"
        >
          {isSubmitting ? "提交中..." : "确认提交"}
        </Button>
      </div>
    </Artifact>
  );
}
