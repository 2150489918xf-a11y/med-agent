"use client";

import React, { useEffect, useState } from "react";
import { cn } from "@/lib/utils";
import { ShieldCheck, User, Image as ImageIcon, FileText, Activity, Loader2, CheckCircle2, Circle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { fetchCase, type CaseData } from "@/core/api/cases";
import { ImagingViewer } from "@/components/doctor/ImagingViewer";

interface EvidenceDeskProps {
  activeTab: string;
  onTabChange: (tab: string) => void;
  isReviewPassed: boolean;
  onReviewPass: () => void;
  caseId?: string | null;  // When provided, fetch real data from API
}

export function EvidenceDesk({ activeTab, onTabChange, isReviewPassed, onReviewPass, caseId }: EvidenceDeskProps) {
  
  // ── API Data State ──────────────────────────────────
  const [caseData, setCaseData] = useState<CaseData | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    if (!caseId) return;
    setIsLoading(true);
    fetchCase(caseId)
      .then((data) => {
        setCaseData(data);
        // Auto-select first evidence tab if available
        if (data.evidence.length > 0) {
          onTabChange("vitals"); // Default to vitals overview
        }
      })
      .catch((err) => {
        console.warn("[EvidenceDesk] Failed to fetch case data, using mock:", err);
        setCaseData(null);
      })
      .finally(() => setIsLoading(false));
  }, [caseId]);

  // Derive display values from API data or mock defaults
  const patientName = caseData?.patient_info?.name ?? "张建国";
  const patientAge = caseData?.patient_info?.age ?? 58;
  const patientSex = caseData?.patient_info?.sex ?? "男";
  const evidenceItems = caseData?.evidence ?? [];

  // Create dynamic ALL_TABS from evidence Items
  const ALL_TABS: { id: string, label: string, type: string, item?: any }[] = [
    { id: "vitals", label: "基础体征与历史", type: "vitals" }
  ];
  evidenceItems.forEach((ev: any, i: number) => {
    ALL_TABS.push({
      id: `ev_${ev.evidence_id || i}`,
      label: ev.title || `附加数据 ${i+1}`,
      type: ev.type,
      item: ev
    });
  });

  const [reviewedTabs, setReviewedTabs] = useState<Set<string>>(new Set());
  const toggleReviewed = (tabId: string) => {
    setReviewedTabs(prev => {
      const next = new Set(prev);
      if (next.has(tabId)) next.delete(tabId); else next.add(tabId);
      return next;
    });
  };
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleReviewPassClick = async () => {
    if (!caseId) {
      onReviewPass();
      return;
    }
    setIsSubmitting(true);
    try {
      const { getBackendBaseURL } = await import("@/core/config");
      await fetch(`${getBackendBaseURL()}/api/cases/${caseId}/status`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status: "diagnosed" })
      });
      onReviewPass();
    } catch (e) {
      console.error("Failed to approve case", e);
      onReviewPass();
    } finally {
      setIsSubmitting(false);
    }
  };

  const allReviewed = ALL_TABS.every(t => reviewedTabs.has(t.id));
  
  const activeTabData = ALL_TABS.find(t => t.id === activeTab);
  
  // 提取一个公用的渲染左侧菜单按钮的小组件函数，保持代码整洁
  const renderTab = (id: string, label: string, Icon: React.ElementType, isAlert = false) => {
    const isActive = activeTab === id;
    const isReviewed = reviewedTabs.has(id);
    return (
      <div key={id} className="flex items-center gap-1">
        <button
          onClick={() => onTabChange(id)}
          className={cn(
            "flex-1 flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-all duration-200 ring-1",
            isActive 
              ? "bg-blue-50 text-blue-700 shadow-sm ring-blue-200 font-semibold" 
              : "bg-transparent text-slate-600 hover:bg-slate-200/50 ring-transparent hover:text-slate-900 font-medium"
          )}
        >
          <div className={cn("p-1.5 rounded-md", isActive ? "bg-white text-blue-600 shadow-sm" : "bg-white text-slate-400 border border-slate-200/50")}>
            <Icon className="h-4 w-4" />
          </div>
          <span className="truncate">{label}</span>
          {isAlert && !isReviewed && <span className="ml-auto w-2 h-2 rounded-full bg-amber-500 animate-pulse"></span>}
        </button>
        <button
          onClick={(e) => { e.stopPropagation(); toggleReviewed(id); }}
          className={cn(
            "p-1.5 rounded-lg transition-all shrink-0",
            isReviewed
              ? "text-emerald-600 hover:text-emerald-700"
              : "text-slate-300 hover:text-slate-500"
          )}
          title={isReviewed ? "已确认审核" : "点击确认审核"}
        >
          {isReviewed ? <CheckCircle2 className="h-4 w-4" /> : <Circle className="h-4 w-4" />}
        </button>
      </div>
    );
  };

  return (
    <div className="flex w-full h-full flex-row relative bg-white overflow-hidden">
      {/* 25% 左侧导航 - 临床证据归档 (Master List) */}
      <div className="w-[280px] shrink-0 border-r border-slate-200 bg-slate-50 flex flex-col h-full z-10 shadow-[4px_0_24px_rgba(0,0,0,0.02)]">
        <div className="px-5 py-4 border-b border-slate-200/60 flex items-center justify-between bg-white/50 backdrop-blur">
          <h3 className="font-semibold text-slate-800 tracking-tight">患者查体归档</h3>
          <span className="text-[10px] font-bold bg-blue-100 text-blue-700 px-2 py-0.5 rounded-full uppercase">6项</span>
        </div>
        
        <div className="flex-1 overflow-y-auto py-4 px-3 space-y-6">
          <div className="space-y-1">
            <div className="text-[11px] font-bold text-slate-400 uppercase tracking-widest mb-3 ml-2 flex items-center justify-between">
              主病历数据 <span className="text-[9px] bg-slate-200 text-slate-500 px-1.5 py-0.5 rounded mr-2">1</span>
            </div>
            {ALL_TABS.filter(t => t.type === 'vitals').map(t => renderTab(t.id, t.label, User, false))}
          </div>

          {ALL_TABS.filter(t => t.type === "imaging").length > 0 && (
            <div className="space-y-1">
              <div className="text-[11px] font-bold text-slate-400 uppercase tracking-widest mb-3 ml-2 flex items-center justify-between">
                医学影像 <span className="text-[9px] bg-slate-200 text-slate-500 px-1.5 py-0.5 rounded mr-2">{ALL_TABS.filter(t => t.type === "imaging").length}</span>
              </div>
              {ALL_TABS.filter(t => t.type === "imaging").map(t => renderTab(t.id, t.label, ImageIcon, t.item?.is_abnormal))}
            </div>
          )}

          {ALL_TABS.filter(t => t.type === "lab" || t.type === "ecg" || t.type === "note").length > 0 && (
            <div className="space-y-1">
              <div className="text-[11px] font-bold text-slate-400 uppercase tracking-widest mb-3 ml-2 flex items-center justify-between">
                化验单与检查 <span className="text-[9px] bg-slate-200 text-slate-500 px-1.5 py-0.5 rounded mr-2">{ALL_TABS.filter(t => t.type === "lab" || t.type === "ecg" || t.type === "note").length}</span>
              </div>
              {ALL_TABS.filter(t => t.type === "lab" || t.type === "ecg" || t.type === "note").map(t => renderTab(t.id, t.label, FileText, t.item?.is_abnormal))}
            </div>
          )}
        </div>
      </div>

      {/* 75% 右侧主视图 - 证据查看器与提交流程 (Detail View) */}
      <div className="flex-1 min-w-0 flex flex-col relative bg-slate-50/50">
        
        {/* 中心视野区 (Content Viewer) */}
        <div className="flex-1 overflow-y-auto p-8 relative">
        
        {activeTab === "vitals" && (
          <div className="animate-in fade-in duration-300 flex flex-col h-full">
            <div className="flex items-center justify-between mb-6 shrink-0">
              <h2 className="text-2xl font-semibold tracking-tight text-slate-800">Patient Vitals & History</h2>
              <div className="text-xs font-medium text-blue-600 bg-blue-50 px-3 py-1 rounded-full flex items-center gap-2 border border-blue-100">
                <span className="relative flex h-2 w-2">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-75"></span>
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-blue-500"></span>
                </span>
                允许编辑修改 (Live EMR)
              </div>
            </div>

            <div className="flex gap-6 shrink-0">
              {/* === 左侧：现代化 患者心电监护仪风格 体征卡 (35%) === */}
              <div className="w-[35%] xl:w-[320px] bg-white border border-slate-200 rounded-2xl shadow-[0_4px_20px_rgba(0,0,0,0.03)] p-6 flex flex-col relative overflow-hidden shrink-0 group hover:border-blue-200 transition-all">
                {/* 装饰性背景 */}
                <div className="absolute top-0 right-0 w-40 h-40 bg-gradient-to-br from-blue-50 to-transparent rounded-bl-full -z-10 opacity-70" />
                
                <div className="flex items-center gap-4 mb-8">
                  <div className="h-16 w-16 rounded-full bg-blue-100 flex items-center justify-center text-blue-600 border-[3px] border-white shadow-md ring-1 ring-slate-100 shrink-0">
                     <User className="h-7 w-7" />
                  </div>
                  <div className="flex flex-col">
                    <h3 className="text-xl font-bold text-slate-800 tracking-tight">{patientName}</h3>
                    <div className="text-sm text-slate-500 font-medium mt-0.5">{patientAge}岁 · {patientSex === "男" ? "男性" : patientSex === "女" ? "女性" : patientSex ?? "N/A"}</div>
                    <div className="flex items-center gap-2 mt-1.5">
                       <span className="bg-slate-100 px-2 py-0.5 rounded text-[10px] font-bold text-slate-500 tracking-widest uppercase">ID: {caseData?.case_id?.slice(0, 8) ?? "Pt-2941"}</span>
                       <span className="text-xs text-slate-500 font-medium">{caseData?.patient_info?.height_cm ?? 175}cm, {caseData?.patient_info?.weight_kg ?? 72}kg</span>
                    </div>
                  </div>
                </div>

                <div className="border-t border-slate-100 pt-5 mt-auto">
                  <h4 className="text-[11px] font-bold text-slate-400 uppercase tracking-widest mb-4 flex items-center gap-2">
                    <Activity className="h-4 w-4 text-blue-500" /> 核心生命体征 (Vitals)
                  </h4>
                  <div className="grid grid-cols-2 gap-3">
                     <div className="bg-slate-50 rounded-xl p-3 border border-slate-100 relative overflow-hidden transition-colors focus-within:ring-2 focus-within:ring-blue-100 focus-within:bg-white">
                       <div className="text-[10px] text-slate-500 font-bold mb-1">体温 (°C)</div>
                       <Input readOnly className="p-0 h-auto border-none bg-transparent shadow-none text-xl font-bold text-slate-800 focus-visible:ring-0 placeholder:text-slate-300 placeholder:font-normal" placeholder="未录入" value={caseData?.patient_info?.temperature || ""} />
                     </div>
                     <div className="bg-slate-50 rounded-xl p-3 border border-slate-100 relative overflow-hidden transition-colors focus-within:ring-2 focus-within:ring-blue-100 focus-within:bg-white">
                       <div className="text-[10px] text-slate-500 font-bold mb-1">心率 (bpm)</div>
                       <Input readOnly className="p-0 h-auto border-none bg-transparent shadow-none text-xl font-bold text-slate-800 focus-visible:ring-0 placeholder:text-slate-300 placeholder:font-normal" placeholder="未录入" value={caseData?.patient_info?.heart_rate || ""} />
                     </div>
                     <div className="bg-slate-50 rounded-xl p-3 border border-slate-100 relative overflow-hidden transition-colors focus-within:ring-2 focus-within:ring-blue-100 focus-within:bg-white">
                       <div className="text-[10px] text-slate-500 font-bold mb-1">血压 (mmHg)</div>
                       <Input readOnly className="p-0 h-auto border-none bg-transparent shadow-none text-xl font-bold text-slate-800 focus-visible:ring-0 placeholder:text-slate-300 placeholder:font-normal" placeholder="未录入" value={caseData?.patient_info?.blood_pressure || ""} />
                     </div>
                     <div className="bg-slate-50 rounded-xl p-3 border border-slate-100 relative overflow-hidden transition-colors focus-within:ring-2 focus-within:ring-blue-100 focus-within:bg-white">
                       <div className="text-[10px] text-slate-500 font-bold mb-1">血氧 (SpO2%)</div>
                       <Input readOnly className="p-0 h-auto border-none bg-transparent shadow-none text-xl font-bold text-slate-800 focus-visible:ring-0 placeholder:text-slate-300 placeholder:font-normal" placeholder="未录入" value={caseData?.patient_info?.spo2 || ""} />
                     </div>
                  </div>
                </div>
              </div>

              {/* === 右侧：主诉与既往史文本流 (65%) === */}
              <div className="flex-1 space-y-4">
                <div className="border border-slate-200 bg-white p-5 rounded-2xl shadow-sm focus-within:ring-2 focus-within:ring-blue-100 transition-all">
                  <label className="text-sm font-medium text-slate-600 mb-3 block">主诉 (Chief Complaint)</label>
                  <Textarea readOnly 
                    className="resize-none border-none shadow-none focus-visible:ring-0 p-0 text-slate-800 font-bold placeholder:text-slate-300 placeholder:font-normal min-h-[40px]"
                    placeholder="未记录 (N/A)"
                    value={caseData?.patient_info?.chief_complaint || ""}
                  />
                </div>
                <div className="border border-slate-200 bg-white p-5 rounded-2xl shadow-sm focus-within:ring-2 focus-within:ring-blue-100 transition-all">
                  <label className="text-sm font-medium text-slate-600 mb-3 block">现病史 (Present Illness)</label>
                  <Textarea readOnly
                    className="resize-none border-none shadow-none focus-visible:ring-0 p-0 text-slate-800 font-bold placeholder:text-slate-300 placeholder:font-normal min-h-[60px]"
                    placeholder="未录入具体现病史... (N/A)"
                    value={caseData?.patient_info?.present_illness || ""}
                  />
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div className="border border-slate-200 bg-white p-4 rounded-xl shadow-sm focus-within:ring-2 focus-within:ring-blue-100 transition-all">
                    <label className="text-sm font-medium text-slate-600 mb-2 block">既往史 (Medical History)</label>
                    <Textarea readOnly
                      className="resize-none border-none shadow-none focus-visible:ring-0 p-0 text-sm text-slate-800 font-semibold placeholder:text-slate-300 placeholder:font-normal min-h-[40px]"
                      placeholder="未录入 (N/A)"
                      value={caseData?.patient_info?.medical_history || ""}
                    />
                  </div>
                  <div className="border border-slate-200 bg-white p-4 rounded-xl shadow-sm focus-within:ring-2 focus-within:ring-blue-100 transition-all">
                    <label className="text-sm font-medium text-amber-600 mb-2 block">过敏与用药 (Allergies/Meds)</label>
                    <Textarea readOnly
                      className="resize-none border-none shadow-none focus-visible:ring-0 p-0 text-sm text-slate-800 font-semibold placeholder:text-amber-200 placeholder:font-normal min-h-[40px]"
                      placeholder="未明示 (N/A)"
                      value={caseData?.patient_info?.allergies || ""}
                    />
                  </div>
                </div>
              </div>
            </div>

            {/* 医生批注区 (Doctor's Annotation) */}
            <div className="mt-8 border-2 border-dashed border-blue-200 bg-[#f8fbff] p-5 rounded-xl relative group focus-within:border-blue-400 focus-within:bg-blue-50/50 transition-colors flex-1 flex flex-col min-h-[200px]">
              <div className="absolute -top-3 left-4 bg-blue-100 text-blue-700 text-xs font-bold px-3 py-1 rounded-full flex items-center gap-1.5 shadow-[0_2px_4px_rgba(0,0,0,0.02)] border border-blue-200">
                 <User className="w-3.5 h-3.5" />
                 医生诊疗批注板 (Doctor's Notepad)
              </div>
              <Textarea 
                 placeholder="全白板模式：向下占据全部剩余空间。在此键入您对该患者病历的分析、修正、或者推断。这些信息将充当后续 LangGraph 的高权重先验知识..."
                 className="mt-2 w-full flex-1 border-none bg-transparent shadow-none focus-visible:ring-0 placeholder:text-blue-300 text-slate-700 text-lg leading-relaxed resize-none p-0"
              />
            </div>
          </div>
        )}

        {activeTabData?.type === "imaging" && (
          <ImagingViewer 
             reportId={activeTabData.item?.evidence_id} 
             threadId={caseData?.patient_thread_id}
             imagePath={activeTabData.item?.file_path} 
             initialStructuredData={activeTabData.item?.structured_data} 
          />
        )}

        {(activeTabData?.type === "lab" || activeTabData?.type === "ecg" || activeTabData?.type === "note") && (
          <div className="animate-in fade-in duration-300 flex flex-col p-8 h-full bg-white border border-slate-200 rounded-xl m-8 shadow-sm overflow-y-auto">
             <div className="flex justify-between items-center mb-6">
               <h2 className="text-xl font-bold text-slate-800">{activeTabData.item?.title}</h2>
               {activeTabData.item?.is_abnormal ? (
                   <span className="bg-red-50 text-red-600 text-xs font-bold px-2 py-1 rounded">存在异常项</span>
               ) : (
                   <span className="bg-green-50 text-green-600 text-xs font-bold px-2 py-1 rounded">未见明显异常</span>
               )}
             </div>
             <div className="bg-slate-50 p-6 rounded-lg border border-slate-100 whitespace-pre-wrap text-sm text-slate-700 font-mono">
                {activeTabData.item?.ai_analysis || (activeTabData.item?.structured_data ? JSON.stringify(activeTabData.item?.structured_data, null, 2) : "无详细报告数据")}
             </div>
          </div>
        )}
        </div>

        {/* 底部审核安全门 (Review Gate) */}
        <div className="h-20 shrink-0 border-t border-slate-200 bg-white/95 backdrop-blur px-8 flex items-center justify-between shadow-[0_-8px_30px_rgba(0,0,0,0.04)] z-10 sticky bottom-0">
           <div className="text-sm text-slate-500 flex flex-col">
              <span className="font-medium text-slate-800">人工审核进度</span>
              <span className="text-xs">已审核 {reviewedTabs.size} / {ALL_TABS.length} 项</span>
           </div>
           <div className="flex items-center gap-3">
             <div className="flex items-center gap-1">
               {ALL_TABS.map(t => (
                 <div key={t.id} className={cn("w-2 h-2 rounded-full transition-colors", reviewedTabs.has(t.id) ? "bg-emerald-500" : "bg-slate-200")} />
               ))}
             </div>
             <Button 
                size="lg"
                onClick={handleReviewPassClick}
                className={cn(
                  "px-8 py-6 text-lg tracking-wide rounded-full font-semibold transition-all shadow-md",
                  (isReviewPassed || isSubmitting)
                    ? "bg-slate-200 text-slate-400 cursor-not-allowed hover:bg-slate-200" 
                    : allReviewed
                      ? "bg-green-600 text-white hover:bg-green-700 hover:shadow-lg hover:-translate-y-0.5"
                      : "bg-slate-300 text-slate-500 cursor-not-allowed hover:bg-slate-300"
                )}
                disabled={isReviewPassed || !allReviewed || isSubmitting}
              >
               <ShieldCheck className="mr-2 h-5 w-5" />
               {isSubmitting ? "正在归档..." : isReviewPassed ? "证据链已锁定 (Locked)" : allReviewed ? "确认人工审核完成" : `还有 ${ALL_TABS.length - reviewedTabs.size} 项未审核`}
              </Button>
           </div>
        </div>
      </div>
    </div>
  );
}
