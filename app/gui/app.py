"""主窗口：侧边导航 + 页面容器。"""
from __future__ import annotations

import customtkinter as ctk

from app.config import ensure_dirs, load_config
from app.gui.pages.dashboard import DashboardPage
from app.gui.pages.guide import GuidePage
from app.gui.pages.settings import SettingsPage
from app.gui.theme import FONT_BODY, FONT_H2, apply_theme
from app.services.farm import FarmController


class GrokFarmApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        ensure_dirs()
        cfg = load_config()
        apply_theme(cfg.get("theme", "dark"), cfg.get("accent", "blue"))

        self.title("GrokFarmBox — 傻瓜式 Grok 号池管理台")
        self.geometry("1180x780")
        self.minsize(980, 640)

        self.farm = FarmController()
        self._pages: dict[str, ctk.CTkFrame] = {}
        self._build_layout()
        self.show("dashboard")

    def _build_layout(self) -> None:
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        nav = ctk.CTkFrame(self, width=200, corner_radius=0)
        nav.grid(row=0, column=0, sticky="nsew")
        nav.grid_propagate(False)

        ctk.CTkLabel(nav, text="GrokFarmBox", font=FONT_H2).pack(padx=16, pady=(20, 8))
        ctk.CTkLabel(nav, text="私有工具 · 本地运行", font=FONT_BODY).pack(padx=16, pady=(0, 16))

        for key, label in (
            ("dashboard", "仪表盘"),
            ("settings", "设置"),
            ("guide", "CF 教程"),
        ):
            ctk.CTkButton(
                nav,
                text=label,
                command=lambda k=key: self.show(k),
                height=36,
                anchor="w",
            ).pack(fill="x", padx=12, pady=6)

        ctk.CTkLabel(
            nav,
            text="默认只操作\n「安全邮箱后缀」匹配的账号\n其它账号不会被改动",
            font=FONT_BODY,
            justify="left",
        ).pack(side="bottom", padx=16, pady=20)

        self.container = ctk.CTkFrame(self, corner_radius=0)
        self.container.grid(row=0, column=1, sticky="nsew")
        self.container.grid_columnconfigure(0, weight=1)
        self.container.grid_rowconfigure(0, weight=1)

        self._pages["dashboard"] = DashboardPage(self.container, farm=self.farm)
        self._pages["settings"] = SettingsPage(self.container)
        self._pages["guide"] = GuidePage(self.container)
        for p in self._pages.values():
            p.grid(row=0, column=0, sticky="nsew")

    def show(self, name: str) -> None:
        page = self._pages[name]
        page.tkraise()
        if name == "dashboard" and hasattr(page, "refresh_status"):
            page.refresh_status()


def run() -> None:
    app = GrokFarmApp()
    app.mainloop()
