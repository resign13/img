from __future__ import annotations

import base64
import io
import os
import random
import time
import uuid

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


def _build_data_url_from_path(image_path: str) -> str:
    img_b64, mime = _encode_image_for_api(image_path)
    return f"data:{mime};base64,{img_b64}"


def _ratio_to_size_alias(ratio: str, image_size: str) -> str:
    clean_ratio = str(ratio or "1:1").replace(":", "x")
    clean_size = str(image_size or "1K").lower()
    return f"{clean_ratio}-{clean_size}"


def _extract_result_image_url(payload: dict) -> str:
    for key in ("url", "download_url", "result_url", "image_url", "detail_url"):
        value = payload.get(key)
        if isinstance(value, str) and value.startswith(("http://", "https://")):
            return value

    data = payload.get("data")
    if isinstance(data, list) and data:
        first_item = data[0]
        if isinstance(first_item, dict):
            for key in ("url", "download_url", "result_url", "image_url"):
                value = first_item.get(key)
                if isinstance(value, str) and value.startswith(("http://", "https://")):
                    return value
    if isinstance(data, dict):
        for key in ("url", "download_url", "result_url", "image_url"):
            value = data.get(key)
            if isinstance(value, str) and value.startswith(("http://", "https://")):
                return value
        image_urls = data.get("image_urls")
        if isinstance(image_urls, list) and image_urls and isinstance(image_urls[0], str):
            return image_urls[0]

    result = payload.get("result")
    if isinstance(result, dict):
        for key in ("url", "download_url", "result_url", "image_url"):
            value = result.get(key)
            if isinstance(value, str) and value.startswith(("http://", "https://")):
                return value
        image_urls = result.get("image_urls")
        if isinstance(image_urls, list) and image_urls and isinstance(image_urls[0], str):
            return image_urls[0]

    return ""


