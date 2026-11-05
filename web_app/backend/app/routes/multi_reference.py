from __future__ import annotations

from flask import Blueprint, jsonify, request
import uuid

import config

from ..services.request_parsers import parse_generation_settings, parse_uploaded_files
from ..services.workflows import run_multi_reference_generation_web
from ..services import image_jobs
from ..services.request_parsers import _sanitize_session_id


multi_reference_bp = Blueprint("multi_reference", __name__)


@multi_reference_bp.post("/multi-reference/tasks")
def submit_multi_reference_task():
    try:
        task_id = str(uuid.UUID(request.form.get("task_id", "")))
        settings = parse_generation_settings(request)
        prompt = request.form.get("prompt", "").strip()
        if not prompt:
            raise ValueError("请输入提示词。")
        files = request.files.getlist("reference_images")
        if not files and not settings.model_config.get("supports_text_only_generation", False):
            raise ValueError("当前模型需要至少一张参考图。")
        paths = parse_uploaded_files(files, "multi_reference", "reference", settings.session_id)
        image_jobs.submit(task_id, settings, paths, prompt)
        return jsonify({"ok": True, "task_id": task_id}), 202
    except Exception as exc:
        return jsonify({"ok": False, "message": str(exc)}), 400


@multi_reference_bp.get("/multi-reference/tasks/<task_id>")
def get_multi_reference_task(task_id):
    session_id = _sanitize_session_id(request.args.get("session_id"))
    job = image_jobs.status(task_id, session_id)
    if job is None:
        return jsonify({"ok": False, "message": "任务不存在或服务器已重启，请检查历史记录后再提交。"}), 404
    return jsonify({"ok": True, "data": job})


@multi_reference_bp.post("/multi-reference/run")
def run_multi_reference():
    try:
        settings = parse_generation_settings(request)
        reference_paths = parse_uploaded_files(request.files.getlist("reference_images"), "multi_reference", "reference", settings.session_id)
        prompt = request.form.get("prompt", "").strip()
        config.log_to_file(
            f"网页端多参考图任务已提交: model={settings.image_model}, session={settings.session_id}, refs={len(reference_paths)}"
        )
        result = run_multi_reference_generation_web(settings, reference_paths, prompt)
        return jsonify({"ok": True, "data": result})
    except Exception as exc:
        return jsonify({"ok": False, "message": str(exc)}), 400
