from __future__ import annotations

import os

import config
from app import web_config
from core import data_manager


def _get_default_ratio_label() -> str:
    labels = list(config.RATIO_MAP.keys())
    return labels[0] if labels else "1:1"


def _configured_value(defaults: dict, config_key: str, env_key: str) -> str:
    return (os.getenv(env_key) or defaults.get(config_key, "") or "").strip()


def get_public_config() -> dict:
    defaults = data_manager.load_json_data(config.CONFIG_FILE, {})
    visible_model_labels = list(web_config.IMAGE_MODELS.keys())
    selected_model = defaults.get("image_model")
    if selected_model not in visible_model_labels:
        selected_model = visible_model_labels[0] if visible_model_labels else ""

    public_models = []
    for label, item in web_config.IMAGE_MODELS.items():
        public_models.append(
            {
                "label": label,
                "supports_ratio_selection": item.get("supports_ratio_selection", True),
                "supports_resolution_selection": item.get("supports_resolution_selection", True),
                "supports_text_only_generation": item.get("supports_text_only_generation", False),
                "allowed_ratios": item.get("allowed_ratios", []),
                "allowed_resolutions": item.get("allowed_resolutions", config.IMAGE_RESOLUTIONS),
            }
        )

    return {
        "models": public_models,
        "ratio_options": [{"label": label, "value": value} for label, value in config.RATIO_MAP.items()],
        "key_status": {
            "llm_key_configured": bool(_configured_value(defaults, "llm_key", "LLM_KEY")),
            "img_key_configured": bool(_configured_value(defaults, "img_key", "IMG_KEY")),
            "img_key_line2_configured": bool(_configured_value(defaults, "img_key_line2", "IMG_KEY_LINE2")),
        },
        "defaults": {
            "image_model": selected_model,
            "image_resolution": defaults.get("image_resolution", getattr(config, "IMAGE_DEFAULT_RESOLUTION", "1K")),
            "ratio": defaults.get("ratio", _get_default_ratio_label()),
            "compress_enable": bool(defaults.get("compress_enable", False)),
            "compress_target": float(defaults.get("compress_target", "2.0") or 2.0),
            "style": defaults.get("style", ""),
            "template": defaults.get("template", ""),
            "extra_info": defaults.get("extra_info", ""),
            "output_path": defaults.get("output_path", config.DEFAULT_OUTPUT_DIR),
        },
        "styles": data_manager.load_json_data(config.STYLES_FILE, config.DEFAULT_STYLES),
        "templates": data_manager.load_json_data(config.TEMPLATES_FILE, config.DEFAULT_TEMPLATES),
    }
