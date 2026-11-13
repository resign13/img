from __future__ import annotations

import config as desktop_config
from core.apiyi_banana21 import LABEL as APIYI_BANANA21_LABEL, MODEL as APIYI_BANANA21_MODEL
from urllib.parse import urlparse

LOCAL_GEMINI_FLASH_LABEL = "\u672c\u5730gemini-3.1-flash-image"
LOCAL_GEMINI_PRO_LABEL = "\u672c\u5730gemini-3.0-pro-image"
LEGACY_GEMINI_FLASH_LABEL = "gemini_3.1_flash_image_preview"
LEGACY_GEMINI_PRO_LABEL = "gemini_3.0_pro_image_preview"
LOW_COST_NANO_BANANA_2_LABEL = "\u4f4e\u6210\u672cnano-banana-2"
LOW_COST_NANO_BANANA_PRO_LABEL = "\u4f4e\u6210\u672cnano-banana-pro"
LEGACY_MODEL_ALIASES = {
    LOCAL_GEMINI_FLASH_LABEL: "gemini2",
    LOCAL_GEMINI_PRO_LABEL: "gemini pro",
    "gemini-3.1-flash-image": "gemini2",
    "gemini-3.0-pro-image": "gemini pro",
    LOW_COST_NANO_BANANA_2_LABEL: LEGACY_GEMINI_FLASH_LABEL,
    LOW_COST_NANO_BANANA_PRO_LABEL: LEGACY_GEMINI_PRO_LABEL,
}

def normalize_image_model_label(label: str | None) -> str:
    raw_label = (label or "").strip()
    if raw_label in IMAGE_MODELS:
        return raw_label

    normalized = raw_label.lower()
    if normalized in LEGACY_MODEL_ALIASES:
        return LEGACY_MODEL_ALIASES[normalized]
    if "gemini-3.1-flash-image" in normalized:
        return "gemini2"
    if "gemini-3.0-pro-image" in normalized:
        return "gemini pro"
    return raw_label


IMAGE_MODELS = {
    str(label): dict(item)
    for label, item in desktop_config.IMAGE_MODELS.items()
}

# Keep web releases independent of the desktop sources installed on the server.
IMAGE_MODELS.update({
    APIYI_BANANA21_LABEL: dict(APIYI_BANANA21_MODEL),
    "API易 gpt-image-2.6-all": {
        "api_type": "gpt_image",
        "url": "https://api.apiyi.com/v1/images/edits",
        "text_url": "https://api.apiyi.com/v1/images/generations",
        "model": "gpt-image-2.6-all",
        "key_provider": "apiyi",
        "gpt_parameter_mode": "apiyi_26",
        "allowed_ratios": ["1:1", "5:4", "4:5", "4:3", "3:4", "3:2", "2:3", "16:9", "9:16", "21:9"],
        "allowed_resolutions": ["1K", "2K", "4K"],
        "max_input_images": 16,
        "supports_text_only_generation": True,
        "quality": "high",
        "allowed_qualities": ["auto", "medium", "high"],
        "output_format": "png",
        "response_format": "b64_json",
        "request_timeout": 600,
        "max_retries": 1,
    },
    "gemini-nano-banana-2.1": {
        "api_type": "gemini_native_image",
        "url": "https://meinianda.top/v1beta/models/gemini-nano-banana-2.1:generateContent",
        "model": "gemini-nano-banana-2.1",
        "key_provider": "meinianda",
        "auth_mode": "x-goog-api-key",
        "response_modalities": ["IMAGE"],
        "allowed_ratios": ["1:1", "16:9", "9:16", "21:9", "4:3", "3:4", "3:2", "2:3", "4:5", "5:4"],
        "allowed_resolutions": ["1K", "2K", "4K"],
        "max_input_images": 9,
        "supports_text_only_generation": True,
        "request_timeout": 600,
        "max_retries": 1,
    },
    "meinianda gpt-image-2.6-flare": {
        "api_type": "gpt_image",
        "url": "https://meinianda.top/v1/images/edits",
        "text_url": "https://meinianda.top/v1/images/generations",
        "model": "gpt-image-2.6-flare",
        "key_provider": "gpt_image_25",
        "allowed_ratios": ["1:1", "5:4", "4:5", "4:3", "3:4", "3:2", "2:3", "16:9", "9:16", "21:9"],
        "allowed_resolutions": ["1K", "2K", "4K"],
        "max_input_images": 16,
        "supports_text_only_generation": True,
        "quality": "high",
        "output_format": "png",
        "response_format": "b64_json",
        "request_timeout": 600,
        "max_retries": 1,
    },
})
REMOVED_IMAGE_MODEL_LABELS = {
    "API易官转 gpt-image-2", "gpt-image-2",
    "API易 gpt-image-2.5-all", "API易 gpt-image-2.5-vip", "gpt-image-2.5-sunburst",
    "kuai便宜banana2", "kuai便宜banana pro",
}
for _label, _model in list(IMAGE_MODELS.items()):
    if _label in REMOVED_IMAGE_MODEL_LABELS or _model.get("model") in {
        "gpt-image-2.5-all", "gpt-image-2.5-vip", "gpt-image-2.5-sunburst",
    }:
        IMAGE_MODELS.pop(_label)

PROVIDER_ENV_VARS = {
    "apiyi": "WEB_APIYI_KEY",
    "meinianda": "WEB_MEINIANDA_KEY",
    "g_aisc": "WEB_G_AISC_KEY",
    "gpt_image_25": "WEB_GPT_IMAGE25_KEY",
}


def provider_for_model(model_config: dict) -> str | None:
    key_provider = model_config.get("key_provider")
    if key_provider in PROVIDER_ENV_VARS:
        return key_provider
    host = (urlparse(str(model_config.get("url") or "")).hostname or "").lower()
    if host == "api.apiyi.com":
        return "apiyi"
    if host == "meinianda.top":
        return "meinianda"
    if host == "sub.g-aisc.com":
        return "g_aisc"
    return None


# Ignore legacy embedded credentials even on an installation with an old
# model_channels.json file. Only server environment variables supply these keys.
for _model in IMAGE_MODELS.values():
    if provider_for_model(_model):
        _model.pop("key_override", None)
