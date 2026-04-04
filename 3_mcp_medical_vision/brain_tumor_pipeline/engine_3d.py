import os
import json
import base64
from loguru import logger
from typing import Dict, Any, Optional
import httpx
import numpy as np
import nibabel as nib
from pathlib import Path
from scipy.ndimage import distance_transform_edt, binary_erosion

# TODO: Update these paths when atlases and models are downloaded
ATLAS_DIR = Path(__file__).parent / "resources" / "atlases"
AAL_ATLAS_PATH = ATLAS_DIR / "AAL3" / "AAL3v1_1mm.nii.gz"
AAL_LABELS_PATH = ATLAS_DIR / "aal_labels.json"
NNUNET_MODEL_DIR = Path(__file__).parent / "models" / "nnunet_brats" / "nnUNetTrainer__nnUNetPlans__3d_fullres"

# AAL3 Brainstem Labels (Vermis, Pons, Midbrain, Medulla etc)
BRAINSTEM_LABELS = [71, 72, 73, 74, 75, 76]

# AAL3 Ventricle Labels 
VENTRICLE_L_LABELS = [121] 
VENTRICLE_R_LABELS = [122]

import asyncio

async def run_pipeline(nifti_dir: str, original_filename: str) -> dict:
    """上传后自动执行 Step 1-4，产出空间数据和报告供返回。"""
    logger.info(f"Starting brain MRI analysis pipeline for {nifti_dir}")
    nifti_path = Path(nifti_dir)
    
    # Check if we have a single .nii.gz file or a directory
    if nifti_path.is_file() and str(nifti_path).endswith('.nii.gz'):
        logger.warning("Single NIfTI file uploaded. Expecting a directory with multiple sequences.")
        t1ce_path = str(nifti_path)
        t1_path = str(nifti_path)
        flair_path = str(nifti_path)
        dir_path = str(nifti_path.parent)
    else:
        dir_path = str(nifti_path)
        t1ce_path = os.path.join(dir_path, "t1ce.nii.gz")
        t1_path = os.path.join(dir_path, "t1.nii.gz")
        flair_path = os.path.join(dir_path, "flair.nii.gz")
        
        if not os.path.exists(t1ce_path):
            found_t1ce = _find_file(dir_path, "t1ce") or _find_file(dir_path, "t1")
            if found_t1ce:
                t1ce_path = found_t1ce
            
    # Step 1: nnU-Net 3D 分割
    import time
    step1_start = time.time()
    tumor_mask, is_mask_mock = await asyncio.to_thread(step1_segment, dir_path)
    
    # --- 优雅降级 (Graceful Degradation) ---
    img = nib.load(t1ce_path) if t1ce_path and os.path.exists(t1ce_path) else None
    clinical_warning = None
    
    if img:
        spacing = img.header.get_zooms()[:3]
        voxel_vol = spacing[0] * spacing[1] * spacing[2]
        total_volume_cm3 = float(np.sum(tumor_mask > 0) * voxel_vol / 1000)
        
        logger.info("brain_pipeline_step_completed", extra={
            "step": "step1_nnunet",
            "duration_ms": int((time.time() - step1_start) * 1000),
            "wt_volume_cm3": total_volume_cm3
        })
        
        if total_volume_cm3 < 0.5:
            logger.info("brain_pipeline_warning", extra={"reason": "volume_too_small", "vol": total_volume_cm3})
            clinical_warning = "体积极小异常 (总体积 < 0.5 cm³)，系统将尝试定位并绘制 2D 贴图。有假阳性噪点或早期微小占位可能，请医师严审图谱辅助诊断！"

    # Step 2: 空间计算
    is_spatial_mock = False
    step2_start = time.time()
    try:
        spatial_info = await asyncio.to_thread(step2_localize, t1ce_path, t1_path, tumor_mask)
        logger.info("brain_pipeline_step_completed", extra={
            "step": "step2_localize",
            "duration_ms": int((time.time() - step2_start) * 1000)
        })
    except Exception as e:
        logger.error(f"Error in spatial localization: {e}")
        is_spatial_mock = True
        spatial_info = _mock_spatial_info()

    if "是" in spatial_info.get("location", "") and "失败" in spatial_info.get("location", ""):
        # Detected mock string
        is_spatial_mock = True
        
    if 'clinical_warning' in locals() and clinical_warning:
        spatial_info["clinical_warning"] = clinical_warning

    spatial_info["is_mock_fallback"] = is_mask_mock or is_spatial_mock

    # Step 3: 2D 渲染
    try:
        slice_png_path = await asyncio.to_thread(step3_render, t1ce_path, flair_path, tumor_mask, spatial_info, dir_path)
    except Exception as e:
        logger.error(f"Error in 2D rendering: {e}")
        slice_png_path = ""

    has_abnormal = spatial_info.get("volumes", {}).get("WT", 0) > 0

    return {
        "status": "completed",
        "spatial_info": spatial_info,
        "slice_png_path": slice_png_path,
        "is_abnormal": has_abnormal,
        "is_mock_fallback": is_mask_mock or is_spatial_mock
    }

