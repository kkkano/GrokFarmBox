"""设置页：sub2api / CF 邮箱 / 注册桥 / 农场选项。"""
from __future__ import annotations

import customtkinter as ctk

from app.config import DEFAULT_CONFIG, load_config, save_config
from app.gui.theme import FONT_BODY, FONT_H2, FONT_TITLE


class SettingsPage(ctk.CTkScrollableFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.vars: dict[str, ctk.StringVar | ctk.BooleanVar] = {}
        self._build()
        self.reload()

    def _field(self, parent, key: str, label: str, secret: bool = False, width: int = 420):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=8, pady=4)
        ctk.CTkLabel(row, text=label, width=200, anchor="w", font=FONT_BODY).pack(side="left")
        var = ctk.StringVar()
        entry = ctk.CTkEntry(row, textvariable=var, show="*" if secret else "", width=width)
        entry.pack(side="left", padx=8)
        self.vars[key] = var
        return var

    def _check(self, parent, key: str, label: str):
        var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(parent, text=label, variable=var, font=FONT_BODY).pack(
            anchor="w", padx=12, pady=4
        )
        self.vars[key] = var
        return var

    def _section(self, title: str) -> ctk.CTkFrame:
        box = ctk.CTkFrame(self)
        box.pack(fill="x", padx=16, pady=10)
        ctk.CTkLabel(box, text=title, font=FONT_H2).pack(anchor="w", padx=10, pady=8)
        return box

    def _build(self) -> None:
        ctk.CTkLabel(self, text="设置", font=FONT_TITLE).pack(anchor="w", padx=16, pady=(16, 4))
        ctk.CTkLabel(
            self,
            text="密码/Token 只保存在本机 data/config.json，不会上传。",
            font=FONT_BODY,
        ).pack(anchor="w", padx=16)

        s1 = self._section("sub2api 网关")
        self._field(s1, "sub2api_base", "Base URL")
        self._field(s1, "sub2api_email", "管理员邮箱")
        self._field(s1, "sub2api_password", "管理员密码", secret=True)
        self._field(s1, "sub2api_group_id", "Grok 分组 ID")
        self._field(s1, "sub2api_proxy_id", "代理 ID (0=不绑)")
        self._field(s1, "sub2api_safe_suffix", "安全邮箱后缀(仅操作匹配项)")

        s2 = self._section("Cloudflare 临时邮箱")
        self._field(s2, "cf_api_base", "Worker API Base")
        self._field(s2, "cf_admin_token", "Admin Token", secret=True)
        self._field(s2, "cf_domain", "邮箱域名")
        self._field(s2, "cf_auth_mode", "鉴权模式")

        s3 = self._section("注册桥（可选）")
        self._field(s3, "external_register_cmd", "外部注册命令")
        self._field(s3, "external_register_cwd", "外部注册工作目录")
        self._field(s3, "register_count", "每批注册数")
        self._field(s3, "proxy", "HTTP 代理")
        self._check(s3, "register_enabled", "农场循环里启用外部注册")
        self._check(s3, "cpa_export_enabled", "启用 CPA 导出")

        s4 = self._section("测活 / 杀号 / 农场")
        self._check(s4, "auto_kill_bad", "测活失败自动删号")
        self._field(s4, "test_concurrency", "测活并发")
        self._field(s4, "test_model", "测活模型")
        self._field(s4, "max_tokens_probe", "冒烟 max_tokens")
        self._field(s4, "clean_interval_min", "清理间隔(分钟,预留)")

        btns = ctk.CTkFrame(self, fg_color="transparent")
        btns.pack(fill="x", padx=16, pady=16)
        ctk.CTkButton(btns, text="保存设置", command=self.save, width=140).pack(side="left", padx=6)
        ctk.CTkButton(btns, text="重新加载", command=self.reload, width=140).pack(side="left", padx=6)
        self.msg = ctk.CTkLabel(btns, text="", font=FONT_BODY)
        self.msg.pack(side="left", padx=12)

    def reload(self) -> None:
        cfg = load_config()
        for key, var in self.vars.items():
            val = cfg.get(key, DEFAULT_CONFIG.get(key, ""))
            if isinstance(var, ctk.BooleanVar):
                var.set(bool(val))
            else:
                var.set("" if val is None else str(val))
        self.msg.configure(text="已加载")

    def save(self) -> None:
        cfg = load_config()
        int_keys = {
            "sub2api_group_id",
            "sub2api_proxy_id",
            "register_count",
            "test_concurrency",
            "max_tokens_probe",
            "clean_interval_min",
        }
        for key, var in self.vars.items():
            val = var.get()
            if key in int_keys:
                try:
                    cfg[key] = int(str(val).strip() or "0")
                except ValueError:
                    self.msg.configure(text=f"{key} 必须是整数")
                    return
            elif isinstance(var, ctk.BooleanVar):
                cfg[key] = bool(val)
            else:
                cfg[key] = str(val).strip()
        save_config(cfg)
        self.msg.configure(text="已保存 ✓")
