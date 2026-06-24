import requests
import base64
import os
import time
import json
import sys
import io
import uuid
import random
import re
from urllib.parse import quote
from PIL import Image, ImageOps

# 解决路径问题
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
import utils


# =================================================================
# 辅助方法：图片处理与 Base64 编码
# =================================================================

def get_mime_type(image_path):
    """根据文件后缀自动检测 mime_type"""
    ext = str(image_path).lower()
    if ext.endswith('.png'):
        return "image/png"
    elif ext.endswith(('.jpg', '.jpeg')):
        return "image/jpeg"
    elif ext.endswith('.webp'):
        return "image/webp"
    return "image/jpeg"  # 默认 fallback


def encode_image_to_base64(image_path):
    """读取图片并转换为 base64 字符串"""
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def _get_resample_filter():
    try:
        return Image.Resampling.LANCZOS
    except AttributeError:
        return Image.LANCZOS


def _flatten_to_rgb(image):
    if image.mode in ("RGBA", "LA"):
        background = Image.new("RGB", image.size, (255, 255, 255))
        alpha = image.getchannel("A")
        background.paste(image.convert("RGBA"), mask=alpha)
        return background
    if image.mode == "P":
        return _flatten_to_rgb(image.convert("RGBA"))
    if image.mode != "RGB":
        return image.convert("RGB")
    return image


def encode_image_to_base64_for_api(image_path):
    """
    发给接口前默认做一次预压缩，避免超大参考图导致请求体过大或接口崩溃。
    返回 (base64_data, mime_type)。
    """
    max_side = int(getattr(config, "API_UPLOAD_MAX_SIDE", 1600))
    max_bytes = int(getattr(config, "API_UPLOAD_MAX_BYTES", 1024 * 1024))
    resample_filter = _get_resample_filter()

    try:
        with Image.open(image_path) as pil_img:
            image = ImageOps.exif_transpose(pil_img)
            image.load()

        width, height = image.size
        if max(width, height) > max_side:
            image.thumbnail((max_side, max_side), resample_filter)

        image = _flatten_to_rgb(image)

        original_size = os.path.getsize(image_path)
        original_mime = get_mime_type(image_path)
        if original_size <= max_bytes and max(width, height) <= max_side and image.mode == "RGB":
            with open(image_path, "rb") as f:
                return base64.b64encode(f.read()).decode("utf-8"), original_mime

        for quality in (92, 88, 84, 80, 76, 72, 68, 64, 60, 55, 50):
            buffer = io.BytesIO()
            image.save(buffer, format="JPEG", quality=quality, optimize=True)
            data = buffer.getvalue()
            if len(data) <= max_bytes or quality == 50:
                return base64.b64encode(data).decode("utf-8"), "image/jpeg"
    except Exception:
        pass

    return encode_image_to_base64(image_path), get_mime_type(image_path)


def _build_image_parts(source_img_path):
    """
    统一处理单图或多图，生成 Google 原生 API 需要的 inline_data parts 列表
    """
    parts = []
    # 如果是多图数组 (List)
    if isinstance(source_img_path, list):
        for path in source_img_path:
            img_b64, mime = encode_image_to_base64_for_api(path)
            parts.append({
                "inline_data": {
                    "mime_type": mime,
                    "data": img_b64
                }
            })
    # 如果是单张图片 (String)
    elif source_img_path and isinstance(source_img_path, str):
        img_b64, mime = encode_image_to_base64_for_api(source_img_path)
        parts.append({
            "inline_data": {
                "mime_type": mime,
                "data": img_b64
            }
        })
    return parts


def _build_chat_image_content(source_img_path):
    content = []
    if isinstance(source_img_path, list):
        paths = source_img_path
    elif source_img_path and isinstance(source_img_path, str):
        paths = [source_img_path]
    else:
        paths = []

    for path in paths:
        img_b64, mime = encode_image_to_base64_for_api(path)
        content.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:{mime};base64,{img_b64}"
            }
        })
    return content


def _normalize_source_paths(source_img_path):
    if isinstance(source_img_path, list):
        return list(source_img_path)
    if source_img_path and isinstance(source_img_path, str):
        return [source_img_path]
    return []


def _build_openai_images_input(source_img_path):
    image_inputs = []
    for path in _normalize_source_paths(source_img_path):
        if isinstance(path, str) and (path.startswith("http://") or path.startswith("https://") or path.startswith("data:")):
            image_inputs.append(path)
            continue

        img_b64, mime = encode_image_to_base64_for_api(path)
        image_inputs.append(f"data:{mime};base64,{img_b64}")

    if not image_inputs:
        return None
    if len(image_inputs) == 1:
        return image_inputs[0]
    return image_inputs


def _build_data_url_from_path(image_path):
    img_b64, mime = encode_image_to_base64_for_api(image_path)
    return f"data:{mime};base64,{img_b64}"


def _build_multipart_image_files(source_img_path):
    files = []
    handles = []
    for path in _normalize_source_paths(source_img_path):
        file_handle = open(path, "rb")
        handles.append(file_handle)
        files.append(("image[]", (os.path.basename(path), file_handle, get_mime_type(path))))
    return files, handles




def _ratio_to_nano_banana_size(ratio, image_size):
    ratio_text = str(ratio or '1:1').strip().replace(':', 'x').lower()
    size_text = str(image_size or '1K').strip().upper()
    if size_text == '2K':
        return f"{ratio_text}-2k"
    return ratio_text

def _build_explicit_size_from_ratio(ratio, image_size):
    resolution_to_side = {
        "1K": 1024,
        "2K": 2048,
        "3K": 3072,
        "4K": 4096,
    }
    long_side = resolution_to_side.get(str(image_size).upper())
    if not long_side or not ratio or ":" not in str(ratio):
        return image_size

    try:
        width_ratio, height_ratio = [int(part) for part in str(ratio).split(":", 1)]
    except (TypeError, ValueError):
        return image_size

    if width_ratio <= 0 or height_ratio <= 0:
        return image_size

    if width_ratio >= height_ratio:
        width = long_side
        height = max(1, int(round(long_side * height_ratio / width_ratio)))
    else:
        height = long_side
        width = max(1, int(round(long_side * width_ratio / height_ratio)))

    return f"{width}x{height}"


def _extract_markdown_image_urls(text):
    if not text:
        return []
    return re.findall(r'!\[.*?\]\((https?://[^)]+)\)', text)


def _extract_task_id(payload):
    if not isinstance(payload, dict):
        return None
    return payload.get("task_id") or payload.get("id") or payload.get("taskId")