def _find_file(directory: str, keyword: str) -> Optional[str]:
    for f in os.listdir(directory):
        if keyword.lower() in f.lower() and (f.endswith('.nii') or f.endswith('.nii.gz')):
            return os.path.join(directory, f)
    return None

def step1_segment(nifti_dir: str) -> tuple[np.ndarray, bool]:
    """调用 nnU-Net v2 预训练模型进行 3D 分割。返回 (mask, is_mock)"""
    logger.info("Executing Step 1: nnU-Net 3D Segmentation")
    try:
        from nnunetv2.inference.predict_from_raw_data import nnUNetPredictor
        logger.warning("nnU-Net prediction not fully implemented yet, returning mock mask")
        is_mock = True
        
        t1c_path = os.path.join(nifti_dir, "t1ce.nii.gz")
        if not os.path.exists(t1c_path):
            t1c_path = _find_file(nifti_dir, "t1c") or _find_file(nifti_dir, "t1")
            
        if t1c_path and os.path.exists(t1c_path):
            img = nib.load(t1c_path)
            shape = img.shape
            mask = np.zeros(shape, dtype=np.uint8)
            cx, cy, cz = shape[0]//2, shape[1]//2, shape[2]//2
            r = shape[0]//10
            
            y, x, z = np.ogrid[-cx:shape[0]-cx, -cy:shape[1]-cy, -cz:shape[2]-cz]
            mask[x**2 + y**2 + z**2 <= (r*1.5)**2] = 2
            mask[x**2 + y**2 + z**2 <= r**2] = 4
            mask[x**2 + y**2 + z**2 <= (r*0.5)**2] = 1
            return mask, is_mock
        else:
            return np.zeros((100, 100, 100), dtype=np.uint8), is_mock
            
    except ImportError:
        logger.warning("nnunetv2 not installed, returning mock mask")
        return np.zeros((100, 100, 100), dtype=np.uint8), True

