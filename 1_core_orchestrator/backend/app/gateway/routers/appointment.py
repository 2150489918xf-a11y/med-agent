"""Appointment router: preview and confirmation endpoints.

[ADR-021] Appointment workflow:
1. Agent calls preview_appointment tool → returns structured preview JSON
2. Frontend renders interactive confirmation card
3. Patient reviews/edits info → clicks "确认提交"
4. Frontend calls POST /api/threads/{tid}/confirm-appointment
5. This endpoint creates the formal Case + SSE broadcast to doctor dashboard
"""

import json
import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.config.paths import get_paths

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/threads/{thread_id}", tags=["appointment"])


# ── Request / Response Models ──────────────────────────────

class EvidenceSelection(BaseModel):
    """Evidence item selected (or deselected) by the patient."""
    id: str
    selected: bool = True


class ConfirmAppointmentRequest(BaseModel):
    """Patient-confirmed appointment data (may be edited from original preview)."""
    patient_info: dict  # Patient may have edited name, age, complaints etc.
    selected_evidence_ids: list[str]  # Only the evidence items the patient chose to submit
    priority: str = "medium"
    department: str | None = None
    reason: str = ""


class ConfirmAppointmentResponse(BaseModel):
    """Response after successful registration."""
    success: bool
    case_id: str
    short_id: str
    department: str | None
    evidence_count: int
    message: str


# ── Preview Endpoint ───────────────────────────────────────

@router.get("/appointment-preview")
async def get_appointment_preview(thread_id: str) -> dict:
    """Return sandbox data for appointment preview.

    This is a read-only endpoint that returns all staged patient info
    and evidence items from the sandbox, without creating any Case.
    """
    from app.gateway.services import case_db

    # Guard: prevent duplicate
    existing = case_db.get_case_by_thread(thread_id)
    if existing:
        return {
            "type": "appointment_confirmed",
            "case_id": existing.case_id,
            "message": f"已挂号（编号: {existing.case_id[:8]}）",
        }

    paths = get_paths()
    sandbox_dir = paths.sandbox_user_data_dir(thread_id)

    # Read patient info
    patient_info: dict = {}
    intake_file = sandbox_dir / "patient_intake.json"
    if intake_file.exists():
        try:
            patient_info = json.loads(intake_file.read_text(encoding="utf-8"))
        except Exception:
            pass

    # Read evidence items
    evidence_items: list[dict] = []

    # Imaging reports
    reports_dir = sandbox_dir / "imaging-reports"
    if reports_dir.exists():
        for rf in sorted(reports_dir.glob("*.json")):
            try:
                rd = json.loads(rf.read_text(encoding="utf-8"))
                ai = rd.get("ai_result", {})
                findings = ai.get("findings", []) if isinstance(ai, dict) else []
                image_path = rd.get("image_path", "")
                fname = image_path.rsplit("/", 1)[-1] if "/" in image_path else Path(image_path).name
                evidence_items.append({
                    "id": rd.get("report_id", rf.stem),
                    "type": "imaging",
                    "title": f"影像分析: {fname}",
                    "filename": fname,
                    "findings_count": len(findings) if isinstance(findings, list) else 0,
                    "is_abnormal": bool(findings),
                })
            except Exception as e:
                logger.warning(f"Failed to parse report {rf}: {e}")

    # Lab reports (OCR sidecars)
    uploads_dir = paths.sandbox_uploads_dir(thread_id)
    if uploads_dir and uploads_dir.exists():
        for ocr_file in sorted(uploads_dir.glob("*.ocr.md")):
            original = ocr_file.name.replace(".ocr.md", "")
            text = ocr_file.read_text(encoding="utf-8")
            lines = [l.strip() for l in text.split("\n") if l.strip()]
            evidence_items.append({
                "id": f"lab_{original}",
                "type": "lab_report",
                "title": f"化验单: {original}",
                "filename": original,
                "ocr_summary": "\n".join(lines[:6]),
            })

    return {
        "type": "appointment_preview",
        "thread_id": thread_id,
        "patient_info": patient_info,
        "evidence_items": evidence_items,
    }


# ── Confirm Endpoint ───────────────────────────────────────