def _extract_task_poll_url(payload, model_config):
    if not isinstance(payload, dict):
        return None
    poll_url = payload.get("poll_url") or payload.get("detail_url")
    if poll_url:
        return poll_url
    task_id = _extract_task_id(payload)
    if not task_id:
        return None
    base_url = str(model_config.get("task_base_url") or "").rstrip("/")
    if base_url:
        return f"{base_url}/api/tasks/{task_id}"
    return None


def _extract_task_image_url(payload):
    if not isinstance(payload, dict):
        return None

    for key in ("download_url", "result_url", "image_url", "url", "detail_url"):
        value = payload.get(key)
        if isinstance(value, str) and value.startswith(("http://", "https://")):
            return value

    data = payload.get("data")
    if isinstance(data, dict):
        for key in ("image_url", "download_url", "result_url", "url"):
            value = data.get(key)
            if isinstance(value, str) and value.startswith(("http://", "https://")):
                return value
        image_urls = data.get("image_urls")
        if isinstance(image_urls, list) and image_urls:
            first_url = image_urls[0]
            if isinstance(first_url, str) and first_url.startswith(("http://", "https://")):
                return first_url

    result = payload.get("result")
    if isinstance(result, dict):
        for key in ("image_url", "download_url", "result_url", "url"):
            value = result.get(key)
            if isinstance(value, str) and value.startswith(("http://", "https://")):
                return value

    return None


def _normalize_task_status(payload):
    if not isinstance(payload, dict):
        return ""
    return str(payload.get("status") or payload.get("state") or "").strip().lower()


def _extract_response_error_message(response):
    try:
        payload = response.json()
    except Exception:
        return response.text

    if isinstance(payload, dict):
        error_obj = payload.get("error")
        if isinstance(error_obj, dict) and error_obj.get("message"):
            return error_obj["message"]
        if payload.get("message"):
            return payload["message"]
        if payload.get("code") and payload.get("message"):
            return f"{payload['code']}: {payload['message']}"
    return response.text


def _save_image_from_url(image_url, save_directory, file_prefix, compress_enabled=False, compress_target=2.0):
    if not os.path.exists(save_directory):
        os.makedirs(save_directory)

    response = requests.get(image_url, timeout=120)
    response.raise_for_status()

    unique_suffix = f"{int(time.time() * 1000)}_{uuid.uuid4().hex[:8]}"
    output_file = os.path.join(save_directory, f"{file_prefix}_{unique_suffix}.png")

    with open(output_file, "wb") as f:
        f.write(response.content)

    if compress_enabled:
        utils.compress_image_smart(output_file, compress_target, output_file)

    return output_file


def _save_image_from_base64_payload(image_payload, save_directory, file_prefix, compress_enabled=False, compress_target=2.0):
    if not os.path.exists(save_directory):
        os.makedirs(save_directory)

    payload = (image_payload or "").strip()
    if not payload:
        raise ValueError("Empty base64 image payload")

    if payload.startswith("data:") and "," in payload:
        payload = payload.split(",", 1)[1]

    unique_suffix = f"{int(time.time() * 1000)}_{uuid.uuid4().hex[:8]}"
    output_file = os.path.join(save_directory, f"{file_prefix}_{unique_suffix}.png")

    with open(output_file, "wb") as f:
        f.write(base64.b64decode(payload))

    if compress_enabled:
        utils.compress_image_smart(output_file, compress_target, output_file)

    return output_file


# =================================================================
# 核心功能 1：AI 生成图片 (支持原生多图传入)
# =================================================================

def api_generate_image(prompt, key, ratio, source_img_path, save_directory, file_prefix="img", compress_enabled=False,
                       compress_target=2.0, image_size="1K", api_url=None):
    """
    调用生图大模型，支持将多图数组直接喂给底层作为参考特征
    """
    url = api_url if api_url else getattr(config, "IMG_API_URL",
                  "https://api.apiyi.com/v1beta/models/gemini-3.1-flash-image-preview:generateContent")

    # 1. 组装 parts
    parts = _build_image_parts(source_img_path)
    parts.append({"text": prompt})

    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json"
    }

    payload = {
        "contents": [{"parts": parts}],
        "generationConfig": {
            "responseModalities": ["IMAGE"],
            "imageConfig": {
                "aspectRatio": ratio,
                "imageSize": image_size
            }
        }
    }

    request_timeout = int(getattr(config, "IMAGE_GEN_TIMEOUT", 300))
    max_retries = max(1, int(getattr(config, "IMG_API_MAX_RETRIES", 3)))
    retry_base_delay = float(getattr(config, "IMG_API_RETRY_BASE_DELAY", 2.0))

    try:
        result = None
        last_error = None

        for attempt in range(1, max_retries + 1):
            try:
                response = requests.post(url, headers=headers, json=payload, timeout=request_timeout)

                if response.status_code != 200:
                    err_msg = response.text
                    try:
                        err_msg = response.json().get("error", {}).get("message", response.text)
                    except:
                        pass

                    retriable_status = response.status_code in (408, 409, 425, 429, 500, 502, 503, 504)
                    if retriable_status and attempt < max_retries:
                        sleep_seconds = retry_base_delay * (2 ** (attempt - 1)) + random.uniform(0, 0.5)
                        time.sleep(sleep_seconds)
                        continue
                    raise Exception(f"API 响应错误 ({response.status_code}): {err_msg}")

                result = response.json()
                break
            except requests.exceptions.RequestException as exc:
                last_error = exc
                if attempt >= max_retries:
                    raise
                sleep_seconds = retry_base_delay * (2 ** (attempt - 1)) + random.uniform(0, 0.5)
                time.sleep(sleep_seconds)

        if result is None:
            raise last_error or Exception("生图接口未返回有效结果。")

        # 解析返回的 base64
        candidate = result.get("candidates", [{}])[0]
        parts_resp = candidate.get("content", {}).get("parts", [{}])[0]

        if "inlineData" in parts_resp:
            image_data = parts_resp["inlineData"]["data"]
        elif "inline_data" in parts_resp:
            image_data = parts_resp["inline_data"]["data"]
        else:
            raise Exception("API 返回的数据中未找到图片内容。")

        # 保存图片至本地
        if not os.path.exists(save_directory):
            os.makedirs(save_directory)

        unique_suffix = f"{int(time.time() * 1000)}_{uuid.uuid4().hex[:8]}"
        output_file = os.path.join(save_directory, f"{file_prefix}_{unique_suffix}.png")

        with open(output_file, 'wb') as f:
            f.write(base64.b64decode(image_data))

        # 智能压缩
        if compress_enabled:
            utils.compress_image_smart(output_file, compress_target, output_file)

        return output_file

    except Exception as e:
        raise Exception(f"生图请求失败: {e}")


