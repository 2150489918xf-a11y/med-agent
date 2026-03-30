"""Imaging reports router for HITL doctor review.

Provides REST API for the frontend to:
- Discover pending reviews (GET with status filter)
- Fetch report details (GET by ID)
- Submit doctor modifications (PUT by ID)
"""

import json
import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from deerflow.config.paths import get_paths
from app.gateway.services.case_db import (
    sync_report_from_file,
    get_reports_by_thread,
    get_report_by_id,
    update_report,
    get_case_by_thread,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/threads/{thread_id}/imaging-reports",
    tags=["imaging-reports"],
)


def _get_reports_dir(thread_id: str) -> Path:
    """Get the imaging-reports directory for a thread."""
    paths = get_paths()
    paths.ensure_thread_dirs(thread_id)
    reports_dir = paths.sandbox_user_data_dir(thread_id) / "imaging-reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    return reports_dir


class DoctorReviewSubmission(BaseModel):
    """Doctor's review submission."""
    doctor_result: dict[str, Any]


@router.get("")
def list_imaging_reports(
    thread_id: str,
    status: str | None = None,
):
    """List imaging reports, optionally filtered by status.

    [ADR-020] Only sync and return reports if the patient has a formal Case
    (i.e., has confirmed scheduling). Otherwise return empty to prevent
    sandbox data from leaking into the EMR database.

    Query params:
        status: Filter by report status (e.g., 'pending_review', 'reviewed')
    """
    # Gate: only allow access if patient has been formally registered
    if not get_case_by_thread(thread_id):
        return {"reports": [], "total": 0}

    reports_dir = _get_reports_dir(thread_id)
    
    # 1. Sync any stray JSON files into DB
    for report_file in sorted(reports_dir.glob("*.json")):
        sync_report_from_file(thread_id, report_file)
            
    # 2. Fetch from DB
    reports = get_reports_by_thread(thread_id, status)

    return {"reports": reports, "total": len(reports)}


@router.get("/{report_id}")
def get_imaging_report(thread_id: str, report_id: str):
    """Get a specific imaging report by ID."""
    # Gate: only allow access if patient has been formally registered
    if not get_case_by_thread(thread_id):
        raise HTTPException(status_code=404, detail="No registered case for this thread")

    reports_dir = _get_reports_dir(thread_id)
    report_file = reports_dir / f"{report_id}.json"

    if report_file.exists():
        sync_report_from_file(thread_id, report_file)

    report = get_report_by_id(report_id)
    if not report:
        raise HTTPException(status_code=404, detail=f"Report {report_id} not found")

    return report


@router.put("/{report_id}")
def submit_doctor_review(
    thread_id: str,
    report_id: str,
    submission: DoctorReviewSubmission,
):
    """Submit doctor's review for an imaging report.

    This changes the report status to 'reviewed', which unblocks the
    submit_for_review tool that is polling this file.
    """
    reports_dir = _get_reports_dir(thread_id)
    report_file = reports_dir / f"{report_id}.json"

    if not report_file.exists():
        raise HTTPException(status_code=404, detail=f"Report file {report_id}.json not found in sandbox")

    # 1. Sync file to ensure it exists in DB
    sync_report_from_file(thread_id, report_file)

    # 2. Update DB and log audit (Option A: Snapshot)
    updated_report = update_report(report_id, submission.doctor_result)
    if not updated_report:
        raise HTTPException(status_code=500, detail="Failed to update report in database")

    # [P1 Sync] Sync to cases table macro evidence array
    from app.gateway.services.case_db import update_case_evidence_from_report
    update_case_evidence_from_report(thread_id, report_id, submission.doctor_result)

    # 3. Write back to sandbox file to unblock the Agent Tool
    try:
        data = json.loads(report_file.read_text(encoding="utf-8"))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read report: {e}")

    # Support re-edit: increment version instead of rejecting already-reviewed reports
    data["version"] = data.get("version", 0) + 1
    data["status"] = "reviewed"
    data["doctor_result"] = submission.doctor_result

    report_file.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    logger.info(f"[HITL] Report {report_id} reviewed by doctor and synced to DB")
    return {"status": "ok", "report_id": report_id, "data": updated_report}


class GenerateDraftRequest(BaseModel):
    doctor_result: dict[str, Any]
    prompt: str | None = None


@router.post("/analyze-cv")
async def stateless_analyze_cv(thread_id: str):
    """
    [Phase 6 Stateless Endpoint] 
    Bypass LangGraph and run CV model (YOLO/DenseNet) directly on the uploaded image.
    Currently returns mock deterministic JSON to unblock frontend.
    """
    import asyncio
    import uuid
    import time
    
    # Simulate CV processing latency
    await asyncio.sleep(1.5)
    
    report_id = f"mock_cv_{uuid.uuid4().hex[:8]}"
    mock_data = {
        "report_id": report_id,
        "thread_id": thread_id,
        "status": "pending_review",
        "version": 1,
        "image_path": "mock_xray.png",
        "ai_result": {
            "findings": [
                {
                    "id": "ai_finding_1",
                    "disease": "Pneumonia",
                    "location_cn": "右下肺",
                    "bbox": [500, 300, 700, 500],
                    "confidence": 0.85
                }
            ],
            "densenet_probs": {
                "Pneumothorax": 0.12,
                "Cardiomegaly": 0.05,
                "Effusion": 0.34
            }
        },
        "doctor_result": {}
    }
    
    # Save the generated CV draft to the file system
    reports_dir = _get_reports_dir(thread_id)
    report_file = reports_dir / f"{report_id}.json"
    report_file.write_text(json.dumps(mock_data, ensure_ascii=False, indent=2), encoding="utf-8")
    
    return {"status": "ok", "report_id": report_id, "data": mock_data}


@router.post("/generate-draft")
async def generate_text_draft(thread_id: str, request: GenerateDraftRequest):
    """
    [Phase 6 Stateless Endpoint]
    A fast Copilot endpoint that takes the doctor's JSON + instructions and returns a readable text report.
    No memory, no LangGraph loop.
    """
    import asyncio
    
    # Simulate LLM generation latency
    await asyncio.sleep(2.0)
    
    # Simulated response incorporating doctor's requested focus
    focus_str = f"重点关注: {request.prompt}。" if request.prompt else ""
    findings = request.doctor_result.get("findings", [])
    finding_summary = "、".join([f"{f.get('location_cn', '某处')}{f.get('disease', '异常')}" for f in findings])
    
    report_text = f"""[AI 放射影像学描述草稿]
    
根据提供的影像与医师圈注特征：
观察到 {finding_summary if finding_summary else "未见明显明显结节或肿块影"}。
{focus_str}双侧胸廓对称，纵隔居中，心影大小形态在正常范围内。双侧膈面光整，肋膈角锐利。

[印象]：
请结合临床症状，建议随诊复查。
"""

    return {"status": "ok", "report_text": report_text}
