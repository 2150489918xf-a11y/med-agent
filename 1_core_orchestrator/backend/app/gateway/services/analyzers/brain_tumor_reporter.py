import os
import json
import base64
import httpx
from loguru import logger

async def generate_brain_report(spatial_info: dict, slice_png_path: str) -> dict:
    """医生审核确认后，用确认的数据调用硅基流动生成报告。"""
    logger.info("Executing Brain Report Generation")
    
    model_name = os.getenv("SILICONFLOW_VLM_MODEL", "Qwen/Qwen2.5-VL-72B-Instruct")
    api_key = os.getenv("SILICONFLOW_OCR_API_KEY", os.getenv("SILICONFLOW_API_KEY"))
    
    if not api_key:
        logger.warning("No SiliconFlow API key found.")
        return {
            "report_text": "未配置硅基流动 API Key，无法生成报告。",
            "spatial_info": spatial_info,
            "cross_check_passed": False
        }

    img_b64_str = ""
    if slice_png_path and os.path.exists(slice_png_path):
        with open(slice_png_path, "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode()
            img_b64_str = f"data:image/png;base64,{img_b64}"

    sr = spatial_info.get("spatial_relations", {})
    vols = spatial_info.get("volumes", {})
    
    forced_data = (
        f"解剖学定位：病灶主体位于{spatial_info.get('location', '未知')}。\n"
        f"量化特征：增强核心(ET)体积 {vols.get('ET', 0):.1f} cm³，"
        f"周围水肿区(ED)体积 {vols.get('ED', 0):.1f} cm³，"
        f"坏死核心(NCR)体积 {vols.get('NCR', 0):.1f} cm³，"
        f"全肿瘤(WT)体积 {vols.get('WT', 0):.1f} cm³。\n"
        f"空间关系：{'肿瘤跨越中线' if sr.get('crosses_midline', False) else '肿瘤未跨越中线'}，"
        f"中线偏移 {sr.get('midline_shift_mm', 0):.1f} mm，"
        f"距脑干最近距离 {sr.get('brainstem_min_dist_mm', 0):.1f} mm，"
        f"同侧/对侧脑室体积比 {sr.get('ventricle_compression_ratio', 1.0):.2f}"
        f"{'（提示脑室受压）' if sr.get('ventricle_compression_ratio', 1.0) < 0.8 else ''}。"
    )

    prompt = f"""【系统设定】
你是一名顶尖的神经影像科医生。请根据我提供的[系统强制前置数据]与[病灶最大截面图]，
撰写一份专业的脑肿瘤 MRI 报告。

【系统强制前置数据（由底层 3D 算法精密计算得出，请作为绝对事实直接引用，禁止篡改！）】
{forced_data}

【你的任务】
1. 无条件采用上述位置、体积和空间关系描述
2. 观察附件图片，描述病灶形态特征（形状、边缘、强化均匀性、囊变坏死、占位效应）
3. 结合空间关系数据，评估占位效应严重程度和手术风险提示
4. 按"部位-大小-形态-信号特征-空间关系-周边情况-影像学印象"格式用Markdown输出

【输出格式要求】
请严格返回 JSON 格式，包含 cross_check 和 report 两个字段。
必须输出可解析的 JSON，不要 Markdown 代码块包裹。
{{
  "cross_check": {{
    "loc": "<引用的解剖位置>",
    "vol_et": <数字>,
    "vol_ed": <数字>,
    "crosses_midline": <布尔值>,
    "brainstem_dist": <数字>
  }},
  "report": "..."
}}"""

    content_list = [{"type": "text", "text": prompt}]
    if img_b64_str:
        content_list.append({"type": "image_url", "image_url": {"url": img_b64_str}})

    payload = {
        "model": model_name,
        "messages": [{
            "role": "user",
            "content": content_list
        }],
        "max_tokens": 2048,
        "response_format": {"type": "json_object"}
    }

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                "https://api.siliconflow.cn/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json=payload,
            )
            resp.raise_for_status()
            
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        
        if content.startswith("```json"):
            content = content.replace("```json", "").replace("```", "").strip()
        elif content.startswith("```"):
            content = content.replace("```", "").strip()
            
        raw_output = json.loads(content)
        
        cross = raw_output.get("cross_check", {})
        passed = True
        
        if cross.get("loc") != spatial_info.get("location"):
            logger.warning(f"[BrainReport] LLM 篡改了位置！强制覆盖。")
            passed = False
        if abs(cross.get("vol_et", 0) - vols.get("ET", 0)) > 0.5:
            logger.warning(f"[BrainReport] LLM 篡改了 ET 体积！强制覆盖。")
            passed = False
            
        if cross.get("crosses_midline") != sr.get("crosses_midline"):
            logger.warning(f"[BrainReport] LLM 篡改了跨中线判定！强制覆盖。")
            passed = False
        if abs(cross.get("brainstem_dist", 0) - sr.get("brainstem_min_dist_mm", 0)) > 2.0:
            logger.warning(f"[BrainReport] LLM 篡改了脑干距离！强制覆盖。")
            passed = False

        if spatial_info.get("is_mock_fallback"):
            report_text = "[WARNING: 无可用模型环境，当前报告与空间数据基于 Mock 测试生成]\n\n" + raw_output.get("report", "")
        else:
            report_text = raw_output.get("report", "生成失败")

        return {
            "report_text": report_text,
            "spatial_info": spatial_info,
            "cross_check_passed": passed,
        }
    except Exception as e:
        logger.error(f"Error calling SiliconFlow API: {e}")
        return {
            "report_text": f"报告生成失败：{str(e)}\n\n{forced_data}",
            "spatial_info": spatial_info,
            "cross_check_passed": False
        }
