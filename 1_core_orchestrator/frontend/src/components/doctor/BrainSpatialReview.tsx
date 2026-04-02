import React, { useState } from 'react';
import { Streamdown } from "streamdown";
import { streamdownPlugins } from "@/core/streamdown";

// Since we are mocking the dependency for now, we just define type props
export interface BrainSpatialReviewProps {
  spatialInfo: any;
  slicePngPath?: string;
  evidenceId: string;
  caseId: string;
  status: string;
}

export function BrainSpatialReview({ 
  spatialInfo, 
  slicePngPath, 
  evidenceId, 
  caseId,
  status: initialStatus
}: BrainSpatialReviewProps) {
  const [editableInfo, setEditableInfo] = useState({
    location: spatialInfo?.location || '',
    vol_et: spatialInfo?.volumes?.ET || 0,
    vol_ed: spatialInfo?.volumes?.ED || 0,
    vol_ncr: spatialInfo?.volumes?.NCR || 0,
    vol_wt: spatialInfo?.volumes?.WT || 0,
    crosses_midline: spatialInfo?.spatial_relations?.crosses_midline || false,
    brainstem_dist: spatialInfo?.spatial_relations?.brainstem_min_dist_mm || 0,
    ventricle_ratio: spatialInfo?.spatial_relations?.ventricle_compression_ratio || 1.0,
    midline_shift: spatialInfo?.spatial_relations?.midline_shift_mm || 0.0
  });

  const [loading, setLoading] = useState(false);
  const [report, setReport] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState(initialStatus);

  const handleGenerateReport = async () => {
    try {
      setLoading(true);
      setError(null);
      
      // Map local state back to the expected API format
      const payloadInfo = {
        ...spatialInfo,
        location: editableInfo.location,
        volumes: {
          ...spatialInfo?.volumes,
          ET: Number(editableInfo.vol_et),
          ED: Number(editableInfo.vol_ed),
          NCR: Number(editableInfo.vol_ncr),
          WT: Number(editableInfo.vol_wt),
        },
        spatial_relations: {
          ...spatialInfo?.spatial_relations,
          crosses_midline: editableInfo.crosses_midline,
          brainstem_min_dist_mm: Number(editableInfo.brainstem_dist),
          ventricle_compression_ratio: Number(editableInfo.ventricle_ratio),
          midline_shift_mm: Number(editableInfo.midline_shift)
        }
      };

      const res = await fetch(`/api/cases/${caseId}/brain-report`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          evidence_id: evidenceId,
          spatial_info: payloadInfo,
          slice_png_path: slicePngPath || ''
        })
      });

      if (!res.ok) {
        throw new Error(`请求失败: ${res.statusText}`);
      }
      
      const data = await res.json();
      setReport(data.report);
      setStatus("report_generated");
      
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const getImageUrl = () => {
    if (!slicePngPath) return null;
    const filename = slicePngPath.split(/[\/\\]/).pop();
    // Use the generic artifact endpoint, using current thread ID if available
    // or passing a placeholder which the backend might not strictly require for pure files
    const currentThreadId = new URLSearchParams(window.location.search).get('threadId') || 'local';
    return `/api/threads/${currentThreadId}/artifacts/${filename}`;
  };

  return (
    <div className="flex flex-col h-full overflow-hidden bg-slate-50">
      <div className="border-b px-4 py-3 bg-white flex items-center justify-between sticky top-0 z-10">
        <h3 className="text-lg font-medium flex items-center gap-2 text-slate-800">
          🧠脑肿瘤分析结果
          {status === 'pending_doctor_review' && (
            <span className="text-xs bg-amber-100 text-amber-800 px-2 py-1 rounded-full animate-pulse border border-amber-200">
              待医生审核
            </span>
          )}
          {status === 'report_generated' && (
            <span className="text-xs bg-emerald-100 text-emerald-800 px-2 py-1 rounded-full border border-emerald-200">
              报告已生成
            </span>
          )}
        </h3>
      </div>

      <div className="flex-1 overflow-auto p-4 flex flex-col lg:flex-row gap-6">
        {/* Left Column: Image Viewer */}
        <div className="flex-1 bg-white rounded-xl shadow-sm border overflow-hidden flex flex-col min-h-[400px]">
          <div className="bg-slate-100 px-4 py-2 border-b text-sm font-medium text-slate-600">
            2D 渲染切片图 (T1ce + FLAIR)
          </div>
          <div className="flex-1 relative flex items-center justify-center bg-black">
            {slicePngPath ? (
              <img 
                src={getImageUrl() || ''} 
                alt="Brain Slice Analysis" 
                className="max-w-full max-h-full object-contain"
                onError={(e) => {
                  /* @ts-ignore */
                  e.target.style.display = 'none';
                  e.currentTarget.parentElement!.innerHTML = '<div class="text-slate-400">图片加载失败</div>';
                }}
              />
            ) : (
              <div className="text-slate-500">暂无包含肿瘤的切片图片</div>
            )}
          </div>
        </div>

        {/* Right Column: Editable Spatial Info */}
        <div className="flex-1 flex flex-col gap-4 min-w-[300px] max-w-xl">
          <div className="bg-white rounded-xl shadow-sm border p-5">
            <h4 className="font-semibold text-slate-800 mb-4 border-b pb-2 flex items-center justify-between">
              几何特征校验面板
              <span className="text-xs font-normal text-slate-500">可手动修正异常值</span>
            </h4>
            
            <div className="space-y-4">
              {/* Location */}
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">
                  解剖位置 <span className="text-slate-400 text-xs font-normal">(MNI+AAL3 图谱定位)</span>
                </label>
                <input 
                  type="text" 
                  value={editableInfo.location}
                  onChange={(e) => setEditableInfo({...editableInfo, location: e.target.value})}
                  className="w-full text-sm p-2 border rounded focus:ring-2 focus:ring-blue-200 focus:border-blue-400 outline-none transition-all"
                  disabled={status === "report_generated"}
                />
              </div>

              {/* Volumes grid */}
              <div className="grid grid-cols-2 gap-3 text-sm">
                <div className="bg-slate-50 p-3 rounded border">
                  <label className="block text-xs text-slate-500 mb-1">增强核心 (ET) 体积</label>
                  <div className="flex items-center">
                    <input 
                      type="number" step="0.1" 
                      value={editableInfo.vol_et}
                      onChange={(e) => setEditableInfo({...editableInfo, vol_et: e.target.value})}
                      className="w-full bg-transparent border-b border-transparent hover:border-slate-300 focus:border-blue-400 outline-none"
                      disabled={status === "report_generated"}
                    />
                    <span className="text-slate-500 text-xs ml-1">cm³</span>
                  </div>
                </div>
                <div className="bg-slate-50 p-3 rounded border">
                  <label className="block text-xs text-slate-500 mb-1">水肿区 (ED) 体积</label>
                  <div className="flex items-center">
                    <input 
                      type="number" step="0.1"
                      value={editableInfo.vol_ed}
                      onChange={(e) => setEditableInfo({...editableInfo, vol_ed: e.target.value})}
                      className="w-full bg-transparent border-b border-transparent hover:border-slate-300 focus:border-blue-400 outline-none"
                      disabled={status === "report_generated"}
                    />
                    <span className="text-slate-500 text-xs ml-1">cm³</span>
                  </div>
                </div>
                <div className="bg-slate-50 p-3 rounded border">
                  <label className="block text-xs text-slate-500 mb-1">坏死核心 (NCR) 体积</label>
                  <div className="flex items-center">
                    <input 
                      type="number" step="0.1"
                      value={editableInfo.vol_ncr}
                      onChange={(e) => setEditableInfo({...editableInfo, vol_ncr: e.target.value})}
                      className="w-full bg-transparent border-b border-transparent hover:border-slate-300 focus:border-blue-400 outline-none"
                      disabled={status === "report_generated"}
                    />
                    <span className="text-slate-500 text-xs ml-1">cm³</span>
                  </div>
                </div>
                <div className="bg-slate-50 p-3 rounded border">
                  <label className="block text-xs text-slate-500 mb-1">全肿瘤 (WT) 体积</label>
                  <div className="flex items-center">
                    <input 
                      type="number" step="0.1"
                      value={editableInfo.vol_wt}
                      onChange={(e) => setEditableInfo({...editableInfo, vol_wt: e.target.value})}
                      className="w-full bg-transparent border-b border-transparent hover:border-slate-300 focus:border-blue-400 outline-none font-medium"
                      disabled={status === "report_generated"}
                    />
                    <span className="text-slate-500 text-xs ml-1">cm³</span>
                  </div>
                </div>
              </div>

              {/* Spatial Relations */}
              <div className="space-y-3 pt-2">
                <h5 className="text-sm font-medium text-slate-700">关键空间特征 (手术决策相关)</h5>
                
                <div className="flex items-center justify-between p-2 bg-slate-50 border rounded text-sm">
                  <span className="text-slate-600">肿瘤跨跨越正中矢状面</span>
                  <label className="relative inline-flex items-center cursor-pointer">
                    <input 
                      type="checkbox" 
                      className="sr-only peer" 
                      checked={editableInfo.crosses_midline}
                      onChange={(e) => setEditableInfo({...editableInfo, crosses_midline: e.target.checked})}
                      disabled={status === "report_generated"}
                    />
                    <div className={"w-9 h-5 bg-slate-200 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-slate-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-blue-500 " + (status === "report_generated" ? "opacity-50" : "")}></div>
                  </label>
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div className="p-2 bg-slate-50 border rounded text-sm">
                    <span className="text-slate-500 text-xs block mb-1">距脑干最短距离</span>
                    <div className="flex items-center">
                      <input 
                        type="number" step="0.1" 
                        value={editableInfo.brainstem_dist}
                        onChange={(e) => setEditableInfo({...editableInfo, brainstem_dist: e.target.value})}
                        className="w-full bg-transparent outline-none font-medium"
                        disabled={status === "report_generated"}
                      />
                      <span className="text-slate-400 text-xs ml-1">mm</span>
                    </div>
                  </div>
                  <div className="p-2 bg-slate-50 border rounded text-sm">
                    <span className="text-slate-500 text-xs block mb-1">中线受压偏移距离</span>
                    <div className="flex items-center">
                      <input 
                        type="number" step="0.1" 
                        value={editableInfo.midline_shift}
                        onChange={(e) => setEditableInfo({...editableInfo, midline_shift: e.target.value})}
                        className="w-full bg-transparent outline-none font-medium"
                        disabled={status === "report_generated"}
                      />
                      <span className="text-slate-400 text-xs ml-1">mm</span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Action Button */}
              {status === "pending_doctor_review" && (
                 <div className="pt-4 mt-2 border-t">
                    <button 
                      onClick={handleGenerateReport}
                      disabled={loading}
                      className="w-full bg-blue-600 hover:bg-blue-700 text-white font-medium py-2.5 rounded shadow-sm flex items-center justify-center transition-colors disabled:opacity-75"
                    >
                      {loading ? (
                        <span className="flex items-center gap-2">
                          <svg className="animate-spin -ml-1 mr-2 h-4 w-4 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                          </svg>
                          大模型正在生成可控报告 (Step 4)...
                        </span>
                      ) : "✓ 确认空间数据，生成诊断报告"}
                    </button>
                    {error && (
                      <p className="text-red-500 text-xs mt-2 text-center">{error}</p>
                    )}
                 </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Bottom Result Area */}
      {report && (
         <div className="border-t bg-white p-5 max-h-[40vh] overflow-y-auto">
            <h4 className="font-medium text-slate-800 mb-3 flex items-center justify-between">
              📄 AI 影像学报告生成结果
              {report.cross_check_passed ? (
                <span className="text-xs bg-green-100 text-green-700 px-2 py-1 rounded-full border border-green-200">数据对账通过</span>
              ) : (
                <span className="text-xs bg-red-100 text-red-700 px-2 py-1 rounded-full border border-red-200" title="模型生成内容可能存在幻觉，与底层计算数据不一">⚠️ 强行篡改警告</span>
              )}
            </h4>
            <div className="prose prose-slate prose-sm max-w-none bg-slate-50 p-4 rounded border">
              <Streamdown {...streamdownPlugins}>
                {report.report_text || "无文本内容"}
              </Streamdown>
            </div>
         </div>
      )}
    </div>
  );
}
