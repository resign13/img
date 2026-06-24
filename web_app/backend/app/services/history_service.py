from __future__ import annotations

import json
import os
import shutil
import threading
import time
from datetime import datetime

import config

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
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


def _build_history_item(path: str) -> dict | None:
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

    return {
        "id": relative_path,
        "url": f"/generated/{relative_path}",
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


def list_generated_history(limit: int = 300) -> list[dict]:
    base_dir = _runtime_base()
    if not os.path.isdir(base_dir):
        return []

    items: list[dict] = []
    for root, _dirs, files in os.walk(base_dir):
        for file_name in files:
            extension = os.path.splitext(file_name)[1].lower()
            if extension not in IMAGE_EXTENSIONS:
                continue
            item = _build_history_item(os.path.join(root, file_name))
            if item:
                items.append(item)

    items.sort(key=lambda item: item["created_at"], reverse=True)
    return items[: max(1, min(limit, 1000))]


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