# =================================================================
# 核心功能 2：LLM 文本/视觉 大模型调用 (分析风格 / 生成 Prompt)
# =================================================================

def _call_llm_api(api_key, parts):
    """底层的文本/视觉 LLM 请求包装器"""
    url = getattr(config, "LLM_API_URL", "https://api.apiyi.com/v1beta/models/gemini-2.5-pro:generateContent")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    payload = {
        "contents": [{"parts": parts}]
    }

    response = requests.post(url, headers=headers, json=payload, timeout=120)
    if response.status_code != 200:
        raise Exception(f"LLM 请求失败: {response.text}")

    result = response.json()
    try:
        text = result["candidates"][0]["content"]["parts"][0]["text"]
        return text
    except KeyError:
        raise Exception(f"LLM 返回格式解析失败: {result}")


def _parse_json_response(text_resp, fallback=None):
    clean_text = text_resp.replace('```json', '').replace('```', '').strip()
    try:
        return json.loads(clean_text)
    except Exception:
        return fallback


def api_analyze_style(api_key, image_path, style_list):
    """让 AI 分析图片风格 (已原样恢复原版的 alternatives 备选规则)"""
    parts = _build_image_parts(image_path)
    style_list_str = json.dumps(style_list, ensure_ascii=False, indent=2)

    prompt = f"""
    You are an expert E-commerce Art Director. 
    Analyze the uploaded product image. Identify the product category, material, and target audience.
    Here is the list of available styles:
    {style_list_str}
    Task:
    1. Select the ONE BEST style that maximizes sales conversion.
    2. Select 2 ALTERNATIVE styles that would also work well.
    3. Provide a short reason for your choice.
    Output: Strict JSON:
    {{ "best_style": "Exact Key", "alternatives": ["Key2", "Key3"], "reasoning": "text" }}
    """
    parts.append({"text": prompt})

    text_resp = _call_llm_api(api_key, parts)

    parsed = _parse_json_response(text_resp)
    if parsed is not None:
        return parsed
    else:
        return {"best_style": style_list[0] if style_list else "", "reasoning": "解析失败，使用默认"}


def api_generate_prompts(api_key, image_path, template_name, raw_template, style_name, style_desc, extra_info):
    """根据模板生成批量 Prompt (已完美恢复 A+ / LISTING 的强大排版指令)"""
    parts = _build_image_parts(image_path)

    core_template_instructions = raw_template.replace("{style}", "[DYNAMIC STYLE SEE BELOW]")

    if "A+" in template_name:
        dynamic_text_rules = """
        **⚠️ CRITICAL TEXT RULES (A+ MODE - STRICT):**
        1. **MANDATORY SUBTITLES:** Every image MUST have a Title AND a Subtitle. No exceptions.
        2. **RICH SUBTITLES:** Subtitle MUST be a complete phrase (3-6 words) explaining the benefit.
        3. **HIERARCHY:** Title is Big/Bold. Subtitle is Smaller but DESCRIPTIVE.
        """
    else:
        dynamic_text_rules = """
        **⚠️ TEXT RULES (LISTING MODE - FLEXIBLE):**
        1. **RESPECT 'NO TEXT':** If a Slot says "NO TEXT", you must generate purely visual prompts with NO text description.
        2. **MINIMALISM:** For feature shots, use short, punchy labels (1-3 words). No long subtitles needed.
        3. **CLARITY:** Text should be functional and informative, not just decorative.
        """

    final_prompt = f"""
    # =================================================================
    # 🧠 PART 1: ART DIRECTOR DECISION (INTERNAL THOUGHT)
    # =================================================================
    1. **Analyze** the Product Image and Selected Style.
    2. **Select ONE Font** from this Safe List:
       - Luxury/Feminine: "Didot", "Bodoni", "Playfair Display"
       - Tech/Sport: "Futura", "Helvetica Neue", "Roboto"
       - Retro/Cozy: "Garamond", "Cooper Black"
    3. **Translation:** Translate User Input ({extra_info}) into professional English marketing copy.

    # =================================================================
    # ⚡ PART 1.5: DYNAMIC SLOT ALLOCATION STRATEGY
    # =================================================================
    You have a total of **10 Image Slots** to fill.

    **STEP A: ANALYZE USER INPUT**
    - Does User Info match a Template Module? -> **MERGE** it into that module.
    - Is User Info a NEW feature? -> **MARK** as "New Content".

    **STEP B: FILL THE SLOTS**
    1. **Phase 1 (Fixed):** Generate prompts for ALL defined [CORE MODULES] in the template first.
    2. **Phase 2 (Dynamic):** Fill remaining slots with "New Content" or "Fresh Perspectives" (Different angles/Details).

    **GOAL:** 10 Distinct, High-Value Images.

    # =================================================================
    # 📐 PART 2: THE PROMPT STRUCTURE & TEXT RULES
    # =================================================================
    You MUST rewrite every generated prompt into this STRICT 3-part order:
    [LAYER 1: SCENE] -> [LAYER 2: DESIGN/FONT] -> [LAYER 3: TEXT CONTENT]

    {dynamic_text_rules}

    # =================================================================
    # 📋 CONTEXT & DATA
    # =================================================================
    **Selected Style:** {style_name} ({style_desc})
    **Template Goal:** {core_template_instructions}
    **User Extra Info:** "{extra_info}"

    Generate 10 Prompts. Output: STRICT JSON LIST format only.
    """

    parts.append({"text": final_prompt})

    text_resp = _call_llm_api(api_key, parts)

    parsed = _parse_json_response(text_resp)
    if isinstance(parsed, list):
        return parsed
    if parsed is not None:
        return [str(parsed)]
    else:
        lines = text_resp.split('\n')
        res = [line.strip().strip('-').strip('1234567890. ') for line in lines if len(line) > 10]
        if not res:
            res = [text_resp]
        return res


# =================================================================
# 核心功能 3：视频矩阵裂变引擎 (Tab 4 专属 API)
# =================================================================

