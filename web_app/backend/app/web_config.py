from __future__ import annotations

import config as desktop_config

WEB_GEMINI_KEY = "sk-XPrpLgc0ICA97q4WEuKPfCEIAIUgcIzEaKWitIPwMtxGtY2D"

IMAGE_MODELS = dict(desktop_config.IMAGE_MODELS)
IMAGE_MODELS.update(
    {
        "gemini2": {
            "api_type": "gemini_native_image",
            "url": "https://llm.zerofall.top/v1beta/models/gemini-3.1-flash-image-preview:generateContent",
            "model": "gemini-3.1-flash-image-preview",
            "key_override": WEB_GEMINI_KEY,
            "allowed_ratios": ["1:1", "16:9", "9:16", "4:3", "3:4", "3:2", "2:3"],
            "allowed_resolutions": ["1K", "2K", "4K"],
            "max_input_images": 9,
            "supports_text_only_generation": True,
        },
        "gemini pro": {
            "api_type": "gemini_native_image",
            "url": "https://llm.zerofall.top/v1beta/models/gemini-3-pro-image-preview:generateContent",
            "model": "gemini-3-pro-image-preview",
            "key_override": WEB_GEMINI_KEY,
            "allowed_ratios": ["1:1", "16:9", "9:16", "4:3", "3:4", "3:2", "2:3"],
            "allowed_resolutions": ["1K", "2K", "4K"],
            "max_input_images": 9,
            "supports_text_only_generation": True,
        },
    }
)
