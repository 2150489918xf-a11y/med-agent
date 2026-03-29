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
async def list_imaging_reports(
    thread_id: str,
    status: str | None = None,
):
    """List imaging reports, optionally filtered by status.

    Query params:
        status: Filter by report status (e.g., 'pending_review', 'reviewed')
    """
    reports_dir = _get_reports_dir(thread_id)
    reports = []

    for report_file in sorted(reports_dir.glob("*.json")):
        try:
            data = json.loads(report_file.read_text(encoding="utf-8"))
            if status and data.get("status") != status:
                continue
            reports.append(data)
        except Exception as e:
            logger.warning(f"Failed to read report {report_file}: {e}")
            continue

    return {"reports": reports, "total": len(reports)}


@router.get("/{report_id}")
async def get_imaging_report(thread_id: str, report_id: str):
    """Get a specific imaging report by ID."""
    reports_dir = _get_reports_dir(thread_id)
    report_file = reports_dir / f"{report_id}.json"

    if not report_file.exists():
        raise HTTPException(status_code=404, detail=f"Report {report_id} not found")

    try:
        data = json.loads(report_file.read_text(encoding="utf-8"))
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{report_id}")
async def submit_doctor_review(
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
        raise HTTPException(status_code=404, detail=f"Report {report_id} not found")

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

    logger.info(f"[HITL] Report {report_id} reviewed by doctor")
    return {"status": "ok", "report_id": report_id}
