"""Preview Appointment tool: generates a structured preview for patient review.

[ADR-021] This tool is called by the Agent when the patient agrees to register.
It reads all sandbox data (patient info + analysis results) and returns a structured
preview that the frontend renders as an interactive confirmation card.

The tool ONLY reads sandbox data — it does NOT create any Case or write to the database.
Actual registration happens when the patient clicks "确认提交" on the frontend,
which triggers POST /api/threads/{tid}/confirm-appointment.
"""

import json
import logging
from pathlib import Path

from langchain.tools import ToolRuntime, tool
from langgraph.typing import ContextT
from pydantic import BaseModel, Field

from app.core.thread_state import ThreadState
from app.core.config.paths import get_paths

logger = logging.getLogger(__name__)


class PreviewAppointmentSchema(BaseModel):
    """Schema for generating appointment preview."""
    priority: str = Field(
        "medium",
        description="基于症状严重程度的分诊优先级: low, medium, high, critical"
    )
    department: str | None = Field(
        None,
        description="建议科室，如 '呼吸内科', '骨科', '心内科'"
    )
    reason: str = Field(
        ...,
        description="挂号原因摘要（1-2 句话概括患者情况）"
    )


@tool("preview_appointment", args_schema=PreviewAppointmentSchema, parse_docstring=True)
async def preview_appointment_tool(
    runtime: ToolRuntime[ContextT, ThreadState],
    priority: str = "medium",
    department: str | None = None,
    reason: str = "",
) -> str:
    """Generate a preview of the appointment registration for patient review.

    Call this tool when the patient confirms they want to register. The system will
    display an interactive confirmation card where the patient can review, edit,
    and confirm their information before final submission.

    Args:
        priority: Triage priority level (low/medium/high/critical) based on symptoms.
        department: Suggested medical department for the consultation.
        reason: Brief summary of why this appointment is being scheduled.
    """
    thread_id = None
    if runtime and runtime.context:
        thread_id = runtime.context.get("thread_id")
    if not thread_id:
        return json.dumps({"error": "Internal error: thread_id not available"})

    try:
        from app.gateway.services import case_db

        # Guard: prevent duplicate registration
        existing_case = case_db.get_case_by_thread(thread_id)
        if existing_case:
            return json.dumps({
                "type": "appointment_confirmed",
                "case_id": existing_case.case_id,
                "message": f"您已成功挂号（编号: {existing_case.case_id[:8]}），无需重复挂号。",
            }, ensure_ascii=False)

        paths = get_paths()
        sandbox_dir = paths.sandbox_user_data_dir(thread_id)

        # ── Step 1: 读取患者基本信息 ──
        patient_info: dict = {}
        intake_file = sandbox_dir / "patient_intake.json"
        if intake_file.exists():
            try:
                patient_info = json.loads(intake_file.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError) as e:
                logger.warning(f"[PREVIEW] Failed to read patient_intake.json: {e}")

        # ── Step 2: 读取所有检查资料 ──
        evidence_items: list[dict] = []

        # 扫描影像分析报告
        reports_dir = sandbox_dir / "imaging-reports"
        if reports_dir.exists():
            for report_file in sorted(reports_dir.glob("*.json")):
                try:
                    report_data = json.loads(report_file.read_text(encoding="utf-8"))
                    ai_result = report_data.get("ai_result", {})
                    image_path = report_data.get("image_path", "")

                    # 提取发现摘要
                    findings = []
                    is_abnormal = False
                    if isinstance(ai_result, dict):
                        findings = ai_result.get("findings", ai_result.get("abnormalities", []))
                        if findings:
                            is_abnormal = True

                    filename = image_path.rsplit("/", 1)[-1] if "/" in image_path else Path(image_path).name

                    evidence_items.append({
                        "id": report_data.get("report_id", report_file.stem),
                        "type": "imaging",
                        "title": f"影像分析: {filename}",
                        "filename": filename,
                        "findings_count": len(findings) if isinstance(findings, list) else 0,
                        "is_abnormal": is_abnormal,
                        "findings_brief": "; ".join(
                            f.get("label", f.get("class", "unknown"))
                            for f in (findings[:5] if isinstance(findings, list) else [])
                        ),
                    })
                except Exception as e:
                    logger.warning(f"[PREVIEW] Failed to parse report {report_file}: {e}")

        # 扫描 OCR 化验单（通过 uploads 目录的 sidecar 文件）
        uploads_dir = paths.sandbox_uploads_dir(thread_id)
        if uploads_dir and uploads_dir.exists():
            for ocr_file in sorted(uploads_dir.glob("*.ocr.md")):
                original_name = ocr_file.name.replace(".ocr.md", "")
                ocr_text = ocr_file.read_text(encoding="utf-8")
                # 提取前几行作为摘要
                lines = [l.strip() for l in ocr_text.split("\n") if l.strip()]
                summary = "\n".join(lines[:6]) if lines else "（OCR 内容为空）"

                evidence_items.append({
                    "id": f"lab_{original_name}",
                    "type": "lab_report",
                    "title": f"化验单: {original_name}",
                    "filename": original_name,
                    "ocr_summary": summary,
                    "is_abnormal": False,  # 化验单异常由 Agent 在对话中判断
                })

        # ── Step 3: 构造预览数据 ──
        preview_data = {
            "type": "appointment_preview",
            "thread_id": thread_id,
            "patient_info": patient_info,
            "evidence_items": evidence_items,
            "suggested_priority": priority,
            "suggested_department": department,
            "reason": reason,
        }

        logger.info(
            f"[PREVIEW] Generated preview for thread {thread_id}: "
            f"{len(evidence_items)} evidence items"
        )

        # 返回给 Agent 的消息（前端会检测 type=appointment_preview 并渲染为交互卡片）
        return json.dumps(preview_data, ensure_ascii=False)

    except Exception as e:
        logger.error(f"[PREVIEW] Failed to generate preview: {e}", exc_info=True)
        return json.dumps({"error": f"预览生成失败，请稍后重试。({str(e)})"}, ensure_ascii=False)
