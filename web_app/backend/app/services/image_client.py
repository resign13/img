from __future__ import annotations

import base64
import io
import os
import random
import time
import uuid
from pathlib import Path

import requests
from PIL import Image, ImageOps

import config
import utils
from core import api_client as desktop_api_client


def _get_mime_type(image_path: str) -> str:
    lower = str(image_path).lower()
    if lower.endswith(".png"):
        return "image/png"
    if lower.endswith(".webp"):
        return "image/webp"
    return "image/jpeg"


def _flatten_to_rgb(image: Image.Image) -> Image.Image:
    if image.mode in ("RGBA", "LA"):
        background = Image.new("RGB", image.size, (255, 255, 255))
        background.paste(image.convert("RGBA"), mask=image.convert("RGBA").getchannel("A"))
        return background
    if image.mode == "P":
        return _flatten_to_rgb(image.convert("RGBA"))
    if image.mode != "RGB":
        return image.convert("RGB")
    return image


def _encode_image_for_api(image_path: str) -> tuple[str, str]:
    max_side = int(getattr(config, "API_UPLOAD_MAX_SIDE", 1600))
    max_bytes = int(getattr(config, "API_UPLOAD_MAX_BYTES", 1024 * 1024))
    try:
        resample = Image.Resampling.LANCZOS
    except AttributeError:
        resample = Image.LANCZOS

    try:
        with Image.open(image_path) as pil_img:
            image = ImageOps.exif_transpose(pil_img)
            image.load()
        width, height = image.size
        if max(width, height) > max_side:
            image.thumbnail((max_side, max_side), resample)
        image = _flatten_to_rgb(image)
        for quality in (92, 88, 84, 80, 76, 72, 68, 64, 60):
            buffer = io.BytesIO()
            image.save(buffer, format="JPEG", quality=quality, optimize=True)
            data = buffer.getvalue()
            if len(data) <= max_bytes or quality == 60:
                return base64.b64encode(data).decode("utf-8"), "image/jpeg"
    except Exception:
        pass

    with open(image_path, "rb") as file_obj:
        return base64.b64encode(file_obj.read()).decode("utf-8"), _get_mime_type(image_path)


def _save_base64_image(image_payload: str, save_directory: str, file_prefix: str, compress_enabled: bool, compress_target: float) -> str:
    os.makedirs(save_directory, exist_ok=True)
    payload = (image_payload or "").strip()
    if payload.startswith("data:") and "," in payload:
        payload = payload.split(",", 1)[1]
    output_file = os.path.join(save_directory, f"{file_prefix}_{int(time.time() * 1000)}_{uuid.uuid4().hex[:8]}.png")
    with open(output_file, "wb") as file_obj:
        file_obj.write(base64.b64decode(payload))
    if compress_enabled:
        utils.compress_image_smart(output_file, compress_target, output_file)
    return output_file


def _save_url_image(image_url: str, save_directory: str, file_prefix: str, compress_enabled: bool, compress_target: float, key: str = "") -> str:
    os.makedirs(save_directory, exist_ok=True)
    headers = {"Authorization": f"Bearer {key}"} if key else None
    response = requests.get(image_url, headers=headers, timeout=120)
    response.raise_for_status()
    output_file = os.path.join(save_directory, f"{file_prefix}_{int(time.time() * 1000)}_{uuid.uuid4().hex[:8]}.png")
    with open(output_file, "wb") as file_obj:
        file_obj.write(response.content)
    if compress_enabled:
        utils.compress_image_smart(output_file, compress_target, output_file)
    return output_file


def _extract_error_message(response: requests.Response) -> str:
    try:
        payload = response.json()
    except Exception:
        return response.text
    if isinstance(payload, dict):
        error = payload.get("error")
        if isinstance(error, dict) and error.get("message"):
            return str(error["message"])
        if payload.get("message"):
            return str(payload["message"])
    return response.text


def _normalize_paths(source_img_path) -> list[str]:
    if isinstance(source_img_path, list):
        return [str(item) for item in source_img_path if item]
    if source_img_path:
        return [str(source_img_path)]
    return []


def generate_image(
    prompt: str,
    key: str,
    ratio: str,
    source_img_path,
    save_directory: str,
    file_prefix: str = "img",
    compress_enabled: bool = False,
    compress_target: float = 2.0,
    image_size: str = "1K",
    model_config: dict | None = None,
) -> str:
    model_config = model_config or {}
    if model_config.get("api_type") != "gemini_native_image":
        return desktop_api_client.api_generate_image(
            prompt,
            key,
            ratio,
            source_img_path,
            save_directory,
            file_prefix,
            compress_enabled,
            compress_target,
            image_size,
            model_config,
        )

    source_paths = _normalize_paths(source_img_path)
    max_input_images = model_config.get("max_input_images")
    if max_input_images and len(source_paths) > int(max_input_images):
        raise Exception(f"当前模型最多支持 {max_input_images} 张参考图，当前请求包含 {len(source_paths)} 张。")

    allowed_ratios = model_config.get("allowed_ratios")
    effective_ratio = ratio if not allowed_ratios or ratio in allowed_ratios else allowed_ratios[0]
    allowed_resolutions = model_config.get("allowed_resolutions")
    effective_size = image_size if not allowed_resolutions or image_size in allowed_resolutions else allowed_resolutions[0]
    effective_key = model_config.get("key_override") or key

    parts = [{"text": prompt}]
    for path in source_paths:
        img_b64, mime = _encode_image_for_api(path)
        parts.append({"inlineData": {"mimeType": mime, "data": img_b64}})

    payload = {
        "contents": [{"role": "user", "parts": parts}],
        "generationConfig": {
            "imageConfig": {
                "imageSize": effective_size,
                "aspectRatio": effective_ratio,
            }
        },
    }
    headers = {
        "x-goog-api-key": effective_key,
        "Content-Type": "application/json",
    }

    timeout = int(getattr(config, "IMAGE_GEN_TIMEOUT", 300))
    max_retries = max(1, int(getattr(config, "IMG_API_MAX_RETRIES", 3)))
    retry_base_delay = float(getattr(config, "IMG_API_RETRY_BASE_DELAY", 2.0))
    result = None
    for attempt in range(1, max_retries + 1):
        response = requests.post(model_config["url"], headers=headers, json=payload, timeout=timeout)
        if 200 <= response.status_code < 300:
            result = response.json()
            break
        retriable = response.status_code in (408, 409, 425, 429, 500, 502, 503, 504)
        if retriable and attempt < max_retries:
            time.sleep(retry_base_delay * (2 ** (attempt - 1)) + random.uniform(0, 0.5))
            continue
        raise Exception(f"API 响应错误 ({response.status_code}): {_extract_error_message(response)}")

    if result is None:
        raise Exception("Gemini 原生生图接口未返回有效结果。")

    candidates = result.get("candidates", []) if isinstance(result, dict) else []
    response_parts = candidates[0].get("content", {}).get("parts", []) if candidates else []
    for item in response_parts:
        inline_data = item.get("inlineData") or item.get("inline_data")
        if inline_data and inline_data.get("data"):
            return _save_base64_image(inline_data["data"], save_directory, file_prefix, compress_enabled, compress_target)
        file_data = item.get("fileData") or item.get("file_data")
        if isinstance(file_data, dict):
            file_url = file_data.get("fileUri") or file_data.get("file_uri")
            if file_url:
                return _save_url_image(file_url, save_directory, file_prefix, compress_enabled, compress_target, effective_key)

    raise Exception(f"Gemini 原生响应中没有解析到图片: {result}")
