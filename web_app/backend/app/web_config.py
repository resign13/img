from __future__ import annotations

import os

import config as desktop_config

FLOW2API_BASE_URL = os.getenv("FLOW2API_BASE_URL", "https://painting-country-neo-regime.trycloudflare.com").rstrip("/")
FLOW2API_API_KEY = os.getenv("FLOW2API_API_KEY", "xiaocai123")

LOCAL_GEMINI_FLASH_LABEL = "\u672c\u5730gemini-3.1-flash-image"
LOCAL_GEMINI_PRO_LABEL = "\u672c\u5730gemini-3.0-pro-image"
LEGACY_GEMINI_FLASH_LABEL = "gemini_3.1_flash_image_preview"
LEGACY_GEMINI_PRO_LABEL = "gemini_3.0_pro_image_preview"
LEGACY_MODEL_ALIASES = {
    "gemini2": LOCAL_GEMINI_FLASH_LABEL,
    "gemini pro": LOCAL_GEMINI_PRO_LABEL,
    "gemini-3.1-flash-image": LOCAL_GEMINI_FLASH_LABEL,
    "gemini-3.0-pro-image": LOCAL_GEMINI_PRO_LABEL,
}


def _is_desktop_only_gemini_model(label: str, item: dict) -> bool:
    url = str(item.get("url", ""))
    model = str(item.get("model", ""))
    return (
        label in {"gemini2", "gemini pro"}
        or (url.startswith("http://127.0.0.1:8000/") and model in {"gemini-3.1-flash-image", "gemini-3.0-pro-image"})
    )


def normalize_image_model_label(label: str | None) -> str:
    raw_label = (label or "").strip()
    if raw_label in IMAGE_MODELS:
        return raw_label

    normalized = raw_label.lower()
    if normalized in LEGACY_MODEL_ALIASES:
        return LEGACY_MODEL_ALIASES[normalized]
    if "gemini-3.1-flash-image" in normalized:
        return LOCAL_GEMINI_FLASH_LABEL
    if "gemini-3.0-pro-image" in normalized:
        return LOCAL_GEMINI_PRO_LABEL
    return raw_label


def _flow2api_gemini_model_config(model: str) -> dict:
    return {
        "api_type": "gemini_native_image",
        "url": f"{FLOW2API_BASE_URL}/v1beta/models/{model}:generateContent",
        "model": model,
        "key_override": FLOW2API_API_KEY,
        "response_modalities": ["IMAGE"],
        "allowed_ratios": ["1:1", "16:9", "9:16", "4:3", "3:4"],
        "allowed_resolutions": ["1K", "2K"],
        "max_input_images": 9,
        "supports_text_only_generation": True,
    }


IMAGE_MODELS = {
    label: item
    for label, item in desktop_config.IMAGE_MODELS.items()
    if not _is_desktop_only_gemini_model(str(label), item)
}
IMAGE_MODELS.update(
    {
        LEGACY_GEMINI_FLASH_LABEL: _flow2api_gemini_model_config("gemini-3.1-flash-image"),
        LEGACY_GEMINI_PRO_LABEL: _flow2api_gemini_model_config("gemini-3.0-pro-image"),
        LOCAL_GEMINI_FLASH_LABEL: _flow2api_gemini_model_config("gemini-3.1-flash-image"),
        LOCAL_GEMINI_PRO_LABEL: _flow2api_gemini_model_config("gemini-3.0-pro-image"),
    }
)