def step2_localize(t1ce_path: str, t1_path: str, tumor_mask: np.ndarray) -> dict:
    logger.info("Executing Step 2: Spatial Localization")
    
    if not t1ce_path or not os.path.exists(t1ce_path):
        logger.warning("t1ce_path not found or invalid, returning mock")
        return _mock_spatial_info()

    try:
        import ants
    except ImportError:
        logger.warning("antspyx not installed, returning basic volume info only")
        img = nib.load(t1ce_path)
        spacing = img.header.get_zooms()[:3]
        voxel_vol = spacing[0] * spacing[1] * spacing[2]
        
        return {
            "volumes": {
                "ET": float(np.sum(tumor_mask == 4) * voxel_vol / 1000),
                "ED": float(np.sum(tumor_mask == 2) * voxel_vol / 1000),
                "NCR": float(np.sum(tumor_mask == 1) * voxel_vol / 1000),
                "WT": float(np.sum(tumor_mask > 0) * voxel_vol / 1000),
            },
            "location": "定位失败 (缺少 antspyx 依赖，使用 Mock)",
            "regions": [],
            "spatial_relations": {
                "crosses_midline": False,
                "midline_shift_mm": 0.0,
                "brainstem_min_dist_mm": 0.0,
                "ventricle_compression_ratio": 1.0,
            }
        }

    img = nib.load(t1ce_path)
    spacing = img.header.get_zooms()[:3]
    voxel_vol = spacing[0] * spacing[1] * spacing[2]
    volumes = {
        "ET": float(np.sum(np.isin(tumor_mask, [3, 4])) * voxel_vol / 1000),
        "ED": float(np.sum(tumor_mask == 2) * voxel_vol / 1000),
        "NCR": float(np.sum(tumor_mask == 1) * voxel_vol / 1000),
        "WT": float(np.sum(tumor_mask > 0) * voxel_vol / 1000),
    }
    
    if volumes["WT"] == 0:
        return {
            "volumes": volumes,
            "location": "未见明显异常占位",
            "regions": [],
            "spatial_relations": {
                "crosses_midline": False,
                "midline_shift_mm": 0.0,
                "brainstem_min_dist_mm": 99.0,
                "ventricle_compression_ratio": 1.0,
            }
        }

    try:
        t1_ants = ants.image_read(t1_path)
        mni_template = ants.image_read(ants.get_ants_data("mni"))
        
        reg = ants.registration(mni_template, t1_ants, type_of_transform="Affine")

        tumor_ants = ants.from_numpy(tumor_mask.astype(float), origin=t1_ants.origin, spacing=t1_ants.spacing, direction=t1_ants.direction)
        tumor_mni = ants.apply_transforms(
            mni_template, tumor_ants,
            transformlist=reg["fwdtransforms"],
            interpolator="nearestNeighbor"
        )
        tumor_mni_data = tumor_mni.numpy()

        aal_labels_map = {}
        if os.path.exists(AAL_LABELS_PATH):
            with open(AAL_LABELS_PATH, 'r', encoding='utf-8') as f:
                aal_labels_map = json.load(f)

        if os.path.exists(AAL_ATLAS_PATH):
            aal_atlas = ants.image_read(str(AAL_ATLAS_PATH))
            aal_data = aal_atlas.numpy()
            regions = _compute_overlap(tumor_mni_data, aal_data, aal_labels_map)
        else:
            logger.warning(f"AAL atlas not found at {AAL_ATLAS_PATH}")
            aal_data = np.zeros_like(tumor_mni_data)
            regions = []

        mni_spacing = mni_template.spacing

        tumor_coords = np.argwhere(tumor_mni_data > 0)
        mni_origin = mni_template.origin
        midline_voxel_x = int(abs(mni_origin[0]) / mni_spacing[0])
        
        min_x = tumor_coords[:, 0].min()
        max_x = tumor_coords[:, 0].max()
        crosses_midline = bool(min_x < midline_voxel_x < max_x)

        tumor_centroid_x = float(tumor_coords[:, 0].mean())
        midline_shift_mm = abs(tumor_centroid_x - midline_voxel_x) * mni_spacing[0]

        if "aal_data" in locals() and aal_data.any():
            brainstem_mask = np.isin(aal_data, BRAINSTEM_LABELS)
            brainstem_min_dist_mm = _compute_min_surface_distance(
                tumor_mni_data > 0, brainstem_mask, mni_spacing
            )
            
            tumor_side = "L" if tumor_centroid_x < midline_voxel_x else "R"
            ipsi_labels = VENTRICLE_L_LABELS if tumor_side == "L" else VENTRICLE_R_LABELS
            contra_labels = VENTRICLE_R_LABELS if tumor_side == "L" else VENTRICLE_L_LABELS
            
            ipsi_vol = float(np.isin(aal_data, ipsi_labels).sum())
            contra_vol = float(np.isin(aal_data, contra_labels).sum())
            ventricle_ratio = round(ipsi_vol / max(contra_vol, 1.0), 2)
        else:
            brainstem_min_dist_mm = 0.0
            ventricle_ratio = 1.0

        spatial_relations = {
            "crosses_midline": crosses_midline,
            "midline_shift_mm": round(midline_shift_mm, 1),
            "brainstem_min_dist_mm": round(brainstem_min_dist_mm, 1),
            "ventricle_compression_ratio": ventricle_ratio,
        }

        return {
            "volumes": volumes,
            "location": _format_location_text(regions),
            "regions": regions,
            "spatial_relations": spatial_relations,
        }
    except Exception as e:
        logger.error(f"Error in ANTs processing: {e}")
        return _mock_spatial_info(volumes)

def _mock_spatial_info(volumes=None):
    if not volumes:
        volumes = {"ET": 0, "ED": 0, "NCR": 0, "WT": 0}
    return {
        "volumes": volumes,
        "location": "计算失败(配准异常，使用 Mock)",
        "regions": [],
        "spatial_relations": {
            "crosses_midline": False,
            "midline_shift_mm": 0.0,
            "brainstem_min_dist_mm": 0.0,
            "ventricle_compression_ratio": 1.0,
        }
    }

