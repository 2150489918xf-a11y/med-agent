from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from loguru import logger

from app.gateway.services.analyzers.brain_tumor_reporter import generate_brain_report
from app.gateway.services.case_db import update_evidence_data


router = APIRouter(prefix="/api/cases/{case_id}", tags=["brain-report"])

class BrainReportRequest(BaseModel):
    """医生审核确认后提交的空间数据（可能已被医生修正）。"""
    evidence_id: str
    spatial_info: dict      # 医生确认/修正后的空间数据
    slice_png_path: str     # Step 3 产出的切片图路径

@router.post("/brain-report")
async def generate_brain_report_endpoint(
    case_id: str,
    request: BrainReportRequest,
):
    """医生确认空间数据后，调用 Step 4 生成最终报告。"""
    logger.info(f"Generating brain report for case {case_id}, evidence {request.evidence_id}")
    
    try:
        report = await generate_brain_report(
            spatial_info=request.spatial_info,
            slice_png_path=request.slice_png_path,
        )
        
        # 更新 evidence 的 ai_analysis_text 为生成的报告
        update_evidence_data(case_id, request.evidence_id, {
            "ai_analysis": report["report_text"],
            "status": "report_generated",
            "cross_check_passed": report["cross_check_passed"],
            "spatial_info": request.spatial_info,
        })
        
        return {"status": "ok", "report": report}
    except Exception as e:
        logger.error(f"Failed to generate brain report: {e}")
        raise HTTPException(status_code=500, detail=f"生成报告失败: {str(e)}")
