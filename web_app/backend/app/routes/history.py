from __future__ import annotations

from flask import Blueprint, jsonify, request

from ..services.history_service import list_generated_history


history_bp = Blueprint("history", __name__)


@history_bp.get("/history/images")
def list_history_images():
    try:
        try:
            limit = int(request.args.get("limit", "300"))
        except (TypeError, ValueError):
            limit = 300
        return jsonify({"ok": True, "data": list_generated_history(limit)})
    except Exception as exc:
        return jsonify({"ok": False, "message": str(exc)}), 400
