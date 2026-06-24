import logging
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

    for filename in ("config.json", "history_data.json", "styles.json", "templates.json"):
        src = os.path.join(PACKAGED_DATA_DIR, filename)
        dst = os.path.join(DATA_DIR, filename)
        if os.path.exists(src) and not os.path.exists(dst):
            shutil.copy2(src, dst)


_seed_runtime_data_files()


HISTORY_FILE = os.path.join(DATA_DIR, "history_data.json")
STYLES_FILE = os.path.join(DATA_DIR, "styles.json")
TEMPLATES_FILE = os.path.join(DATA_DIR, "templates.json")
CONFIG_FILE = os.path.join(DATA_DIR, "config.json")
LOG_FILE = os.path.join(BASE_DIR, "app_debug.log")


LLM_API_BASE_URL = "https://api.apiyi.com"
LLM_MODEL_NAME = "gemini-3-pro-preview"
LLM_API_URL = f"{LLM_API_BASE_URL}/v1beta/models/{LLM_MODEL_NAME}:generateContent"
IMAGE_API_URL = "https://api.apiyi.com/v1beta/models/gemini-3.1-flash-image-preview:generateContent"
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
HANCAT_IMAGE_KEY = os.getenv("HANCAT_IMAGE_KEY", "")
MINGYU_NANO_BANANA_KEY = os.getenv("MINGYU_NANO_BANANA_KEY", "")
MANJU_GEMINI_IMAGE_KEY = os.getenv("MANJU_GEMINI_IMAGE_KEY", "")


IMAGE_MODELS = {
    "nano banana2": {
        "api_type": "google_image",
        "url": "https://api.apiyi.com/v1beta/models/gemini-3.1-flash-image-preview:generateContent",
        "supports_text_only_generation": True,
    },
    "nano banana pro": {
        "api_type": "google_image",
        "url": "https://api.apiyi.com/v1beta/models/gemini-3-pro-image-preview:generateContent",
        "supports_text_only_generation": True,
    },
    "gemini2": {
        "api_type": "chat_completions_task",
        "url": "https://manjuapi.com/v1/chat/completions",
        "text_url": "https://manjuapi.com/v1/images/generations",
        "task_base_url": "https://manjuapi.com",
        "model": "Nano Banana 2",
        "model_4k": "Nano Banana 2 4K",
        "key_override": MANJU_GEMINI_IMAGE_KEY,
        "allowed_ratios": ["1:1", "4:3", "3:4", "3:2", "2:3", "16:9", "9:16"],
        "allowed_resolutions": ["1K", "2K", "4K"],
        "max_input_images": 10,
        "supports_text_only_generation": True,
    },
    "gemini pro": {
        "api_type": "chat_completions_task",
        "url": "https://manjuapi.com/v1/chat/completions",
        "text_url": "https://manjuapi.com/v1/images/generations",
        "task_base_url": "https://manjuapi.com",
        "model": "gemini-3.0-pro-image",
        "model_4k": "gemini-3.0-pro-image 4K",
        "key_override": MANJU_GEMINI_IMAGE_KEY,
        "allowed_ratios": ["1:1", "4:3", "3:4", "3:2", "2:3", "16:9", "9:16"],
        "allowed_resolutions": ["1K", "2K", "4K"],
        "max_input_images": 10,
        "supports_text_only_generation": True,
    },
    "gpt-image-2": {
        "api_type": "gpt_image_edits",
        "url": "https://api.apiyi.com/v1/images/edits",
        "model": "gpt-image-2-all",
        "supports_ratio_selection": False,
        "supports_resolution_selection": False,
    },
    "gemini_3.0_pro_image_preview": {
        "api_type": "google_image",
        "url": "https://img-api.xn--1ys141f4ks.com/v1beta/models/gemini_3.0_pro_image_preview:generateContent",
        "model": "gemini_3.0_pro_image_preview",
        "key_override": HANCAT_IMAGE_KEY,
        "include_user_role": True,
        "response_modalities": ["TEXT", "IMAGE"],
        "allowed_ratios": ["1:1", "16:9", "9:16", "21:9", "4:3", "3:4", "3:2", "2:3", "4:5", "5:4"],
        "allowed_resolutions": ["1K", "2K", "4K"],
        "max_input_images": 10,
        "supports_text_only_generation": True,
    },
    "gemini_3.1_flash_image_preview": {
        "api_type": "google_image",
        "url": "https://img-api.xn--1ys141f4ks.com/v1beta/models/gemini_3.1_flash_image_preview:generateContent",
        "model": "gemini_3.1_flash_image_preview",
        "key_override": HANCAT_IMAGE_KEY,
        "include_user_role": True,
        "response_modalities": ["TEXT", "IMAGE"],
        "allowed_ratios": ["1:1", "16:9", "9:16", "21:9", "4:3", "3:4", "3:2", "2:3", "4:5", "5:4"],
        "allowed_resolutions": ["1K", "2K", "4K"],
        "max_input_images": 10,
        "supports_text_only_generation": True,
    },
}

IMAGE_RESOLUTIONS = ["1K", "2K", "4K"]
SORA_ALLOWED_RATIOS = ["2:3", "3:2", "1:1"]


RATIO_MAP = {
    "1:1 (正方形 - 通用主图)": "1:1",
    "3:4 (竖屏 - 电商详情页)": "3:4",
    "4:3 (横屏 - 传统展示)": "4:3",
    "9:16 (全竖屏 - 手机/Stories)": "9:16",
    "16:9 (宽屏 - 视频封面/Banner)": "16:9",
    "2:3 (竖屏 - 经典摄影)": "2:3",
    "3:2 (横屏 - 经典摄影)": "3:2",
    "4:5 (竖屏 - 社媒商品图)": "4:5",
    "5:4 (横屏 - 大画幅展示)": "5:4",
    "21:9 (超宽屏 - 电影感 Banner)": "21:9",
    "4:1 (超宽横幅 - Gemini Flash)": "4:1",
    "8:1 (极宽横幅 - Gemini Flash)": "8:1",
    "1:4 (超高竖幅 - Gemini Flash)": "1:4",
    "1:8 (极高竖幅 - Gemini Flash)": "1:8",
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
