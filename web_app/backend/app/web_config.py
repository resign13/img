from __future__ import annotations

import config as desktop_config
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

PROVIDER_ENV_VARS = {
    "apiyi": "WEB_APIYI_KEY",
    "meinianda": "WEB_MEINIANDA_KEY",
    "g_aisc": "WEB_G_AISC_KEY",
}


def provider_for_model(model_config: dict) -> str | None:
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