def api_matrix_generate_scene_prompts(api_key, source_img_path, rule_name, rule_content, count):
    """【节点 A：脑暴裂变】分析原图特征，根据规则裂变出 N 个不同的场景 Prompt"""
    parts = _build_image_parts(source_img_path)

    prompt = f"""
    You are a top-tier Commercial AI Prompt Engineer and Creative Director.
    Task: Create EXACTLY {count} distinct, highly-detailed English prompts for an AI image generator (like Midjourney).

    Context: The user provided product image(s). You must keep the core product strictly identical (shape, color, material).
    Scene Rule to follow: {rule_name} - {rule_content}

    Requirement: 
    Ensure each of the {count} prompts explores a completely different angle, background, or lighting variation within the bounds of the Scene Rule.

    Output Format: ONLY output a strict JSON array containing {count} strings. No markdown, no explanations, no numbers at the start.
    Example: ["prompt 1 details...", "prompt 2 details...", ...]
    """
    parts.append({"text": prompt})

    text_resp = _call_llm_api(api_key, parts)

    parsed = _parse_json_response(text_resp)
    if isinstance(parsed, list):
        return parsed[:int(count)]
    if parsed is not None:
        return [str(parsed)]
    else:
        lines = text_resp.split('\n')
        res = [line.strip().strip('-*0123456789. "') for line in lines if len(line) > 10]
        return res[:int(count)]


def api_matrix_generate_video_script(api_key, gen_img_path, rule_name, rule_content):
    """【节点 C：看图写本】看着新生成的场景图，根据运镜规则生成标准化视频脚本"""
    parts = _build_image_parts(gen_img_path)

    prompt = f"""
    You are a master AI Video Director. 
    Task: Write a highly specific video generation prompt (for models like Runway Gen-3 or Sora) based EXACTLY on the provided image, which serves as the FIRST FRAME.

    Camera Motion Rule to follow: {rule_name} - {rule_content}

    STRICT FORMULA: [Camera Movement] + [Lighting/Atmosphere] + [Subject Action/Details] + [Environment/Background]

    Requirements:
    - Describe the visual elements natively present in the image.
    - Apply the requested camera motion smoothly.
    - ONLY output the pure English prompt string (1-2 sentences). 
    - Do NOT include any markdown formatting, prefixes, or explanations.
    """
    parts.append({"text": prompt})

    text_resp = _call_llm_api(api_key, parts)
    return text_resp.replace('```', '').replace('\n', ' ').strip()


def api_extract_product_fingerprint(api_key, image_path):
    """提取商品细节指纹，供爆款替换做严格保款约束"""
    parts = _build_image_parts(image_path)
    prompt = """
    You are a meticulous apparel and product QA inspector.
    Analyze the uploaded product image and extract a strict product fingerprint for image replacement.

    Requirements:
    1. Focus on visible, objective, non-ambiguous product details only.
    2. Be especially precise about structural details that models often change during image generation.
    3. If a detail is not visible, write "unknown" instead of guessing.
    4. For trousers or pants, pay extra attention to fit profile, rise, front pleats, hip/thigh ease, leg volume,
       taper profile, knee width impression, hem opening, crease style, and whether the silhouette is relaxed,
       straight, tapered, carrot, slim, or wide.
    5. Explicitly identify the visible view and surfaces: front view, side view, back view, or mixed; front panel only,
       side seam visible, back panel visible, back pockets visible, and whether hidden surfaces should remain unseen.
    6. Be precise about closure presentation: exposed button, concealed button, zipper visibility, fly stitch shape,
       straight placket, J-stitch, overlap direction, or no visible fly.
    7. For apparel, separately capture easy-to-mess-up details such as button color, zipper color, hardware finish,
       seam or topstitch color, wash depth, overall color tone, panel construction, and fabric drape or weight.

    Output STRICT JSON only:
    {
      "product_type": "pants/shirt/jacket/dress/shoes/bag/other",
      "category_label": "short label",
      "view_orientation": "text",
      "visible_surfaces": "text",
      "silhouette": "text",
      "fit_profile": "text",
      "rise": "text",
      "front_pleats": "text",
      "leg_volume": "text",
      "taper_profile": "text",
      "hem_opening": "text",
      "crease_style": "text",
      "closure_visibility": "text",
      "fly_shape": "text",
      "primary_color": "text",
      "secondary_colors": ["text"],
      "color_tone_depth": "text",
      "wash_effect": "text",
      "material_texture": "text",
      "fabric_weight_drape": "text",
      "closure_system": "text",
      "button_color": "text",
      "zipper_color": "text",
      "hardware_finish": "text",
      "seam_stitch_color": "text",
      "waistband_or_opening": "text",
      "collar_or_neckline": "text",
      "sleeve_or_leg_shape": "text",
      "hem_or_cuff": "text",
      "pockets": "text",
      "panel_structure": "text",
      "hardware_and_trims": ["text"],
      "patterns_or_logos": ["text"],
      "signature_details": ["text"],
      "protected_regions": ["text"],
      "high_priority_features": ["text"],
      "summary": "one concise sentence"
    }
    """
    parts.append({"text": prompt})
    text_resp = _call_llm_api(api_key, parts)
    fallback = {
        "product_type": "other",
        "category_label": "unknown",
        "view_orientation": "unknown",
        "visible_surfaces": "unknown",
        "silhouette": "unknown",
        "fit_profile": "unknown",
        "rise": "unknown",
        "front_pleats": "unknown",
        "leg_volume": "unknown",
        "taper_profile": "unknown",
        "hem_opening": "unknown",
        "crease_style": "unknown",
        "closure_visibility": "unknown",
        "fly_shape": "unknown",
        "primary_color": "unknown",
        "secondary_colors": [],
        "color_tone_depth": "unknown",
        "wash_effect": "unknown",
        "material_texture": "unknown",
        "fabric_weight_drape": "unknown",
        "closure_system": "unknown",
        "button_color": "unknown",
        "zipper_color": "unknown",
        "hardware_finish": "unknown",
        "seam_stitch_color": "unknown",
        "waistband_or_opening": "unknown",
        "collar_or_neckline": "unknown",
        "sleeve_or_leg_shape": "unknown",
        "hem_or_cuff": "unknown",
        "pockets": "unknown",
        "panel_structure": "unknown",
        "hardware_and_trims": [],
        "patterns_or_logos": [],
        "signature_details": [],
        "protected_regions": [],
        "high_priority_features": [],
        "summary": "Fingerprint parsing failed",
    }
    parsed = _parse_json_response(text_resp, fallback=fallback)
    if not isinstance(parsed, dict):
        return fallback
    return parsed


