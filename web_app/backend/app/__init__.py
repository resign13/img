from __future__ import annotations

import os
import sys

from flask import Flask, abort, jsonify, send_from_directory
from flask_cors import CORS


CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(CURRENT_DIR)
WEB_ROOT = os.path.dirname(BACKEND_DIR)
REPO_ROOT = os.path.dirname(WEB_ROOT)
DESKTOP_ROOT = os.path.join(REPO_ROOT, "desktop_app")

if DESKTOP_ROOT not in sys.path:
    sys.path.insert(0, DESKTOP_ROOT)

import config

from .routes.face_swap import face_swap_bp
from .routes.health import health_bp
from .routes.history import history_bp
from .routes.models import models_bp
from .routes.multi_reference import multi_reference_bp
from .routes.replacer import replacer_bp
from .routes.scene import scene_bp
from .services.history_service import start_history_cleanup_thread


def create_app() -> Flask:
    static_folder = os.path.join(os.path.dirname(__file__), "static")
    app = Flask(__name__, static_folder=None)
    app.config["JSON_AS_ASCII"] = False
    app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024

    CORS(app, resources={r"/api/*": {"origins": "*"}})
    start_history_cleanup_thread()

    app.register_blueprint(health_bp, url_prefix="/api")
    app.register_blueprint(history_bp, url_prefix="/api")
    app.register_blueprint(models_bp, url_prefix="/api")
    app.register_blueprint(scene_bp, url_prefix="/api")
    app.register_blueprint(replacer_bp, url_prefix="/api")
    app.register_blueprint(multi_reference_bp, url_prefix="/api")
    app.register_blueprint(face_swap_bp, url_prefix="/api")

    @app.errorhandler(413)
    def handle_file_too_large(_error):
        return jsonify({"ok": False, "message": "上传文件过大，请压缩后重试。"}), 413

    @app.route("/generated/<path:relative_path>")
    def serve_generated_file(relative_path: str):
        base_dir = os.path.join(config.DEFAULT_OUTPUT_DIR, "web_runtime")
        normalized_base = os.path.abspath(base_dir)
        absolute_path = os.path.abspath(os.path.join(base_dir, relative_path))
        if not absolute_path.startswith(normalized_base) or not os.path.exists(absolute_path):
            abort(404)
        folder = os.path.dirname(absolute_path)
        filename = os.path.basename(absolute_path)
        return send_from_directory(folder, filename)

    @app.route("/", defaults={"path": ""})
    @app.route("/<path:path>")
    def serve_frontend(path: str):
        if path.startswith("api/"):
            return jsonify({"ok": False, "message": "API route not found"}), 404

        if path and os.path.exists(os.path.join(static_folder, path)):
            return send_from_directory(static_folder, path)

        index_path = os.path.join(static_folder, "index.html")
        if os.path.exists(index_path):
            return send_from_directory(static_folder, "index.html")
        return jsonify(
            {
                "ok": False,
                "message": "Frontend build not found. Please run the Vue build before deployment.",
            }
        ), 503

    return app
