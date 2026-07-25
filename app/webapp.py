"""pywebview 启动：加载本地前端，绑定 Python API。"""
from __future__ import annotations

import sys
import threading
import traceback
from pathlib import Path

import webview

from app.config import ensure_dirs, load_config
from app.web_api import Api, web_dir


class _App:
    def __init__(self) -> None:
        self.api: Api | None = None
        self.window = None

    def on_loaded(self):
        ensure_dirs()


def run() -> None:
    ensure_dirs()
    try:
        cfg = load_config()
    except Exception:
        cfg = {}

    api = Api()

    index = web_dir() / "index.html"
    if not index.exists():
        # 开发兜底
        index = Path(__file__).resolve().parent / "web" / "index.html"

    window = webview.create_window(
        title="GrokFarmBox · 号池控制台",
        url=str(index),
        js_api=api,
        width=1240,
        height=840,
        min_size=(960, 640),
        text_select=True,
    )
    api.window = window

    try:
        webview.start(debug=False)
    except Exception:
        # 某些环境缺后端时给提示
        traceback.print_exc()
        raise


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    run()
