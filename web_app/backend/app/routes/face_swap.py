from __future__ import annotations

from flask import Blueprint, jsonify, request

from ..services.request_parsers import parse_generation_settings, parse_uploaded_files
from ..services.workflows import run_face_swap_generation_web


face_swap_bp = Blueprint("face_swap", __name__)


@face_swap_bp.post("/face-swap/run")
def run_face_swap():
    try:
        settings = parse_generation_settings(request)
        target_paths = parse_uploaded_files(request.files.getlist("target_images"), "face_targets", "target", settings.session_id)
        head_paths = parse_uploaded_files(request.files.getlist("head_images"), "face_heads", "head", settings.session_id)
        accessory_paths = parse_uploaded_files(request.files.getlist("accessory_images"), "face_accessories", "accessory", settings.session_id)
        manual_text = request.form.get("manual_text", "").strip()
        results = run_face_swap_generation_web(settings, target_paths, head_paths, accessory_paths, manual_text)
        return jsonify({"ok": True, "data": results})
    except Exception as exc:
        return jsonify({"ok": False, "message": str(exc)}), 400
