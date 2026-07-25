"""CustomTkinter 主题辅助。"""
from __future__ import annotations

import customtkinter as ctk


def apply_theme(theme: str = "dark", accent: str = "blue") -> None:
    ctk.set_appearance_mode(theme if theme in ("dark", "light", "system") else "dark")
    ctk.set_default_color_theme(accent if accent in ("blue", "green", "dark-blue") else "blue")


FONT_TITLE = ("Microsoft YaHei UI", 20, "bold")
FONT_H2 = ("Microsoft YaHei UI", 15, "bold")
FONT_BODY = ("Microsoft YaHei UI", 12)
FONT_MONO = ("Consolas", 11)
