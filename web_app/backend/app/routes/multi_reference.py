from __future__ import annotations

from flask import Blueprint, jsonify, request

import config

from ..services.request_parsers import parse_generation_settings, parse_uploaded_files
from ..services.workflows import run_multi_reference_generation_web


multi_reference_bp = Blueprint("multi_reference", __name__)


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
