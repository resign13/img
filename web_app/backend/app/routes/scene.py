from __future__ import annotations

from flask import Blueprint, jsonify, request

from ..services.request_parsers import parse_generation_settings, parse_single_uploaded_file
from ..services.workflows import analyze_style_web, generate_scene_images_web, generate_scene_prompts_web


scene_bp = Blueprint("scene", __name__)


@scene_bp.post("/scene/analyze-style")
def analyze_scene_style():
    try:
        settings = parse_generation_settings(request)
        source_path = parse_single_uploaded_file(request.files.get("source_image"), "scene_source", "scene", settings.session_id)
        style_names = request.form.getlist("style_names")
        result = analyze_style_web(settings, source_path, style_names)
        return jsonify({"ok": True, "data": result})
    except Exception as exc:
        return jsonify({"ok": False, "message": str(exc)}), 400


@scene_bp.post("/scene/prompts")
def generate_scene_prompts():
    try:
        settings = parse_generation_settings(request)
        source_path = parse_single_uploaded_file(request.files.get("source_image"), "scene_source", "scene", settings.session_id)
        payload = {
            "template_name": request.form.get("template_name", "").strip(),
            "style_name": request.form.get("style_name", "").strip(),
            "style_desc": request.form.get("style_desc", "").strip(),
            "raw_template": request.form.get("raw_template", "").strip(),
            "extra_info": request.form.get("extra_info", "").strip(),
        }
        prompts = generate_scene_prompts_web(settings, source_path, payload)
        return jsonify({"ok": True, "data": prompts})
    except Exception as exc:
        return jsonify({"ok": False, "message": str(exc)}), 400


@scene_bp.post("/scene/generate")
def generate_scene_images():
    try:
        settings = parse_generation_settings(request)
        source_path = parse_single_uploaded_file(request.files.get("source_image"), "scene_source", "scene", settings.session_id)
        prompts = request.form.getlist("prompts")
        if not prompts:
            raw_prompts = request.form.get("prompts_json", "").strip()
            if raw_prompts:
                import json

                prompts = json.loads(raw_prompts)
        results = generate_scene_images_web(settings, source_path, prompts)
        return jsonify({"ok": True, "data": results})
    except Exception as exc:
        return jsonify({"ok": False, "message": str(exc)}), 400