def _compute_overlap(tumor_mask: np.ndarray, atlas_data: np.ndarray, labels_map: dict) -> list:
    tumor_voxels = np.sum(tumor_mask > 0)
    if tumor_voxels == 0:
        return []
        
    overlap_counts = {}
    tumor_indices = tumor_mask > 0
    atlas_in_tumor = atlas_data[tumor_indices]
    
    unique_labels, counts = np.unique(atlas_in_tumor, return_counts=True)
    
    regions = []
    for label, count in zip(unique_labels, counts):
        if label == 0:
            continue
        pct = (count / tumor_voxels) * 100
        if pct > 1.0:
            label_str = str(int(label))
            name = labels_map.get(label_str, f"Region {label}")
            regions.append({
                "label_id": int(label),
                "name": name,
                "overlap_pct": round(pct, 1)
            })
            
    regions.sort(key=lambda x: x["overlap_pct"], reverse=True)
    return regions

def _format_location_text(regions: list) -> str:
    if not regions:
        return "未能确定明确脑区"
    
    parts = []
    for r in regions[:3]:
        parts.append(f"{r['name']}({r['overlap_pct']}%)")
    return ", ".join(parts)

def _compute_min_surface_distance(mask_a: np.ndarray, mask_b: np.ndarray, spacing: tuple) -> float:
    if not mask_a.any() or not mask_b.any():
        return 999.0
        
    dist_from_b = distance_transform_edt(~mask_b, sampling=spacing)
    surface_a = mask_a & ~binary_erosion(mask_a)
    if not surface_a.any():
        surface_a = mask_a
        
    return float(dist_from_b[surface_a].min())

def step3_render(t1ce_path: str, flair_path: str, tumor_mask: np.ndarray, spatial_info: dict, output_dir: str) -> str:
    logger.info("Executing Step 3: 2D Rendering")
    if not t1ce_path or not os.path.exists(t1ce_path):
        return ""

    try:
        import cv2
    except ImportError:
        logger.warning("cv2 not installed, cannot render 2D slices")
        return ""

    areas = [np.sum(tumor_mask[:, :, z] > 0) for z in range(tumor_mask.shape[2])]
    if not any(areas):
        return ""
        
    best_z = int(np.argmax(areas))

    t1ce_img = nib.load(t1ce_path)
    t1ce_slice = t1ce_img.get_fdata()[:, :, best_z]
    
    def normalize(slice_data):
        slice_data = np.nan_to_num(slice_data)
        min_val, max_val = slice_data.min(), slice_data.max()
        if max_val > min_val:
            return ((slice_data - min_val) / (max_val - min_val) * 255).astype(np.uint8)
        return np.zeros_like(slice_data, dtype=np.uint8)
        
    t1ce_slice_uint8 = normalize(t1ce_slice)
    
    t1ce_color = cv2.applyColorMap(t1ce_slice_uint8, cv2.COLORMAP_BONE)

    mask_slice = tumor_mask[:, :, best_z]
    
    et_mask = (np.isin(mask_slice, [3, 4])).astype(np.uint8)
    contours_et, _ = cv2.findContours(et_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cv2.drawContours(t1ce_color, contours_et, -1, (0, 0, 255), 1)
    
    ed_mask = (mask_slice == 2).astype(np.uint8)
    contours_ed, _ = cv2.findContours(ed_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cv2.drawContours(t1ce_color, contours_ed, -1, (255, 0, 0), 1)

    ncr_mask = (mask_slice == 1).astype(np.uint8)
    contours_ncr, _ = cv2.findContours(ncr_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cv2.drawContours(t1ce_color, contours_ncr, -1, (0, 255, 255), 1)
    
    flair_color = None
    if flair_path and os.path.exists(flair_path):
        try:
            flair_img = nib.load(flair_path)
            flair_slice = flair_img.get_fdata()[:, :, best_z]
            flair_slice_uint8 = normalize(flair_slice)
            flair_color = cv2.applyColorMap(flair_slice_uint8, cv2.COLORMAP_BONE)
            cv2.drawContours(flair_color, contours_ed, -1, (255, 0, 0), 1)
        except Exception:
            pass
            
    h, w = t1ce_color.shape[:2]
    t1ce_color = np.rot90(t1ce_color, 1)
    
    cv2.putText(t1ce_color, "R", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2)
    cv2.putText(t1ce_color, "L", (w - 30, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2)

    if flair_color is not None:
        flair_color = np.rot90(flair_color, 1)
        cv2.putText(flair_color, "R", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2)
        cv2.putText(flair_color, "L", (w - 30, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2)
        combined = np.hstack([t1ce_color, flair_color])
    else:
        combined = t1ce_color
        
    output_path = os.path.join(output_dir, f"brain_slice_z{best_z}.png")
    cv2.imwrite(output_path, combined)
    return output_path