def api_compare_product_consistency(api_key, original_image_path, generated_image_path, fingerprint):
    """对比原产品和替换结果，判断是否需要第二阶段修正"""
    parts = _build_image_parts([original_image_path, generated_image_path])
    fingerprint_str = json.dumps(fingerprint, ensure_ascii=False)
    prompt = f"""
    You are a strict product consistency reviewer for e-commerce image replacement.
    Image 1 is the original product reference.
    Image 2 is the generated replacement result.

    Product fingerprint:
    {fingerprint_str}

    Compare the product in Image 2 against Image 1.
    Focus on closure/opening structure, collar/neckline, waistband, pocket configuration, buttons, zippers,
    trims, logos, silhouette, hem/cuff shape, sleeve/leg shape, and other high priority details from the fingerprint.

    Output STRICT JSON only:
    {{
      "is_match": true,
      "score": 0,
      "issues": ["issue 1"],
      "correction_focus": ["focus 1"],
      "summary": "short sentence"
    }}

    Rules:
    - score is 0-100, where 100 means excellent consistency.
    - Set is_match to false if any important structural detail is changed or missing.
    - Keep issues concrete and visual.
    """
    parts.append({"text": prompt})
    text_resp = _call_llm_api(api_key, parts)
    fallback = {
        "is_match": True,
        "score": 100,
        "issues": [],
        "correction_focus": [],
        "summary": "Comparison parsing failed, assume pass",
    }
    parsed = _parse_json_response(text_resp, fallback=fallback)
    if not isinstance(parsed, dict):
        return fallback
    parsed.setdefault("is_match", True)
    parsed.setdefault("score", 100)
    parsed.setdefault("issues", [])
    parsed.setdefault("correction_focus", [])
    parsed.setdefault("summary", "")
    return parsed


