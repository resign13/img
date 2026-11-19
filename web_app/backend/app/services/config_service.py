from __future__ import annotations

import os

import config
from app import web_config
from core import data_manager


def _get_default_ratio_label() -> str:
    labels = list(config.RATIO_MAP.keys())
    return labels[0] if labels else "1:1"


def get_public_config() -> dict:
    defaults = data_manager.load_json_data(config.CONFIG_FILE, {})
    visible_model_labels = list(web_config.IMAGE_MODELS.keys())
    selected_model = web_config.normalize_image_model_label(defaults.get("image_model"))
    if selected_model not in visible_model_labels:
        selected_model = visible_model_labels[0] if visible_model_labels else ""
    selected_config = web_config.IMAGE_MODELS.get(selected_model, {})
    selected_ratio = web_config.normalize_ratio(defaults.get("ratio"), selected_config)
    if selected_ratio is None:
        selected_ratio = (selected_config.get("allowed_ratios") or [_get_default_ratio_label()])[0]

    public_models = []
    for label, item in web_config.IMAGE_MODELS.items():
        public_models.append(
            {
                "label": label,
                "supports_ratio_selection": item.get("supports_ratio_selection", True),
                "supports_resolution_selection": item.get("supports_resolution_selection", True),
                "supports_text_only_generation": item.get("supports_text_only_generation", False),
                "allowed_ratios": item.get("allowed_ratios", []),
                "custom_ratio_max": item.get("custom_ratio_max"),
                "allowed_resolutions": item.get("allowed_resolutions", config.IMAGE_RESOLUTIONS),
            }
        )

    ratio_options = dict(config.RATIO_MAP)
    for model in web_config.IMAGE_MODELS.values():
        for ratio in model.get("allowed_ratios", []):
            ratio_options.setdefault(ratio, ratio)

    return {
        "models": public_models,
        "ratio_options": [{"label": label, "value": value} for label, value in ratio_options.items()],
        "key_status": {
            f"{provider}_key_configured": bool((os.getenv(env_name) or "").strip())
            for provider, env_name in web_config.PROVIDER_ENV_VARS.items()
        },
        "defaults": {
            "image_model": selected_model,
            "image_resolution": defaults.get("image_resolution", getattr(config, "IMAGE_DEFAULT_RESOLUTION", "1K")),
            "ratio": selected_ratio,
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
