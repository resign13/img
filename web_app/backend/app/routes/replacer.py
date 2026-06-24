from __future__ import annotations

from flask import Blueprint, jsonify, request

from ..services.request_parsers import parse_generation_settings, parse_uploaded_files
from ..services.workflows import run_product_replacement_web


replacer_bp = Blueprint("replacer", __name__)


@replacer_bp.post("/replacer/run")
def run_replacer():
    try:
        settings = parse_generation_settings(request)
        scene_paths = parse_uploaded_files(request.files.getlist("scene_images"), "replacer_scenes", "scene", settings.session_id)
        product_paths = parse_uploaded_files(request.files.getlist("product_images"), "replacer_products", "product", settings.session_id)
        manual_text = request.form.get("manual_text", "").strip()
        results = run_product_replacement_web(settings, scene_paths, product_paths, manual_text)
        return jsonify({"ok": True, "data": results})
    except Exception as exc:
        return jsonify({"ok": False, "message": str(exc)}), 400