def api_generate_image(prompt, key, ratio, source_img_path, save_directory, file_prefix="img", compress_enabled=False,
                       compress_target=2.0, image_size="1K", api_url=None):
    """
    统一生图入口：
    - 默认走 Google 原生图片接口
    - 当 model_config.api_type == chat_completions 时走 Sora / GPT-4o Image 对话补全接口
    - 当 model_config.api_type == openai_images 时走兼容 OpenAI Images 的 Seedream 接口
    """
    model_config = api_url if isinstance(api_url, dict) else {
        "api_type": "google_image",
        "url": api_url if api_url else getattr(
            config,
            "IMG_API_URL",
            "https://api.apiyi.com/v1beta/models/gemini-3.1-flash-image-preview:generateContent",
        ),
    }
    request_timeout = int(getattr(config, "IMAGE_GEN_TIMEOUT", 300))
    max_retries = max(1, int(getattr(config, "IMG_API_MAX_RETRIES", 3)))
    retry_base_delay = float(getattr(config, "IMG_API_RETRY_BASE_DELAY", 2.0))
    source_paths = _normalize_source_paths(source_img_path)

    try:
        try:
            config.log_to_file(f"生图请求准备发送: api_type={model_config.get('api_type')}, url={model_config.get('url')}, refs={len(source_paths)}, ratio={ratio}, size={image_size}")
        except Exception:
            pass

        if model_config.get("api_type") == "chat_completions_task":
            max_input_images = model_config.get("max_input_images")
            if max_input_images and len(source_paths) > int(max_input_images):
                raise Exception(f"当前模型最多支持 {max_input_images} 张参考图，当前请求包含 {len(source_paths)} 张。")

            allowed_ratios = model_config.get("allowed_ratios")
            effective_ratio = ratio if not allowed_ratios or ratio in allowed_ratios else allowed_ratios[0]
            allowed_resolutions = model_config.get("allowed_resolutions")
            output_resolution = image_size if not allowed_resolutions or image_size in allowed_resolutions else allowed_resolutions[0]
            model_name = model_config.get("model_4k") if str(output_resolution).upper() == "4K" and model_config.get("model_4k") else model_config.get("model")
            effective_key = model_config.get("key_override") or key

            headers = {
                "Authorization": f"Bearer {effective_key}",
                "Content-Type": "application/json",
            }

            if source_paths:
                content = [{"type": "text", "text": prompt}]
                content.extend(_build_chat_image_content(source_paths))
                payload = {
                    "model": model_name,
                    "stream": False,
                    "aspect_ratio": effective_ratio,
                    "output_resolution": output_resolution,
                    "messages": [{"role": "user", "content": content}],
                }
                submit_url = model_config["url"]
                request_mode = "image-to-image"
            else:
                payload = {
                    "model": model_name,
                    "prompt": prompt,
                    "aspect_ratio": effective_ratio,
                    "output_resolution": output_resolution,
                }
                submit_url = model_config.get("text_url") or model_config["url"]
                request_mode = "text-to-image"

            try:
                config.log_to_file(
                    f"OpenAI兼容图片请求: mode={request_mode}, submit_url={submit_url}, model={model_name}, refs={len(source_paths)}, ratio={effective_ratio}, resolution={output_resolution}"
                )
            except Exception:
                pass

            result = None
            last_error = None
            for attempt in range(1, max_retries + 1):
                try:
                    response = requests.post(submit_url, headers=headers, json=payload, timeout=request_timeout)
                    if response.status_code < 200 or response.status_code >= 300:
                        err_msg = _extract_response_error_message(response)
                        retriable_status = response.status_code in (408, 409, 425, 429, 500, 502, 503, 504)
                        if retriable_status and attempt < max_retries:
                            sleep_seconds = retry_base_delay * (2 ** (attempt - 1)) + random.uniform(0, 0.5)
                            time.sleep(sleep_seconds)
                            continue
                        raise Exception(f"API 响应错误 ({response.status_code}): {err_msg}")
                    result = response.json()
                    break
                except requests.exceptions.RequestException as exc:
                    last_error = exc
                    if attempt >= max_retries:
                        raise
                    sleep_seconds = retry_base_delay * (2 ** (attempt - 1)) + random.uniform(0, 0.5)
                    time.sleep(sleep_seconds)

            if result is None:
                raise last_error or Exception("图片任务提交接口未返回有效结果。")

            image_data = result.get("data") if isinstance(result, dict) else None
            first_item = image_data[0] if image_data and isinstance(image_data[0], dict) else {}
            direct_image_url = (
                first_item.get("url")
                or first_item.get("image_url")
                or first_item.get("download_url")
                or first_item.get("result_url")
                or _extract_task_image_url(result)
            )
            if direct_image_url:
                return _save_image_from_url(
                    direct_image_url,
                    save_directory,
                    file_prefix,
                    compress_enabled=compress_enabled,
                    compress_target=compress_target,
                )

            message_content = ""
            if isinstance(result, dict):
                message_content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
            markdown_urls = _extract_markdown_image_urls(message_content)
            if markdown_urls:
                return _save_image_from_url(
                    markdown_urls[0],
                    save_directory,
                    file_prefix,
                    compress_enabled=compress_enabled,
                    compress_target=compress_target,
                )

            poll_url = _extract_task_poll_url(result, model_config)
            if not poll_url:
                raise Exception(f"图片任务提交成功但未返回图片地址、task_id 或 poll_url: {result}")

            deadline = time.time() + request_timeout
            while time.time() < deadline:
                response = requests.get(
                    poll_url,
                    headers={"Authorization": f"Bearer {effective_key}"},
                    timeout=min(60, request_timeout),
                )
                if response.status_code < 200 or response.status_code >= 300:
                    err_msg = _extract_response_error_message(response)
                    raise Exception(f"任务查询失败 ({response.status_code}): {err_msg}")

                task_result = response.json()
                image_url = _extract_task_image_url(task_result)
                if image_url:
                    return _save_image_from_url(
                        image_url,
                        save_directory,
                        file_prefix,
                        compress_enabled=compress_enabled,
                        compress_target=compress_target,
                    )

                status = _normalize_task_status(task_result)
                if status in {"failed", "error", "cancelled", "canceled"}:
                    raise Exception(task_result.get("fail_reason") or task_result.get("error") or f"图片任务失败: {task_result}")

                time.sleep(3)

            raise Exception(f"图片任务超时未完成: {poll_url}")

        if model_config.get("api_type") == "chat_completions":
            max_input_images = model_config.get("max_input_images")
            if max_input_images and len(source_paths) > int(max_input_images):
                raise Exception(f"当前模型最多支持 {max_input_images} 张参考图，实际传入 {len(source_paths)} 张。")

            allowed_ratios = model_config.get("allowed_ratios")
            effective_ratio = ratio if not allowed_ratios or ratio in allowed_ratios else allowed_ratios[0]
            effective_key = model_config.get("key_override") or key

            headers = {
                "Authorization": f"Bearer {effective_key}",
                "Content-Type": "application/json",
            }
            content = [{"type": "text", "text": prompt}]
            content.extend(_build_chat_image_content(source_img_path))
            payload = {
                "model": model_config.get("model", "sora_image"),
                "messages": [{"role": "user", "content": content}],
            }
            if model_config.get("size_param_mode") == "nano_banana":
                payload["size"] = _ratio_to_nano_banana_size(effective_ratio or "1:1", image_size)
            elif effective_ratio:
                payload["size"] = effective_ratio

            result = None
            last_error = None
            for attempt in range(1, max_retries + 1):
                try:
                    response = requests.post(model_config["url"], headers=headers, json=payload, timeout=request_timeout)
                    if response.status_code != 200:
                        err_msg = response.text
                        try:
                            err_msg = response.json().get("error", {}).get("message", response.text)
                        except Exception:
                            pass
                        retriable_status = response.status_code in (408, 409, 425, 429, 500, 502, 503, 504)
                        if retriable_status and attempt < max_retries:
                            sleep_seconds = retry_base_delay * (2 ** (attempt - 1)) + random.uniform(0, 0.5)
                            time.sleep(sleep_seconds)
                            continue
                        raise Exception(f"API 请求失败 ({response.status_code}): {err_msg}")
                    result = response.json()
                    break
                except requests.exceptions.RequestException as exc:
                    last_error = exc
                    if attempt >= max_retries:
                        raise
                    sleep_seconds = retry_base_delay * (2 ** (attempt - 1)) + random.uniform(0, 0.5)
                    time.sleep(sleep_seconds)

            if result is None:
                raise last_error or Exception("接口未返回有效结果")

            message_content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
            image_urls = _extract_markdown_image_urls(message_content)
            if not image_urls:
                raise Exception(f"响应中没有解析到图片链接: {message_content}")

            return _save_image_from_url(
                image_urls[0],
                save_directory,
                file_prefix,
                compress_enabled=compress_enabled,
                compress_target=compress_target,
            )

        if model_config.get("api_type") == "openai_images":
            max_input_images = model_config.get("max_input_images")
            if max_input_images and len(source_paths) > int(max_input_images):
                raise Exception(f"当前模型最多支持 {max_input_images} 张输入图，当前请求包含 {len(source_paths)} 张。")

            allowed_ratios = model_config.get("allowed_ratios")
            effective_ratio = ratio if not allowed_ratios or ratio in allowed_ratios else allowed_ratios[0]
            effective_size = _build_explicit_size_from_ratio(effective_ratio, image_size)

            headers = {
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
            }
            payload = {
                "model": model_config.get("model", "seedream-5-0-260128"),
                "prompt": prompt,
                "response_format": "url",
                "size": effective_size,
                "stream": False,
                "watermark": False,
            }

            image_input = _build_openai_images_input(source_paths)
            if image_input is not None:
                payload["image"] = image_input
                payload["sequential_image_generation"] = "disabled"

            result = None
            last_error = None
            for attempt in range(1, max_retries + 1):
                try:
                    response = requests.post(model_config["url"], headers=headers, json=payload, timeout=request_timeout)
                    if response.status_code != 200:
                        err_msg = response.text
                        try:
                            err_msg = response.json().get("error", {}).get("message", response.text)
                        except Exception:
                            pass
                        retriable_status = response.status_code in (408, 409, 425, 429, 500, 502, 503, 504)
                        if retriable_status and attempt < max_retries:
                            sleep_seconds = retry_base_delay * (2 ** (attempt - 1)) + random.uniform(0, 0.5)
                            time.sleep(sleep_seconds)
                            continue
                        raise Exception(f"API 响应错误 ({response.status_code}): {err_msg}")
                    result = response.json()
                    break
                except requests.exceptions.RequestException as exc:
                    last_error = exc
                    if attempt >= max_retries:
                        raise
                    sleep_seconds = retry_base_delay * (2 ** (attempt - 1)) + random.uniform(0, 0.5)
                    time.sleep(sleep_seconds)

            if result is None:
                raise last_error or Exception("生图接口未返回有效结果。")

            image_data = result.get("data") or []
            image_url = image_data[0].get("url") if image_data and isinstance(image_data[0], dict) else None
            if not image_url:
                raise Exception(f"未在响应中提取到图片链接: {result}")

            return _save_image_from_url(
                image_url,
                save_directory,
                file_prefix,
                compress_enabled=compress_enabled,
                compress_target=compress_target,
            )

        if model_config.get("api_type") == "hancat_banana_images":
            max_input_images = model_config.get("max_input_images")
            if max_input_images and len(source_paths) > int(max_input_images):
                raise Exception(f"当前模型最多支持 {max_input_images} 张参考图，当前请求包含 {len(source_paths)} 张。")

            allowed_ratios = model_config.get("allowed_ratios")
            effective_ratio = ratio if not allowed_ratios or ratio in allowed_ratios else allowed_ratios[0]
            allowed_resolutions = model_config.get("allowed_resolutions")
            effective_image_size = image_size if not allowed_resolutions or image_size in allowed_resolutions else allowed_resolutions[0]
            effective_size = _build_explicit_size_from_ratio(effective_ratio, effective_image_size)
            effective_key = model_config.get("key_override") or key

            headers = {
                "Authorization": f"Bearer {effective_key}",
                "Content-Type": "application/json",
            }
            payload = {
                "model": model_config.get("model", "gemini_3.1_flash_image_preview"),
                "prompt": prompt,
                "size": effective_size,
                "response_format": "b64_json",
                "extra_body": {
                    "google": {
                        "image_config": {
                            "aspect_ratio": effective_ratio,
                            "image_size": effective_image_size,
                            "size": effective_size,
                        }
                    }
                },
            }

            image_input = _build_openai_images_input(source_paths)
            if image_input is not None:
                payload["image"] = image_input

            result = None
            last_error = None
            for attempt in range(1, max_retries + 1):
                try:
                    response = requests.post(model_config["url"], headers=headers, json=payload, timeout=request_timeout)
                    if response.status_code != 200:
                        err_msg = _extract_response_error_message(response)
                        retriable_status = response.status_code in (408, 409, 425, 429, 500, 502, 503, 504)
                        if retriable_status and attempt < max_retries:
                            sleep_seconds = retry_base_delay * (2 ** (attempt - 1)) + random.uniform(0, 0.5)
                            time.sleep(sleep_seconds)
                            continue
                        raise Exception(f"API 响应错误 ({response.status_code}): {err_msg}")
                    result = response.json()
                    break
                except requests.exceptions.RequestException as exc:
                    last_error = exc
                    if attempt >= max_retries:
                        raise
                    sleep_seconds = retry_base_delay * (2 ** (attempt - 1)) + random.uniform(0, 0.5)
                    time.sleep(sleep_seconds)

            if result is None:
                raise last_error or Exception("图片接口未返回有效结果。")

            image_data = result.get("data") or []
            first_item = image_data[0] if image_data and isinstance(image_data[0], dict) else {}

            image_b64 = first_item.get("b64_json")
            if image_b64:
                return _save_image_from_base64_payload(
                    image_b64,
                    save_directory,
                    file_prefix,
                    compress_enabled=compress_enabled,
                    compress_target=compress_target,
                )

            image_url = first_item.get("url") or first_item.get("image_url")
            if image_url:
                return _save_image_from_url(
                    image_url,
                    save_directory,
                    file_prefix,
                    compress_enabled=compress_enabled,
                    compress_target=compress_target,
                )

            direct_url = result.get("url") or result.get("image_url")
            if direct_url:
                return _save_image_from_url(
                    direct_url,
                    save_directory,
                    file_prefix,
                    compress_enabled=compress_enabled,
                    compress_target=compress_target,
                )

            raise Exception(f"未在响应中提取到图片结果: {result}")

        if model_config.get("api_type") == "gpt_image_edits":
            if not source_paths:
                raise Exception("gpt-image-2 闇€瑕佽嚦灏?1 寮犲弬鑰冨浘")

            headers = {
                "Authorization": f"Bearer {key}",
            }
            data = {
                "model": model_config.get("model", "gpt-image-2-all"),
                "prompt": prompt,
                "response_format": "url",
            }

            result = None
            last_error = None
            for attempt in range(1, max_retries + 1):
                loop_handles = []
                try:
                    files, loop_handles = _build_multipart_image_files(source_paths)
                    response = requests.post(
                        model_config["url"],
                        headers=headers,
                        data=data,
                        files=files,
                        timeout=request_timeout,
                    )
                    if response.status_code != 200:
                        err_msg = _extract_response_error_message(response)
                        retriable_status = response.status_code in (408, 409, 425, 429, 500, 502, 503, 504)
                        if retriable_status and attempt < max_retries:
                            sleep_seconds = retry_base_delay * (2 ** (attempt - 1)) + random.uniform(0, 0.5)
                            time.sleep(sleep_seconds)
                            continue
                        raise Exception(f"API 鍝嶅簲閿欒 ({response.status_code}): {err_msg}")
                    result = response.json()
                    break
                except requests.exceptions.RequestException as exc:
                    last_error = exc
                    if attempt >= max_retries:
                        raise
                    sleep_seconds = retry_base_delay * (2 ** (attempt - 1)) + random.uniform(0, 0.5)
                    time.sleep(sleep_seconds)
                finally:
                    for handle in loop_handles:
                        try:
                            handle.close()
                        except Exception:
                            pass

            if result is None:
                raise last_error or Exception("鍥剧墖缂栬緫鎺ュ彛鏈繑鍥炴湁鏁堢粨鏋溿€?")

            image_data = result.get("data") or []
            first_item = image_data[0] if image_data and isinstance(image_data[0], dict) else {}
            image_url = first_item.get("url")
            if image_url:
                return _save_image_from_url(
                    image_url,
                    save_directory,
                    file_prefix,
                    compress_enabled=compress_enabled,
                    compress_target=compress_target,
                )

            image_b64 = first_item.get("b64_json")
            if image_b64:
                return _save_image_from_base64_payload(
                    image_b64,
                    save_directory,
                    file_prefix,
                    compress_enabled=compress_enabled,
                    compress_target=compress_target,
                )

            raise Exception(f"鏈湪鍝嶅簲涓彁鍙栧埌鍥剧墖缁撴灉: {result}")

        if model_config.get("api_type") == "catking_image_task":
            effective_key = model_config.get("key_override") or key
            max_input_images = int(model_config.get("max_input_images", 1))
            if len(source_paths) > max_input_images:
                raise Exception(f"当前模型最多支持 {max_input_images} 张参考图，当前请求包含 {len(source_paths)} 张。")

            model_name = f"{model_config['model_prefix']}-{ratio}-{str(image_size).lower()}"
            headers = {
                "Authorization": f"Bearer {effective_key}",
                "Content-Type": "application/json",
            }
            payload = {
                "prompt": prompt,
                "model": model_name,
            }
            if source_paths:
                ref_images = [_build_data_url_from_path(p) for p in source_paths]
                payload["reference_images"] = ref_images

            result = None
            last_error = None
            create_url = model_config["url"]
            for attempt in range(1, max_retries + 1):
                try:
                    response = requests.post(create_url, headers=headers, json=payload, timeout=request_timeout)
                    if response.status_code < 200 or response.status_code >= 300:
                        err_msg = _extract_response_error_message(response)
                        retriable_status = response.status_code in (408, 409, 425, 429, 500, 502, 503, 504)
                        if retriable_status and attempt < max_retries:
                            sleep_seconds = retry_base_delay * (2 ** (attempt - 1)) + random.uniform(0, 0.5)
                            time.sleep(sleep_seconds)
                            continue
                        raise Exception(f"API 响应错误 ({response.status_code}): {err_msg}")
                    result = response.json()
                    break
                except requests.exceptions.RequestException as exc:
                    last_error = exc
                    if attempt >= max_retries:
                        raise
                    sleep_seconds = retry_base_delay * (2 ** (attempt - 1)) + random.uniform(0, 0.5)
                    time.sleep(sleep_seconds)

            if result is None:
                raise last_error or Exception("图片任务接口未返回有效结果。")

            task_id = result.get("id")
            if not task_id:
                raise Exception(f"创建图片任务失败，响应中未返回任务 ID: {result}")

            poll_url = f"{create_url.rstrip('/')}/{task_id}"
            deadline = time.time() + request_timeout
            while time.time() < deadline:
                response = requests.get(
                    poll_url,
                    headers={"Authorization": f"Bearer {effective_key}"},
                    timeout=min(60, request_timeout),
                )
                if response.status_code < 200 or response.status_code >= 300:
                    err_msg = _extract_response_error_message(response)
                    raise Exception(f"任务查询失败 ({response.status_code}): {err_msg}")

                task_result = response.json()
                status = str(task_result.get("status", "")).lower()
                if status == "completed":
                    result_url = task_result.get("url")
                    if not result_url:
                        raise Exception(f"任务已完成但未返回结果地址: {task_result}")
                    return _save_image_from_url(
                        result_url,
                        save_directory,
                        file_prefix,
                        compress_enabled=compress_enabled,
                        compress_target=compress_target,
                    )
                if status in {"failed", "error", "cancelled", "canceled"}:
                    raise Exception(task_result.get("message") or f"图片任务失败: {task_result}")

                time.sleep(3)

            raise Exception(f"图片任务超时未完成，任务 ID: {task_id}")

        url = model_config["url"]
        effective_key = model_config.get("key_override") or key
        if model_config.get("append_key_query"):
            connector = "&" if "?" in url else "?"
            url = f"{url}{connector}key={quote(str(effective_key), safe='')}"

        max_input_images = model_config.get("max_input_images")
        if max_input_images and len(source_paths) > int(max_input_images):
            raise Exception(f"当前模型最多支持 {max_input_images} 张参考图，当前请求包含 {len(source_paths)} 张。")

        allowed_ratios = model_config.get("allowed_ratios")
        effective_ratio = ratio if not allowed_ratios or ratio in allowed_ratios else allowed_ratios[0]
        allowed_resolutions = model_config.get("allowed_resolutions")
        effective_image_size = image_size if not allowed_resolutions or image_size in allowed_resolutions else allowed_resolutions[0]

        parts = _build_image_parts(source_paths)
        parts.append({"text": prompt})
        headers = {
            "Authorization": f"Bearer {effective_key}",
            "Content-Type": "application/json"
        }
        content_item = {"parts": parts}
        if model_config.get("include_user_role"):
            content_item["role"] = "user"

        payload = {
            "contents": [content_item],
            "generationConfig": {
                "responseModalities": model_config.get("response_modalities", ["IMAGE"]),
                "imageConfig": {
                    "aspectRatio": effective_ratio,
                    "imageSize": effective_image_size
                }
            }
        }

        result = None
        last_error = None
        for attempt in range(1, max_retries + 1):
            try:
                if model_config.get("use_request_data"):
                    response = requests.request(
                        "POST",
                        url,
                        headers=headers,
                        data=json.dumps(payload),
                        timeout=request_timeout,
                    )
                else:
                    response = requests.post(url, headers=headers, json=payload, timeout=request_timeout)
                if response.status_code != 200:
                    err_msg = response.text
                    try:
                        err_msg = response.json().get("error", {}).get("message", response.text)
                    except Exception:
                        pass
                    retriable_status = response.status_code in (408, 409, 425, 429, 500, 502, 503, 504)
                    if retriable_status and attempt < max_retries:
                        sleep_seconds = retry_base_delay * (2 ** (attempt - 1)) + random.uniform(0, 0.5)
                        time.sleep(sleep_seconds)
                        continue
                    raise Exception(f"API 响应错误 ({response.status_code}): {err_msg}")
                result = response.json()
                break
            except requests.exceptions.RequestException as exc:
                last_error = exc
                if attempt >= max_retries:
                    raise
                sleep_seconds = retry_base_delay * (2 ** (attempt - 1)) + random.uniform(0, 0.5)
                time.sleep(sleep_seconds)

        if result is None:
            raise last_error or Exception("生图接口未返回有效结果。")

        candidate = result.get("candidates", [{}])[0]
        response_parts = candidate.get("content", {}).get("parts", [])
        image_data = None
        for parts_resp in response_parts:
            if "inlineData" in parts_resp:
                image_data = parts_resp["inlineData"].get("data")
                break
            if "inline_data" in parts_resp:
                image_data = parts_resp["inline_data"].get("data")
                break
        if not image_data:
            raise Exception("API 返回的数据中未找到图片内容。")

        if not os.path.exists(save_directory):
            os.makedirs(save_directory)

        unique_suffix = f"{int(time.time() * 1000)}_{uuid.uuid4().hex[:8]}"
        output_file = os.path.join(save_directory, f"{file_prefix}_{unique_suffix}.png")
        with open(output_file, "wb") as f:
            f.write(base64.b64decode(image_data))

        if compress_enabled:
            utils.compress_image_smart(output_file, compress_target, output_file)

        return output_file

    except Exception as e:
        raise Exception(f"生图请求失败: {e}")
