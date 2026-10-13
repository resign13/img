"""APIyi Nano Banana 2.1 protocol shared by desktop and web."""
import base64
import io
import math
import os
from pathlib import Path
import time
import uuid

from PIL import Image, ImageOps

LABEL = "API易 Nano Banana 2.1"
MODEL = {
    "api_type": "gemini_native_image",
    "protocol": "apiyi_banana21",
    "url": "https://api.apiyi.com/v1beta/models/gemini-nano-banana-2.1:generateContent",
    "model": "gemini-nano-banana-2.1",
    "key_provider": "apiyi",
    "auth_mode": "bearer",
    "allowed_ratios": ["1:1", "1:4", "4:1", "1:8", "8:1", "2:3", "3:2", "3:4", "4:3", "4:5", "5:4", "9:16", "16:9", "21:9"],
    "allowed_resolutions": ["1K", "2K", "4K"],
    "default_resolution": "1K",
    "supports_text_only_generation": True,
    "supports_mask": False,
    "max_input_images": 17,
    "request_timeout": 360,
    "max_retries": 1,
}


def encode_references(paths):
    originals = [Path(path).read_bytes() for path in paths]
    total = sum(map(len, originals))
    budget = min(int(1.5 * 1024**2), 6 * 1024**2 // max(1, len(paths)))
    result = []
    for path, original in zip(paths, originals):
        data = original
        mime = {".png": "image/png", ".webp": "image/webp", ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}.get(Path(path).suffix.lower(), "image/png")
        try:
            with Image.open(io.BytesIO(original)) as source:
                fmt = source.format
                mime = Image.MIME.get(fmt, mime)
                if len(original) > 1.5 * 1024**2 or total > 6 * 1024**2:
                    image = ImageOps.exif_transpose(source)
                    image.thumbnail((2048, 2048), Image.Resampling.LANCZOS)
                    for _ in range(15):
                        buffer = io.BytesIO()
                        image.save(buffer, format=fmt, quality=90, optimize=True)
                        data = buffer.getvalue()
                        if len(data) <= budget:
                            break
                        scale = min(0.85, math.sqrt(budget / len(data)) * 0.95)
                        image.thumbnail((max(1, int(image.width * scale)), max(1, int(image.height * scale))), Image.Resampling.LANCZOS)
        except Exception:
            data = original
        result.append({"inlineData": {"mimeType": mime, "data": base64.b64encode(data).decode("ascii")}})
    return result


def parse_image(result):
    candidates = result.get("candidates") or []
    candidate = candidates[0] if candidates else {}
    parts = (candidate.get("content") or {}).get("parts") or []
    images = [p["inlineData"] for p in parts if isinstance(p, dict) and isinstance(p.get("inlineData"), dict) and p["inlineData"].get("data")]
    if images:
        return images[-1], None
    usage = result.get("usageMetadata") or {}
    zero_tokens = usage.get("candidatesTokenCount") == 0
    reason = candidate.get("finishReason") or (result.get("promptFeedback") or {}).get("blockReason") or "UNKNOWN"
    # Zero tokens is diagnostic, not sufficient evidence of an unbilled safety block.
    return None, {"zero_candidates_tokens": zero_tokens, "finish_reason": reason,
                  "safety": reason in {"IMAGE_SAFETY", "SAFETY"}}


def generate(prompt, key, ratio, paths, directory, prefix, size, post, observe=None):
    key = os.getenv("APIYI_API_KEY") or key
    if not key:
        raise ValueError("请先填写 API易 Key")
    size = str(size or "1K").upper()
    if size not in MODEL["allowed_resolutions"] or ratio not in MODEL["allowed_ratios"]:
        raise ValueError("API易 Banana 2.1 仅支持 1K/2K/4K 和界面列出的 14 种比例")
    if len(paths) > MODEL["max_input_images"]:
        raise ValueError("API易 Banana 2.1 最多支持 17 张参考图")
    payload = {"contents": [{"role": "user", "parts": [{"text": prompt}] + encode_references(paths)}],
               "generationConfig": {"responseModalities": ["IMAGE"], "imageConfig": {"imageSize": size, "aspectRatio": ratio}}}
    for attempt in range(3):
        # No automatic retry for timeouts/disconnects: the synchronous request may have been billed.
        response, result = post(MODEL["url"], {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}, payload, 360)
        if observe:
            observe(response, result)
        if not 200 <= response.status_code < 300:
            error = result.get("error", {}) if isinstance(result, dict) else {}
            message = error.get("message", "请求失败") if isinstance(error, dict) else str(error)
            raise RuntimeError(f"API 响应错误 ({response.status_code}): {message}")
        image, failure = parse_image(result)
        if image:
            mime = image.get("mimeType", "")
            extension = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp", "image/gif": ".gif"}.get(mime)
            if not extension:
                raise ValueError(f"不支持的响应图片 MIME: {mime}")
            data = base64.b64decode(image["data"], validate=True)
            with Image.open(io.BytesIO(data)) as decoded:
                decoded.verify()
            destination = Path(directory)
            destination.mkdir(parents=True, exist_ok=True)
            output = destination / f"{prefix}_{time.time_ns()}_{uuid.uuid4().hex[:8]}{extension}"
            output.write_bytes(data)
            return str(output)
        if failure["safety"] and attempt < 2:
            time.sleep(1)
            continue
        raise RuntimeError(f"Gemini 未返回图片: candidatesTokenCount为0={failure['zero_candidates_tokens']}, finishReason={failure['finish_reason']}")
