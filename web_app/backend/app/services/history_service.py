from __future__ import annotations

import json
import os
import shutil
import threading
import time
from datetime import datetime

from PIL import Image, ImageOps

import config

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
THUMBNAIL_MAX_SIZE = (420, 260)
RESULT_MODULE_LABELS = {
    "scene_results": "场景生图",
    "replacement_results": "爆款替换",
    "multi_reference_results": "多参考图生图",
    "face_swap_results": "批量换头",
}
HISTORY_CLEANUP_INTERVAL_SECONDS = int(os.getenv("BATCHPIC_HISTORY_CLEANUP_SECONDS", str(12 * 60 * 60)))
_cleanup_started = False
_cleanup_lock = threading.Lock()


def _runtime_base() -> str:
    return os.path.join(config.DEFAULT_OUTPUT_DIR, "web_runtime")


def _metadata_path(image_path: str) -> str:
    return f"{image_path}.meta.json"


def write_result_metadata(path: str, title: str, prompt: str, source_name: str = "") -> None:
    try:
        data = {
            "title": title,
            "prompt": prompt,
            "source_name": source_name,
            "created_at": time.time(),
        }
        with open(_metadata_path(path), "w", encoding="utf-8") as file_obj:
            json.dump(data, file_obj, ensure_ascii=False, indent=2)
    except Exception:
        # Metadata is helpful for history, but image generation should not fail because of it.
        return


def _load_metadata(image_path: str) -> dict:
    try:
        with open(_metadata_path(image_path), "r", encoding="utf-8") as file_obj:
            data = json.load(file_obj)
            return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _iso_from_timestamp(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp).isoformat(timespec="seconds")


def _thumbnail_relative_path(relative_path: str) -> str:
    stem, _extension = os.path.splitext(relative_path)
    return f"_thumbs/{stem}.jpg"


def _ensure_thumbnail(image_path: str, relative_path: str) -> str:
    base_dir = _runtime_base()
    thumb_relative = _thumbnail_relative_path(relative_path)
    thumb_path = os.path.join(base_dir, thumb_relative.replace("/", os.sep))

    try:
        source_mtime = os.path.getmtime(image_path)
        if os.path.exists(thumb_path) and os.path.getmtime(thumb_path) >= source_mtime:
            return thumb_relative

        os.makedirs(os.path.dirname(thumb_path), exist_ok=True)
        with Image.open(image_path) as image:
            image = ImageOps.exif_transpose(image)
            image.thumbnail(THUMBNAIL_MAX_SIZE)
            if image.mode in ("RGBA", "LA", "P"):
                if image.mode == "P":
                    image = image.convert("RGBA")
                background = Image.new("RGB", image.size, (28, 28, 28))
                alpha = image.getchannel("A") if image.mode in ("RGBA", "LA") else None
                background.paste(image.convert("RGBA"), mask=alpha)
                image = background
            elif image.mode != "RGB":
                image = image.convert("RGB")
            image.save(thumb_path, format="JPEG", quality=72, optimize=True)
        return thumb_relative
    except Exception:
        return relative_path


def _build_history_item(path: str, include_thumbnail: bool = False) -> dict | None:
    base_dir = _runtime_base()
    relative_path = os.path.relpath(path, base_dir).replace("\\", "/")
    parts = relative_path.split("/")
    if "runs" not in parts:
        return None

    parent_dir = os.path.basename(os.path.dirname(path))
    if parent_dir not in RESULT_MODULE_LABELS:
        return None

    stat = os.stat(path)
    metadata = _load_metadata(path)
    created_at = float(metadata.get("created_at") or stat.st_mtime)
    session_id = parts[1] if len(parts) > 2 and parts[0] == "sessions" else "unknown"
    file_name = os.path.basename(path)
    thumb_relative = _ensure_thumbnail(path, relative_path) if include_thumbnail else relative_path

    return {
        "id": relative_path,
        "url": f"/generated/{relative_path}",
        "thumbnail_url": f"/generated/{thumb_relative}",
        "file_name": file_name,
        "title": metadata.get("title") or file_name,
        "prompt": metadata.get("prompt") or "",
        "source_name": metadata.get("source_name") or "",
        "module": parent_dir,
        "module_label": RESULT_MODULE_LABELS[parent_dir],
        "session_id": session_id,
        "session_label": session_id[:8],
        "created_at": created_at,
        "created_at_text": _iso_from_timestamp(created_at),
        "size_bytes": stat.st_size,
    }


def list_generated_history(limit: int = 12, offset: int = 0) -> dict:
    base_dir = _runtime_base()
    if not os.path.isdir(base_dir):
        return {"items": [], "total": 0, "limit": limit, "offset": offset, "has_more": False}

    limit = max(1, min(int(limit or 12), 60))
    offset = max(0, int(offset or 0))
    items: list[dict] = []
    for root, dirs, files in os.walk(base_dir):
        dirs[:] = [name for name in dirs if name not in {"_thumbs", "uploads", "smart_png"}]
        for file_name in files:
            extension = os.path.splitext(file_name)[1].lower()
            if extension not in IMAGE_EXTENSIONS:
                continue
            item = _build_history_item(os.path.join(root, file_name), include_thumbnail=False)
            if item:
                items.append(item)

    items.sort(key=lambda item: item["created_at"], reverse=True)
    total = len(items)
    page_items = []
    for item in items[offset : offset + limit]:
        full_path = os.path.join(base_dir, item["id"].replace("/", os.sep))
        hydrated = _build_history_item(full_path, include_thumbnail=True)
        if hydrated:
            page_items.append(hydrated)

    return {
        "items": page_items,
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_more": offset + len(page_items) < total,
    }

def cleanup_all_web_runtime() -> None:
    base_dir = _runtime_base()
    if not os.path.isdir(base_dir):
        return
    shutil.rmtree(base_dir, ignore_errors=True)
    os.makedirs(base_dir, exist_ok=True)


def start_history_cleanup_thread() -> None:
    global _cleanup_started
    with _cleanup_lock:
        if _cleanup_started:
            return
        _cleanup_started = True

    def worker() -> None:
        while True:
            time.sleep(HISTORY_CLEANUP_INTERVAL_SECONDS)
            try:
                cleanup_all_web_runtime()
                config.log_to_file("网页端任务历史与生成图片已按 12 小时周期清理。")
            except Exception as exc:
                config.log_to_file(f"网页端任务历史清理失败: {exc}", "ERROR")

    thread = threading.Thread(target=worker, name="web-history-cleanup", daemon=True)
    thread.start()