def _run_mingyu_async_image(
    prompt: str,
    key: str,
    ratio: str,
    source_paths: list[str],
    save_directory: str,
    file_prefix: str,
    compress_enabled: bool,
    compress_target: float,
    image_size: str,
    model_config: dict,
) -> str:
    max_input_images = model_config.get("max_input_images")
    if max_input_images and len(source_paths) > int(max_input_images):
        raise Exception(f"\u5f53\u524d\u6a21\u578b\u6700\u591a\u652f\u6301 {max_input_images} \u5f20\u53c2\u8003\u56fe\uff0c\u5f53\u524d\u8bf7\u6c42\u5305\u542b {len(source_paths)} \u5f20\u3002")

    allowed_ratios = model_config.get("allowed_ratios")
    effective_ratio = ratio if not allowed_ratios or ratio in allowed_ratios else allowed_ratios[0]
    allowed_resolutions = model_config.get("allowed_resolutions")
    normalized_size = str(image_size or "").upper()
    effective_size = normalized_size if not allowed_resolutions or normalized_size in allowed_resolutions else allowed_resolutions[0]
    effective_key = (model_config.get("key_override") or key or "").strip()
    if not effective_key:
        raise Exception("低成本 Nano Banana 渠道缺少 API Key，请在服务器环境变量 MINGYU_NANO_BANANA_KEY 中配置。")

    payload = {
        "model": model_config.get("model", "nano-banana-2"),
        "prompt": prompt,
        "mode": "image_to_image" if source_paths else "text_to_image",
        "size": _ratio_to_size_alias(effective_ratio, effective_size),
        "quality": effective_size,
        "response_format": "url",
    }
    if source_paths:
        payload["images"] = [_build_data_url_from_path(path) for path in source_paths]

    headers = {
        "Authorization": f"Bearer {effective_key}",
        "Content-Type": "application/json",
    }
    timeout = int(getattr(config, "IMAGE_GEN_TIMEOUT", 300))
    max_retries = max(1, int(getattr(config, "IMG_API_MAX_RETRIES", 3)))
    retry_base_delay = float(getattr(config, "IMG_API_RETRY_BASE_DELAY", 2.0))
    create_url = model_config["url"]

    result = None
    for attempt in range(1, max_retries + 1):
        if attempt == 1:
            config.log_to_file(
                "Web Mingyu async image request: "
                f"model={payload['model']}, url={create_url}, size={payload['size']}, refs={len(source_paths)}"
            )
        response = requests.post(create_url, headers=headers, json=payload, timeout=timeout)
        if 200 <= response.status_code < 300:
            result = response.json()
            break
        retriable = response.status_code in (408, 409, 425, 429, 500, 502, 503, 504)
        if retriable and attempt < max_retries:
            time.sleep(retry_base_delay * (2 ** (attempt - 1)) + random.uniform(0, 0.5))
            continue
        raise Exception(f"API \u54cd\u5e94\u9519\u8bef ({response.status_code}): {_extract_error_message(response)}")

    if result is None:
        raise Exception("低成本 Nano Banana 接口未返回有效结果。")

    immediate_url = _extract_result_image_url(result)
    if immediate_url:
        return _save_url_image(immediate_url, save_directory, file_prefix, compress_enabled, compress_target, effective_key)

    task_id = result.get("id") or result.get("task_id") or result.get("taskId")
    if not task_id:
        raise Exception(f"低成本 Nano Banana 任务提交成功但未返回任务 ID: {result}")

    poll_url = f"{create_url.rstrip('/')}/{task_id}"
    deadline = time.time() + timeout
    while time.time() < deadline:
        response = requests.get(poll_url, headers={"Authorization": f"Bearer {effective_key}"}, timeout=min(60, timeout))
        if response.status_code < 200 or response.status_code >= 300:
            raise Exception(f"任务查询失败 ({response.status_code}): {_extract_error_message(response)}")

        task_result = response.json()
        status = str(task_result.get("status") or task_result.get("state") or "").strip().lower()
        if status in {"completed", "succeeded", "success", "done"}:
            result_url = _extract_result_image_url(task_result)
            if not result_url:
                raise Exception(f"任务已完成但未返回图片地址: {task_result}")
            return _save_url_image(result_url, save_directory, file_prefix, compress_enabled, compress_target, effective_key)
        if status in {"failed", "error", "cancelled", "canceled"}:
            raise Exception(task_result.get("error") or task_result.get("message") or f"低成本 Nano Banana 任务失败: {task_result}")
        time.sleep(3)

    raise Exception(f"低成本 Nano Banana 任务超时未完成，任务 ID: {task_id}")


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
    source_paths = _normalize_paths(source_img_path)
    if model_config.get("api_type") == "mingyu_async_image":
        return _run_mingyu_async_image(
            prompt=prompt,
            key=key,
            ratio=ratio,
            source_paths=source_paths,
            save_directory=save_directory,
            file_prefix=file_prefix,
            compress_enabled=compress_enabled,
            compress_target=compress_target,
            image_size=image_size,
            model_config=model_config,
        )

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

    max_input_images = model_config.get("max_input_images")
    if max_input_images and len(source_paths) > int(max_input_images):
        raise Exception(f"\u5f53\u524d\u6a21\u578b\u6700\u591a\u652f\u6301 {max_input_images} \u5f20\u53c2\u8003\u56fe\uff0c\u5f53\u524d\u8bf7\u6c42\u5305\u542b {len(source_paths)} \u5f20\u3002")

    allowed_ratios = model_config.get("allowed_ratios")
    effective_ratio = ratio if not allowed_ratios or ratio in allowed_ratios else allowed_ratios[0]
    allowed_resolutions = model_config.get("allowed_resolutions")
    normalized_size = str(image_size or "").upper()
    effective_size = normalized_size if not allowed_resolutions or normalized_size in allowed_resolutions else allowed_resolutions[0]
    effective_key = model_config.get("key_override") or key

    parts = [{"text": prompt}]
    for path in source_paths:
        img_b64, mime = _encode_image_for_api(path)
        parts.append({"inlineData": {"mimeType": mime, "data": img_b64}})

    payload = {
        "contents": [{"role": "user", "parts": parts}],
        "generationConfig": {
            "responseModalities": model_config.get("response_modalities", ["IMAGE"]),
            "imageConfig": {
                "imageSize": effective_size,
                "aspectRatio": effective_ratio,
            },
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
        if attempt == 1:
            config.log_to_file(
                "Web Gemini native request: "
                f"model={model_config.get('model')}, url={model_config.get('url')}, "
                f"ratio={effective_ratio}, size={effective_size}, refs={len(source_paths)}"
            )
        response = requests.post(model_config["url"], headers=headers, json=payload, timeout=timeout)
        if 200 <= response.status_code < 300:
            result = response.json()
            break
        retriable = response.status_code in (408, 409, 425, 429, 500, 502, 503, 504)
        if retriable and attempt < max_retries:
            time.sleep(retry_base_delay * (2 ** (attempt - 1)) + random.uniform(0, 0.5))
            continue
        raise Exception(f"API \u54cd\u5e94\u9519\u8bef ({response.status_code}): {_extract_error_message(response)}")

    if result is None:
        raise Exception("Gemini \u539f\u751f\u751f\u56fe\u63a5\u53e3\u672a\u8fd4\u56de\u6709\u6548\u7ed3\u679c\u3002")

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

    raise Exception(f"Gemini \u539f\u751f\u54cd\u5e94\u4e2d\u6ca1\u6709\u89e3\u6790\u5230\u56fe\u7247: {result}")
