#!/usr/bin/env python3
"""GrokFarmBox 入口（pywebview 前端版）。"""
from __future__ import annotations

import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import LOG_DIR, ensure_dirs


def _install_excepthook() -> None:
    def hook(etype, exc, tb):
        txt = "".join(traceback.format_exception(etype, exc, tb))
        try:
            ensure_dirs()
            (LOG_DIR / "crash.log").write_text(txt, encoding="utf-8")
        except Exception:
            pass
        try:
            import tkinter.messagebox as mb
            mb.showerror("GrokFarmBox 出错", txt[:1600])
        except Exception:
            pass

    sys.excepthook = hook


if __name__ == "__main__":
    _install_excepthook()
    from app.webapp import run
    run()
