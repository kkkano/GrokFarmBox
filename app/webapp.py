"""启动 Flask + 用 Chrome/Edge 的 --app 模式打开（桌面应用感，不依赖 WebView2）。"""
from __future__ import annotations

import os
import subprocess
import threading
import time
import webbrowser

from app.web_server import create_app

PORT = 8848


def _find_browser() -> str:
    cands = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    ]
    for p in cands:
        if os.path.exists(p):
            return p
    return ""


def _open(url: str) -> None:
    time.sleep(1.2)
    exe = _find_browser()
    try:
        if exe:
            subprocess.Popen([exe, "--app=" + url, "--new-window"])
        else:
            webbrowser.open(url)
    except Exception:
        try:
            webbrowser.open(url)
        except Exception:
            pass


def run() -> None:
    app = create_app()
    url = f"http://127.0.0.1:{PORT}"
    threading.Thread(target=_open, args=(url,), daemon=True).start()
    app.run(host="127.0.0.1", port=PORT, debug=False, threaded=True, use_reloader=False)


if __name__ == "__main__":
    run()
