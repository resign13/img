from __future__ import annotations

import os
import re
import uuid
from dataclasses import dataclass

from werkzeug.datastructures import FileStorage

import config


@dataclass
class WebGenerationSettings:
    llm_key: str
    img_key: str
    img_key_line2: str
    image_model: str
    image_resolution: str
    ratio_label: str
    compress_enabled: bool = False
    compress_target: float = 2.0
    session_id: str = "anonymous"

    @property
    def model_config(self) -> dict:
        return config.IMAGE_MODELS.get(self.image_model, {})

    @property
    def ratio_value(self) -> str:
        return config.RATIO_MAP.get(self.ratio_label, "3:4")

    @property
    def effective_image_key(self) -> str:
        if self.model_config.get("key_slot") == "line2":
            return (self.img_key_line2 or self.img_key).strip()
        return self.img_key.strip()


def _sanitize_session_id(value: str | None) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_-]", "", (value or "").strip())
    return cleaned[:64] or "anonymous"


def _load_default_keys() -> dict:
    from core import data_manager

    defaults = data_manager.load_json_data(config.CONFIG_FILE, {})
    return {
        "llm_key": defaults.get("llm_key", ""),
        "img_key": defaults.get("img_key", ""),
        "img_key_line2": defaults.get("img_key_line2", ""),
        "image_model": defaults.get("image_model", list(config.IMAGE_MODELS.keys())[0]),
        "image_resolution": defaults.get("image_resolution", getattr(config, "IMAGE_DEFAULT_RESOLUTION", "1K")),
        "ratio": defaults.get("ratio", list(config.RATIO_MAP.keys())[0]),
        "compress_enable": bool(defaults.get("compress_enable", False)),
        "compress_target": float(defaults.get("compress_target", "2.0") or 2.0),
    }


def parse_generation_settings(request) -> WebGenerationSettings:
    defaults = _load_default_keys()
    image_model = request.form.get("image_model", defaults["image_model"]).strip()
    if image_model not in config.IMAGE_MODELS:
        image_model = defaults["image_model"]

    image_resolution = request.form.get("image_resolution", defaults["image_resolution"]).strip()
    ratio_label = request.form.get("ratio_label", defaults["ratio"]).strip()

    if ratio_label not in config.RATIO_MAP:
        ratio_label = defaults["ratio"]

    compress_raw = request.form.get("compress_enabled", str(defaults["compress_enable"])).strip().lower()
    compress_enabled = compress_raw in {"1", "true", "yes", "on"}

    try:
        compress_target = float(request.form.get("compress_target", defaults["compress_target"]))
    except (TypeError, ValueError):
        compress_target = float(defaults["compress_target"])

    return WebGenerationSettings(
        llm_key=defaults["llm_key"],
        img_key=defaults["img_key"],
        img_key_line2=defaults["img_key_line2"],
        image_model=image_model,
        image_resolution=image_resolution,
        ratio_label=ratio_label,
        compress_enabled=compress_enabled,
        compress_target=compress_target,
        session_id=_sanitize_session_id(request.form.get("session_id") or request.headers.get("X-Batchpic-Session")),
    )


def _ensure_upload_dir(subdir: str, session_id: str = "anonymous") -> str:
    path = os.path.join(config.DEFAULT_OUTPUT_DIR, "web_runtime", "sessions", _sanitize_session_id(session_id), "uploads", subdir)
    os.makedirs(path, exist_ok=True)
    return path


def _save_file(file_obj: FileStorage, target_dir: str, prefix: str) -> str:
    original_name = file_obj.filename or f"{prefix}.png"
    _, extension = os.path.splitext(original_name)
    extension = extension.lower() if extension else ".png"
    if extension not in {".png", ".jpg", ".jpeg", ".webp"}:
        extension = ".png"
    file_name = f"{prefix}_{uuid.uuid4().hex[:8]}{extension}"
    target_path = os.path.join(target_dir, file_name)
    file_obj.save(target_path)
    return target_path


def parse_uploaded_files(files: list[FileStorage], subdir: str, prefix: str, session_id: str = "anonymous") -> list[str]:
    valid_files = [file_obj for file_obj in files if file_obj and getattr(file_obj, "filename", "")]
    if not valid_files:
        return []
    target_dir = _ensure_upload_dir(subdir, session_id)
    return [_save_file(file_obj, target_dir, prefix) for file_obj in valid_files]


def parse_single_uploaded_file(file_obj: FileStorage | None, subdir: str, prefix: str, session_id: str = "anonymous") -> str:
    if not file_obj or not getattr(file_obj, "filename", ""):
        raise ValueError("缺少上传图片。")
    target_dir = _ensure_upload_dir(subdir, session_id)
    return _save_file(file_obj, target_dir, prefix)
