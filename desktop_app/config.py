import logging
import json
import os
import shutil
import sys


if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(sys.executable)
    RESOURCE_BASE_DIR = getattr(sys, "_MEIPASS", BASE_DIR)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    RESOURCE_BASE_DIR = BASE_DIR


DATA_DIR = os.path.join(BASE_DIR, "data")
PACKAGED_DATA_DIR = os.path.join(RESOURCE_BASE_DIR, "data")
DEFAULT_OUTPUT_DIR = os.path.join(BASE_DIR, "output")
CACHE_DIR = os.path.join(DEFAULT_OUTPUT_DIR, "_white_bg_cache")

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(DEFAULT_OUTPUT_DIR, exist_ok=True)
os.makedirs(CACHE_DIR, exist_ok=True)


def _seed_runtime_data_files():
    if not os.path.isdir(PACKAGED_DATA_DIR):
        return

    for filename in ("config.json", "history_data.json", "model_channels.json", "styles.json", "templates.json"):
        src = os.path.join(PACKAGED_DATA_DIR, filename)
        dst = os.path.join(DATA_DIR, filename)
        if os.path.exists(src) and not os.path.exists(dst):
            shutil.copy2(src, dst)


_seed_runtime_data_files()


HISTORY_FILE = os.path.join(DATA_DIR, "history_data.json")
STYLES_FILE = os.path.join(DATA_DIR, "styles.json")
TEMPLATES_FILE = os.path.join(DATA_DIR, "templates.json")
CONFIG_FILE = os.path.join(DATA_DIR, "config.json")
MODEL_CHANNELS_FILE = os.path.join(DATA_DIR, "model_channels.json")
LOG_FILE = os.path.join(BASE_DIR, "app_debug.log")


LLM_API_BASE_URL = "https://api.apiyi.com"
LLM_MODEL_NAME = "gemini-3-pro-preview"
LLM_API_URL = f"{LLM_API_BASE_URL}/v1beta/models/{LLM_MODEL_NAME}:generateContent"
IMAGE_API_URL = "https://api.apiyi.com/v1beta/models/gemini-3.1-flash-image-preview:generateContent"
APP_VERSION = os.getenv("APP_VERSION", "1.0.12")
UPDATE_MANIFEST_URL = os.getenv("UPDATE_MANIFEST_URL", "https://design.smawell.shop/desktop/latest.json")
IMAGE_DEFAULT_RESOLUTION = "1K"
IMAGE_GEN_TIMEOUT = 300
MAX_CONCURRENT_WORKERS = 3
API_UPLOAD_MAX_SIDE = 1600
API_UPLOAD_MAX_BYTES = 1024 * 1024
IMG_API_MAX_RETRIES = 3
IMG_API_RETRY_BASE_DELAY = 2.0
LLM_API_MAX_RETRIES = 3
LLM_API_RETRY_BASE_DELAY = 2.0
CATKING_ROUTE3_KEY = os.getenv("CATKING_ROUTE3_KEY", "")
HANCAT_IMAGE_KEY = os.getenv("HANCAT_IMAGE_KEY", "sk-dOGl8b4lzskGp9qItvQ6YF4gnDhHXOdNT35MuqjC2z1mVyQD")
MINGYU_NANO_BANANA_KEY = os.getenv("MINGYU_NANO_BANANA_KEY", "sk-T7i3ssqEdBbAD0P0lqnG6Uk3mWhoHJ3XCidZXmtPltXecHv5")
MANJU_GEMINI_IMAGE_KEY = os.getenv("MANJU_GEMINI_IMAGE_KEY", "sk-XPrpLgc0ICA97q4WEuKPfCEIAIUgcIzEaKWitIPwMtxGtY2D")


