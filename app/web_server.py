"""Flask 后端：托管前端 + 暴露 /api/* 给 JS（替代不稳定的 pywebview WebView2 桥）。"""
from __future__ import annotations

from flask import Flask, jsonify, request, send_from_directory

from app.web_api import Api, web_dir

_api_singleton: Api | None = None


def get_api() -> Api:
    global _api_singleton
    if _api_singleton is None:
        _api_singleton = Api()
    return _api_singleton


# 需要从请求 body 取一个参数的方法
TAKES_BODY = {"save_config", "clean", "purge_error"}


def create_app() -> Flask:
    app = Flask(__name__, static_folder=None)
    api = get_api()

    @app.get("/")
    def _index():
        return send_from_directory(str(web_dir()), "index.html")

    @app.get("/<path:filename>")
    def _static(filename):
        return send_from_directory(str(web_dir()), filename)

    @app.post("/api/<method>")
    def _call(method):
        fn = getattr(api, method, None)
        if fn is None or method.startswith("_"):
            return jsonify({"ok": False, "error": "unknown method"}), 404
        body = request.get_json(silent=True)
        try:
            if method in TAKES_BODY and body is not None:
                return jsonify(fn(body))
            return jsonify(fn())
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)}), 500

    return app
