from __future__ import annotations

from flask import Blueprint, jsonify

from ..services.config_service import get_public_config


models_bp = Blueprint("models", __name__)


@models_bp.get("/config/public")
def public_config():
    return jsonify({"ok": True, "data": get_public_config()})