IMAGE_MODELS = {
    "nano banana2": {
        "api_type": "gemini_native_image",
        "url": "https://api.apiyi.com/v1beta/models/gemini-3.1-flash-image-preview:generateContent",
        "model": "gemini-3.1-flash-image-preview",
        "auth_mode": "bearer",
        "response_modalities": ["IMAGE"],
        "allowed_ratios": ["1:1", "16:9", "9:16", "21:9", "4:3", "3:4", "3:2", "2:3", "4:5", "5:4"],
        "allowed_resolutions": ["512", "1K", "2K", "4K"],
        "max_input_images": 9,
        "supports_text_only_generation": True,
    },
    "nano banana pro": {
        "api_type": "gemini_native_image",
        "url": "https://api.apiyi.com/v1beta/models/gemini-3-pro-image-preview:generateContent",
        "model": "gemini-3-pro-image-preview",
        "auth_mode": "bearer",
        "response_modalities": ["IMAGE"],
        "allowed_ratios": ["1:1", "16:9", "9:16", "21:9", "4:3", "3:4", "3:2", "2:3", "4:5", "5:4"],
        "allowed_resolutions": ["1K", "2K", "4K"],
        "max_input_images": 9,
        "supports_text_only_generation": True,
    },
    "gemini2": {
        "api_type": "gemini_native_image",
        "url": "https://meinianda.top/v1beta/models/gemini-3.1-flash-image:generateContent",
        "model": "gemini-3.1-flash-image",
        "key_override": "sk-UTvMtBCMj2BtILEWf2UEOZg6Bft8Rorcn1zLjw9gVRDKuIVV",
        "auth_mode": "x-goog-api-key",
        "response_modalities": ["IMAGE"],
        "allowed_ratios": ["1:1", "16:9", "9:16", "4:3", "3:4", "3:2", "2:3"],
        "allowed_resolutions": ["1K", "2K", "4K"],
        "max_input_images": 9,
        "supports_text_only_generation": True,
    },
    "gemini pro": {
        "api_type": "gemini_native_image",
        "url": "https://meinianda.top/v1beta/models/gemini-3-pro-image:generateContent",
        "model": "gemini-3-pro-image",
        "key_override": "sk-UTvMtBCMj2BtILEWf2UEOZg6Bft8Rorcn1zLjw9gVRDKuIVV",
        "auth_mode": "x-goog-api-key",
        "response_modalities": ["IMAGE"],
        "allowed_ratios": ["1:1", "16:9", "9:16", "4:3", "3:4", "3:2", "2:3"],
        "allowed_resolutions": ["1K", "2K", "4K"],
        "max_input_images": 9,
        "supports_text_only_generation": True,
    },
    "local gemini-3.1-flash-image": {
        "api_type": "gemini_native_image",
        "url": "http://127.0.0.1:8000/models/gemini-3.1-flash-image:generateContent",
        "model": "gemini-3.1-flash-image",
        "key_override": "xiaocai123",
        "allowed_ratios": ["1:1", "16:9", "9:16", "4:3", "3:4"],
        "allowed_resolutions": ["1K", "2K"],
        "max_input_images": 9,
        "supports_text_only_generation": True,
    },
    "local gemini-3.0-pro-image": {
        "api_type": "gemini_native_image",
        "url": "http://127.0.0.1:8000/models/gemini-3.0-pro-image:generateContent",
        "model": "gemini-3.0-pro-image",
        "key_override": "xiaocai123",
        "allowed_ratios": ["1:1", "16:9", "9:16", "4:3", "3:4"],
        "allowed_resolutions": ["1K", "2K"],
        "max_input_images": 9,
        "supports_text_only_generation": True,
    },
    "gpt-image-2": {
        "api_type": "chat_completions_task",
        "url": "https://manjuapi.com/v1/chat/completions",
        "text_url": "https://manjuapi.com/v1/images/generations",
        "task_base_url": "https://manjuapi.com",
        "model": "gpt-image-2",
        "key_override": MANJU_GEMINI_IMAGE_KEY,
        "allowed_ratios": ["1:1", "5:4", "4:5", "4:3", "3:4", "3:2", "2:3", "16:9", "9:16", "21:9"],
        "allowed_resolutions": ["1K", "2K", "4K"],
        "max_input_images": 10,
        "supports_text_only_generation": True,
    },
    "gemini_3.0_pro_image_preview": {
        "api_type": "gemini_native_image",
        "url": "https://mingyu.it.com/v1beta/models/nano-banana-pro:generateContent",
        "model": "nano-banana-pro",
        "key_override": MINGYU_NANO_BANANA_KEY,
        "auth_mode": "bearer",
        "response_modalities": ["IMAGE"],
        "allowed_ratios": ["1:1", "16:9", "9:16", "21:9", "4:3", "3:4", "3:2", "2:3", "4:5", "5:4"],
        "allowed_resolutions": ["1K", "2K", "4K"],
        "max_input_images": 9,
        "supports_text_only_generation": True,
    },
    "gemini_3.1_flash_image_preview": {
        "api_type": "gemini_native_image",
        "url": "https://mingyu.it.com/v1beta/models/nano-banana-2:generateContent",
        "model": "nano-banana-2",
        "key_override": MINGYU_NANO_BANANA_KEY,
        "auth_mode": "bearer",
        "response_modalities": ["IMAGE"],
        "allowed_ratios": ["1:1", "16:9", "9:16", "21:9", "4:3", "3:4", "3:2", "2:3", "4:5", "5:4"],
        "allowed_resolutions": ["1K", "2K", "4K"],
        "max_input_images": 9,
        "supports_text_only_generation": True,
    },
}


