"""Upload router for handling file uploads."""

import asyncio
import json
import logging
import sys
import uuid
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

from deerflow.config.app_config import get_app_config
from deerflow.config.paths import get_paths
from deerflow.sandbox.sandbox_provider import get_sandbox_provider
from deerflow.uploads.manager import (
    PathTraversalError,
    delete_file_safe,
    enrich_file_listing,
    ensure_uploads_dir,
    get_uploads_dir,
    list_files_in_dir,
    normalize_filename,
    upload_artifact_url,
    upload_virtual_path,
)
from deerflow.utils.file_conversion import CONVERTIBLE_EXTENSIONS, convert_file_to_markdown

logger = logging.getLogger(__name__)

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".webp"}

router = APIRouter(prefix="/api/threads/{thread_id}/uploads", tags=["uploads"])


# ── [ADR-021] MCP Vision Engine 直调辅助函数 ──────────────────────
# 在上传管线中直接调用 MCP Vision 引擎进行影像分析，
# 避免经过 Agent → MCP Client 的间接路径，节省 5+ 秒的 LLM 调用开销。

async def _call_mcp_analyze(image_path: str, thread_id: str, filename: str) -> dict | None:
    """直接调用 MCP Vision 引擎分析影像并将结果写入沙箱。

    使用 import engine 直接在进程内调用（方案 B），
    不走 MCP SSE 网络协议。由于 uploads 路由的 for 循环是顺序的，
    不会出现 GPU 并发竞争。

    Args:
        image_path: 待分析影像的绝对路径
        thread_id: 患者会话 ID，用于定位沙箱目录
        filename: 原始文件名，用于日志

    Returns:
        MCP 引擎返回的结构化分析结果 dict，失败时返回 None
    """
    # 将 MCP 服务目录加入 sys.path（仅首次，惰性加载）
    mcp_dir = Path(__file__).resolve().parents[4] / "3_mcp_medical_vision" / "mcp_chest_xray"
    if str(mcp_dir) not in sys.path:
        sys.path.insert(0, str(mcp_dir))

    # 惰性导入 engine 模块（首次调用时会加载模型权重）
    import engine as vision_engine  # noqa: E402

    logger.info(f"[ADR-021] 开始自动 MCP 分析: {filename}")

    # 在线程池中执行 GPU 推理，不阻塞事件循环
    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(
        None, lambda: vision_engine.analyze(image_path, enable_sam=False)
    )

    if not result:
        logger.warning(f"[ADR-021] MCP 引擎返回空结果: {filename}")
        return None

    # 将分析结果写入沙箱（复用 save_analysis_result 的文件格式，保持一致性）
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
        "ai_result": result,
        "doctor_result": None,
    }
    report_file.write_text(
        json.dumps(report_data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    total_findings = result.get("summary", {}).get("total_findings", 0)
    logger.info(
        f"[ADR-021] MCP 自动分析完成: {filename} → report_id={report_id}, "
        f"findings={total_findings}"
    )
    return result


class UploadResponse(BaseModel):
    """Response model for file upload."""

    success: bool
    files: list[dict[str, str]]
    message: str


@router.post("", response_model=UploadResponse)
async def upload_files(
    thread_id: str,
    files: list[UploadFile] = File(...),
) -> UploadResponse:
    """Upload multiple files to a thread's uploads directory."""
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")

    try:
        uploads_dir = ensure_uploads_dir(thread_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    sandbox_uploads = get_paths().sandbox_uploads_dir(thread_id)
    uploaded_files = []

    sandbox_provider = get_sandbox_provider()
    sandbox_id = sandbox_provider.acquire(thread_id)
    sandbox = sandbox_provider.get(sandbox_id)

    for file in files:
        if not file.filename:
            continue

        try:
            safe_filename = normalize_filename(file.filename)
        except ValueError:
            logger.warning(f"Skipping file with unsafe filename: {file.filename!r}")
            continue

        try:
            content = await file.read()
            file_path = uploads_dir / safe_filename
            file_path.write_bytes(content)

            virtual_path = upload_virtual_path(safe_filename)

            if sandbox_id != "local":
                sandbox.update_file(virtual_path, content)

            file_info = {
                "filename": safe_filename,
                "size": str(len(content)),
                "path": str(sandbox_uploads / safe_filename),
                "virtual_path": virtual_path,
                "artifact_url": upload_artifact_url(thread_id, safe_filename),
            }

            logger.info(f"Saved file: {safe_filename} ({len(content)} bytes) to {file_info['path']}")

            file_ext = file_path.suffix.lower()
            if file_ext in CONVERTIBLE_EXTENSIONS:
                md_path = await convert_file_to_markdown(file_path)
                if md_path:
                    md_virtual_path = upload_virtual_path(md_path.name)

                    if sandbox_id != "local":
                        sandbox.update_file(md_virtual_path, md_path.read_bytes())

                    file_info["markdown_file"] = md_path.name
                    file_info["markdown_path"] = str(sandbox_uploads / md_path.name)
                    file_info["markdown_virtual_path"] = md_virtual_path
                    file_info["markdown_artifact_url"] = upload_artifact_url(thread_id, md_path.name)

            uploaded_files.append(file_info)

            # ── P2: 视觉管道（受 vision.enabled 开关控制） ──
            file_ext = file_path.suffix.lower()
            vision_cfg = getattr(get_app_config(), "vision", None) or {}
            vision_enabled = vision_cfg.get("enabled", False)

            if file_ext in IMAGE_EXTS and vision_enabled:
                try:
                    from app.gateway.services.vision_gateway import (
                        classify_image,
                        enhance_lab_report,
                        enhance_medical_imaging,
                    )

                    classification = await classify_image(str(file_path))
                    confidence = classification["confidence"]
                    file_info["image_type"] = classification["category"]
                    file_info["image_confidence"] = str(confidence)

                    # 写入分类结果 sidecar 文件，保证多次会话/重载时不丢失类型信息
                    import json
                    meta_path = uploads_dir / f"{safe_filename}.meta.json"
                    meta_path.write_text(json.dumps({
                        "image_type": classification["category"], 
                        "image_confidence": confidence
                    }), encoding="utf-8")

                    outputs_dir = get_paths().sandbox_outputs_dir(thread_id)
                    outputs_dir.mkdir(parents=True, exist_ok=True)
                    enhanced_name = f"enhanced_{safe_filename}"
                    enhanced_host = str(outputs_dir / enhanced_name)

                    if classification["category"] == "lab_report":
                        # 步骤1: 增强（检查文件是否仍存在）
                        if not file_path.exists():
                            logger.warning(f"文件已被删除，跳过增强: {file_path}")
                            continue
                        await asyncio.to_thread(
                            enhance_lab_report, str(file_path), enhanced_host
                        )
                        file_info["enhanced_path"] = f"/mnt/user-data/outputs/{enhanced_name}"

                        # 步骤2: 百度 OCR（使用原始图片，增强版仅供前端展示）
                        from app.gateway.services.baidu_ocr import fetch_medical_report_ocr

                        raw_json = await fetch_medical_report_ocr(str(file_path))
                        logger.info(f"百度 OCR 原始返回 ({safe_filename}): 包含 {len(raw_json.get('Item', raw_json.get('item', [])))} 项" if raw_json else f"百度 OCR 返回 None ({safe_filename})")

                        # 步骤3: JSON → Markdown + 写 sidecar 文件
                        from app.gateway.services.ocr_formatter import format_to_markdown

                        clean_md = format_to_markdown(raw_json or {})
                        sidecar_path = uploads_dir / f"{safe_filename}.ocr.md"
                        sidecar_path.write_text(clean_md, encoding="utf-8")
                        logger.info(f"OCR sidecar 已写入: {sidecar_path}")

                    elif classification["category"] == "medical_imaging":
                        # 步骤1: CLAHE 增强
                        if not file_path.exists():
                            logger.warning(f"文件已被删除，跳过增强: {file_path}")
                            continue
                        await asyncio.to_thread(
                            enhance_medical_imaging, str(file_path), enhanced_host
                        )
                        file_info["enhanced_path"] = f"/mnt/user-data/outputs/{enhanced_name}"

                        # [ADR-021] 步骤2: 置信度 ≥ 0.75 时自动调用 MCP 影像分析
                        if confidence >= 0.75:
                            try:
                                mcp_result = await _call_mcp_analyze(
                                    str(file_path), thread_id, safe_filename
                                )
                                if mcp_result:
                                    file_info["mcp_analysis_status"] = "completed"
                                    # 将发现数量写入供 Agent 快速判断
                                    findings = mcp_result.get("findings", mcp_result.get("summary", {}).get("findings", []))
                                    file_info["mcp_findings_count"] = str(
                                        len(findings) if isinstance(findings, list) 
                                        else mcp_result.get("summary", {}).get("total_findings", 0)
                                    )
                                else:
                                    file_info["mcp_analysis_status"] = "no_result"
                            except Exception as mcp_err:
                                logger.warning(f"[ADR-021] MCP 自动分析失败 ({safe_filename}): {mcp_err}")
                                file_info["mcp_analysis_status"] = "failed"
                        else:
                            # 置信度不足，不自动调用 MCP，让 Agent 自行判断
                            file_info["mcp_analysis_status"] = "skipped_low_confidence"
                            logger.info(
                                f"[ADR-021] 跳过 MCP 自动分析: {safe_filename} "
                                f"(confidence={confidence:.3f} < 0.75)"
                            )

                except Exception as vision_err:
                    logger.error(f"视觉管道处理失败 ({safe_filename}): {vision_err}")
                    # 视觉管道失败不影响上传本身

        except Exception as e:
            logger.error(f"Failed to upload {file.filename}: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to upload {file.filename}: {str(e)}")

    return UploadResponse(
        success=True,
        files=uploaded_files,
        message=f"Successfully uploaded {len(uploaded_files)} file(s)",
    )


@router.get("/list", response_model=dict)
async def list_uploaded_files(thread_id: str) -> dict:
    """List all files in a thread's uploads directory."""
    try:
        uploads_dir = get_uploads_dir(thread_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    result = list_files_in_dir(uploads_dir)
    # 过滤 sidecar 文件，不向前端暴露
    result["files"] = [
        f for f in result["files"] 
        if not f["filename"].endswith(".ocr.md") and not f["filename"].endswith(".meta.json")
    ]
    result["count"] = len(result["files"])
    enrich_file_listing(result, thread_id)

    # Gateway additionally includes the sandbox-relative path.
    sandbox_uploads = get_paths().sandbox_uploads_dir(thread_id)
    for f in result["files"]:
        f["path"] = str(sandbox_uploads / f["filename"])

    return result


@router.delete("/{filename}")
async def delete_uploaded_file(thread_id: str, filename: str) -> dict:
    """Delete a file from a thread's uploads directory."""
    try:
        uploads_dir = get_uploads_dir(thread_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    try:
        result = delete_file_safe(uploads_dir, filename, convertible_extensions=CONVERTIBLE_EXTENSIONS)
        # 清理 sidecar 文件（如果存在）
        sidecar_ocr = uploads_dir / f"{filename}.ocr.md"
        sidecar_ocr.unlink(missing_ok=True)
        sidecar_meta = uploads_dir / f"{filename}.meta.json"
        sidecar_meta.unlink(missing_ok=True)
        return result
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"File not found: {filename}")
    except PathTraversalError:
        raise HTTPException(status_code=400, detail="Invalid path")
    except Exception as e:
        logger.error(f"Failed to delete {filename}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete {filename}: {str(e)}")
