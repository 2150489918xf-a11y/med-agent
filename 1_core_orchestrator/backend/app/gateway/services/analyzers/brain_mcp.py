"""脑肿瘤 MRI 切片分析器 (Brain Tumor Analyzer)。

架构决策 (ADR-033):
- 本模块为"脑肿瘤 HITL 分割"子系统的后端调度入口。
- 当 CLIP 视觉网关将上传图片打标为 brain_mri 时，
  parallel_analyzer 会通过注册表将任务委托给本模块。
- 本模块调用远端 MCP 微服务 (mcp_brain_tumor) 执行 YOLO-Seg 实例分割，
  获取不规则多边形蒙版坐标 (polygon) 和肿瘤分类结果。
- VLM 解剖学推理部分 (任务3) 暂缓，未来将通过 RAG 工具链集成。

返回的 AnalysisResult 中:
- structured_data.findings[].polygon: 扁平坐标数组 [x1,y1,x2,y2,...]
- structured_data.findings[].disease: 肿瘤类别 (Glioma/Meningioma/Pituitary)
"""

import asyncio
import json
import logging
import uuid
from pathlib import Path

from app.gateway.services.analyzer_registry import AnalysisResult
from app.gateway.services.vision_gateway import enhance_medical_imaging
from app.core.config.paths import get_paths

logger = logging.getLogger(__name__)


async def _call_brain_mcp(image_path: str, thread_id: str, original_filename: str) -> dict | None:
    """调用脑肿瘤 MCP 微服务进行 YOLO-Seg 实例分割。

    当微服务未部署时，返回 None（系统降级到 VLM fallback）。
    """
    # 动态导入，避免在服务未部署时阻塞启动
    try:
        from app.gateway.services.mcp_brain_client import analyze_brain_mri
    except ImportError:
        logger.warning(
            "[BrainMCP] mcp_brain_client 模块不存在，"
            "脑肿瘤 MCP 微服务可能尚未部署。降级跳过。"
        )
        return None

    logger.info(f"[BrainMCP] 开始分析脑部 MRI: {original_filename}")

    try:
        result = await analyze_brain_mri(image_path)
    except Exception as e:
        logger.error(f"[BrainMCP] MCP 调用失败 ({original_filename}): {e}")
        return None

    if not result:
        logger.warning(f"[BrainMCP] MCP 引擎返回空结果: {original_filename}")
        return None

    # 将分析结果写入沙盒 JSON，供医生工作站加载审阅
    report_id = str(uuid.uuid4())[:8]
    paths = get_paths()
    reports_dir = paths.sandbox_user_data_dir(thread_id) / "imaging-reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    report_file = reports_dir / f"{report_id}.json"

    report_data = {
        "report_id": report_id,
        "thread_id": thread_id,
        "status": "pending_review",
        "image_path": image_path,
        "modality": "brain_mri",  # 区分于 xray 的模态标记
        "ai_result": result,
        "doctor_result": None,
    }
    report_file.write_text(
        json.dumps(report_data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    total_findings = len(result.get("findings", []))
    logger.info(
        f"[BrainMCP] 分析完成: {original_filename} → report_id={report_id}, "
        f"发现 {total_findings} 个疑似病灶"
    )
    return result


class BrainTumorAnalyzer:
    """脑肿瘤 MRI 分割分析器。

    使用远端 YOLO-Seg 微服务进行实例分割，
    返回包含 polygon 多边形蒙版坐标的 AnalysisResult。
    """

    async def analyze(self, image_path: str, thread_id: str, original_filename: str) -> AnalysisResult:
        outputs_dir = get_paths().sandbox_outputs_dir(thread_id)
        outputs_dir.mkdir(parents=True, exist_ok=True)

        safe_filename = Path(image_path).name
        enhanced_name = f"enhanced_{safe_filename}"
        enhanced_host = str(outputs_dir / enhanced_name)

        # Step 1: CLAHE 增强（提升 MRI 对比度，便于医生肉眼审阅）
        if Path(image_path).exists():
            await asyncio.to_thread(enhance_medical_imaging, image_path, enhanced_host)
        else:
            logger.warning(f"[BrainMCP] 文件不存在，跳过增强: {image_path}")

        # Step 2: 调用 MCP 微服务进行脑肿瘤分割
        result = await _call_brain_mcp(image_path, thread_id, original_filename)

        if result:
            findings = result.get("findings", [])
            structured = {
                "mcp_status": "completed",
                "modality": "brain_mri",
                "findings_count": len(findings),
                # 将完整的 findings（含 polygon 坐标）传递给前端
                "findings": findings,
            }
            has_abnormal = len(findings) > 0
        else:
            structured = None
            has_abnormal = False

        return AnalysisResult(
            filename=original_filename,
            category="",  # 由注册表调度器覆写
            confidence=0.0,
            analyzer_name="",
            evidence_type="imaging",
            evidence_title="脑部核磁共振 (MRI)",
            structured_data=structured,
            is_abnormal=has_abnormal,
            enhanced_file_path=(
                f"/mnt/user-data/outputs/{enhanced_name}"
                if Path(enhanced_host).exists() else None
            ),
        )