def _load_external_image_models(base_models):
    if not os.path.exists(MODEL_CHANNELS_FILE):
        return base_models

    try:
        with open(MODEL_CHANNELS_FILE, "r", encoding="utf-8") as file_obj:
            payload = json.load(file_obj)
    except Exception as exc:
        print(f"[WARN] Failed to load model channels file: {exc}")
        return base_models

    if not isinstance(payload, dict):
        return base_models

    raw_models = payload.get("models", payload)
    if not isinstance(raw_models, dict):
        return base_models

    should_merge = bool(payload.get("merge", True))
    models = dict(base_models) if should_merge else {}
    for label, model_config in raw_models.items():
        if not isinstance(label, str) or not isinstance(model_config, dict):
            continue

        if model_config.get("enabled") is False:
            models.pop(label, None)
            continue

        normalized_config = dict(model_config)
        normalized_config.pop("enabled", None)
        key_env = str(normalized_config.pop("key_override_env", "") or "").strip()
        if key_env:
            normalized_config["key_override"] = os.getenv(key_env, normalized_config.get("key_override", ""))
        models[label] = normalized_config

    return models


IMAGE_MODELS = _load_external_image_models(IMAGE_MODELS)

HIDDEN_IMAGE_MODEL_LABELS = {
    "local gemini-3.1-flash-image",
    "local gemini-3.0-pro-image",
}
for _hidden_model_label in HIDDEN_IMAGE_MODEL_LABELS:
    IMAGE_MODELS.pop(_hidden_model_label, None)

IMAGE_RESOLUTIONS = ["1K", "2K", "4K"]
SORA_ALLOWED_RATIOS = ["2:3", "3:2", "1:1"]


RATIO_MAP = {
    "1:1": "1:1",
    "3:4": "3:4",
    "4:3": "4:3",
    "9:16": "9:16",
    "16:9": "16:9",
    "2:3": "2:3",
    "3:2": "3:2",
    "4:5": "4:5",
    "5:4": "5:4",
    "21:9": "21:9",
    "4:1": "4:1",
    "8:1": "8:1",
    "1:4": "1:4",
    "1:8": "1:8",
}


DEFAULT_STYLES = {}
DEFAULT_TEMPLATES = {}


def init_system_settings():
    os.environ["HTTP_PROXY"] = ""
    os.environ["HTTPS_PROXY"] = ""
    os.environ["http_proxy"] = ""
    os.environ["https_proxy"] = ""


logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    encoding="utf-8",
    filemode="a",
)


def log_to_file(message, level="INFO"):
    print(f"[{level}] {message}")
    if level == "ERROR":
        logging.error(message)
    else:
        logging.info(message)