@router.post("/confirm-appointment", response_model=ConfirmAppointmentResponse)
async def confirm_appointment(thread_id: str, req: ConfirmAppointmentRequest):
    """Formally register the patient's case after review.

    This is the ONLY endpoint that creates a Case in the EMR database.
    It is triggered by the patient clicking "确认提交" on the confirmation card.
    """
    from app.gateway.models.case import (
        AddEvidenceRequest,
        CreateCaseRequest,
        PatientInfo,
        Priority,
    )
    from app.gateway.services import case_db

    # Guard: prevent duplicate
    existing = case_db.get_case_by_thread(thread_id)
    if existing:
        return ConfirmAppointmentResponse(
            success=True,
            case_id=existing.case_id,
            short_id=existing.case_id[:8],
            department=req.department,
            evidence_count=0,
            message=f"您已成功挂号（编号: {existing.case_id[:8]}），无需重复操作。",
        )

    # Build PatientInfo from edited data
    patient_info = PatientInfo(**{
        k: v for k, v in req.patient_info.items()
        if hasattr(PatientInfo, k) and v is not None
    })

    # Write back edited patient info to sandbox (for consistency)
    paths = get_paths()
    sandbox_dir = paths.sandbox_user_data_dir(thread_id)
    intake_file = sandbox_dir / "patient_intake.json"
    intake_file.write_text(
        json.dumps(req.patient_info, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # Map priority
    priority_map = {
        "low": Priority.LOW,
        "medium": Priority.MEDIUM,
        "high": Priority.HIGH,
        "critical": Priority.CRITICAL,
    }
    case_priority = priority_map.get(req.priority.lower(), Priority.MEDIUM)

    # Create the formal Case
    new_case = case_db.create_case(CreateCaseRequest(
        patient_thread_id=thread_id,
        priority=case_priority,
        patient_info=patient_info,
    ))
    logger.info(f"[CONFIRM] Created case {new_case.case_id} for thread {thread_id}")

    # Attach only the evidence items that the patient selected
    selected_ids = set(req.selected_evidence_ids)
    reports_dir = sandbox_dir / "imaging-reports"
    report_files: list[Path] = []

    if reports_dir.exists():
        report_files = sorted(reports_dir.glob("*.json"))
        for rf in report_files:
            try:
                rd = json.loads(rf.read_text(encoding="utf-8"))
                report_id = rd.get("report_id", rf.stem)
                if report_id not in selected_ids:
                    continue  # Skipped by patient

                ai_result = rd.get("ai_result", {})
                image_path = rd.get("image_path", "")
                findings = ai_result.get("findings", []) if isinstance(ai_result, dict) else []
                fname = image_path.rsplit("/", 1)[-1] if "/" in image_path else image_path

                case_db.add_evidence(new_case.case_id, AddEvidenceRequest(
                    evidence_id=report_id,
                    type="imaging",
                    title=f"影像分析: {fname}",
                    source="ai_generated",
                    file_path=image_path,
                    structured_data=ai_result if isinstance(ai_result, dict) else None,
                    ai_analysis=json.dumps(ai_result, ensure_ascii=False)[:500] if ai_result else None,
                    is_abnormal=bool(findings),
                ))
            except Exception as e:
                logger.warning(f"[CONFIRM] Failed to process report {rf}: {e}")

    # Sync reports to DB for ImagingViewer
    for rf in report_files:
        try:
            rd = json.loads(rf.read_text(encoding="utf-8"))
            if rd.get("report_id", rf.stem) in selected_ids:
                case_db.sync_report_from_file(thread_id, rf)
        except Exception as e:
            logger.warning(f"[CONFIRM] Failed to sync report: {e}")

    # Attach lab reports (OCR) as evidence
    uploads_dir = paths.sandbox_uploads_dir(thread_id)
    if uploads_dir and uploads_dir.exists():
        for ocr_file in sorted(uploads_dir.glob("*.ocr.md")):
            original = ocr_file.name.replace(".ocr.md", "")
            lab_id = f"lab_{original}"
            if lab_id not in selected_ids:
                continue

            ocr_text = ocr_file.read_text(encoding="utf-8")
            case_db.add_evidence(new_case.case_id, AddEvidenceRequest(
                evidence_id=lab_id,
                type="lab_report",
                title=f"化验单: {original}",
                source="ocr",
                ai_analysis=ocr_text[:500] if ocr_text else None,
                is_abnormal=False,
            ))

    evidence_count = len(selected_ids)

    # ── SSE Broadcast to doctor dashboard ──
    try:
        from app.gateway.routers.cases import _broadcast_event
        _broadcast_event("new_case", {
            "case_id": new_case.case_id,
            "priority": case_priority.value,
            "chief_complaint": patient_info.chief_complaint or "未填写",
        })
        logger.info(f"[CONFIRM] SSE broadcast: new_case {new_case.case_id}")
    except Exception as e:
        logger.warning(f"[CONFIRM] SSE broadcast failed: {e}")

    dept_text = f"，建议科室：{req.department}" if req.department else ""
    short_id = new_case.case_id[:8]

    return ConfirmAppointmentResponse(
        success=True,
        case_id=new_case.case_id,
        short_id=short_id,
        department=req.department,
        evidence_count=evidence_count,
        message=f"挂号成功！就诊编号 {short_id}{dept_text}。已提交 {evidence_count} 份检查资料。",
    )
