"""Analyzer for lab and text-heavy medical reports.

[ADR-032 修订] 移除图像压缩流程
原设计中 optimize_lab_image 会将化验单灰度化 + 缩放至 2048px + JPEG 85 压缩，
实测发现压缩后 OCR 准确率断崖式下降（"NE%" → "东北", "血小板计数" → "连续统计"），
根因是 JPEG 压缩 artifact 破坏了小字体和特殊符号（%, #, ↓）的边缘像素。
现改为直接使用原图送入 VLM OCR，牺牲少量传输耗时换取医疗级识别准确率。

[ADR-036] 新增数值校验环节
OCR 完成后对清洗后 Markdown 执行两轮校验：
1. 小数点位移检测：结果值 vs 参考区间 vs 箭头标记的三角自洽性验证
2. 双源数值对账：PaddleOCR 原始数值 vs Qwen 清洗后数值的集合差异分析
校验告警挂载到 structured_data["value_warnings"]，前端据此渲染告警 UI。
"""

import asyncio
from loguru import logger
from pathlib import Path

from app.gateway.services.analyzer_registry import AnalysisResult
from app.gateway.services.vision_gateway import enhance_lab_report
from app.gateway.services.paddle_ocr import fetch_medical_report_ocr, _extract_title_from_markdown
from app.gateway.services.lab_value_validator import validate_lab_values
from app.core.config.paths import get_paths


class LabOCRAnalyzer:
    """Uses PaddleOCR-VL model to extract markdown from lab reports."""
    
    async def analyze(self, image_path: str, thread_id: str, original_filename: str) -> AnalysisResult:
        outputs_dir = get_paths().sandbox_outputs_dir(thread_id)
        outputs_dir.mkdir(parents=True, exist_ok=True)
        
        safe_filename = Path(image_path).name # The already safe name 
        enhanced_name = f"enhanced_{safe_filename}"
        enhanced_host = str(outputs_dir / enhanced_name)

        # Step 1: Enhance Image for text extraction (使用原图，不压缩)
        if Path(image_path).exists():
             await asyncio.to_thread(enhance_lab_report, image_path, enhanced_host)
        else:
             logger.warning(f"File missing, skipping enhancement: {image_path}")

        # Step 2: Extract text using VLM (直接使用原图以保证最高识别精度)
        # [ADR-035] 返回值变为 (markdown, ocr_raw_numbers) 元组
        ocr_markdown, ocr_raw_numbers = await fetch_medical_report_ocr(image_path)
        logger.info(f"VLM OCR yield ({original_filename}): {len(ocr_markdown)} chars, {len(ocr_raw_numbers)} numbers" if ocr_markdown else f"VLM Empty ({original_filename})")

        evidence_title = original_filename
        if ocr_markdown:
             # Cache to sidecar (useful for development and debugging)
             uploads_dir = Path(image_path).parent
             sidecar_path = uploads_dir / f"{safe_filename}.ocr.md"
             sidecar_path.write_text(ocr_markdown, encoding="utf-8")
             
             extracted_title = _extract_title_from_markdown(ocr_markdown)
             if extracted_title:
                 evidence_title = extracted_title

        # Step 3: [ADR-036] 数值校验——小数点位移检测 + 双源对账
        # 校验器是纯函数，不修改 ocr_markdown，仅产出告警列表
        value_warnings: list[dict] = []
        if ocr_markdown:
            value_warnings = validate_lab_values(ocr_markdown, ocr_raw_numbers)

        # 构建 structured_data，同时存储原始数值指纹和校验告警
        structured = {}
        if ocr_raw_numbers:
            structured["ocr_raw_numbers"] = ocr_raw_numbers
        if value_warnings:
            structured["value_warnings"] = value_warnings
            # 有高严重度告警时标记 abnormal，提升前端可见性
            has_high_severity = any(w.get("severity") == "high" for w in value_warnings)
            if has_high_severity:
                structured["value_validation_status"] = "alert"
            else:
                structured["value_validation_status"] = "warning"
        else:
            structured["value_validation_status"] = "passed"

        return AnalysisResult(
            filename=original_filename,
            category="", # Overwritten by registry dispatcher
            confidence=0.0,
            analyzer_name="",
            evidence_type="lab",
            evidence_title=evidence_title,
            ai_analysis_text=ocr_markdown,
            structured_data=structured if structured else None,
            # 有高严重度校验告警时也视为异常，触发前端强调显示
            is_abnormal=any(w.get("severity") == "high" for w in value_warnings),
            enhanced_file_path=f"/mnt/user-data/outputs/{enhanced_name}" if Path(enhanced_host).exists() else None
        )
