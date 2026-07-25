"""设置页：每个字段都有示例和说明，照着填就行。"""
from __future__ import annotations

import customtkinter as ctk

from app.config import DEFAULT_CONFIG, load_config, save_config
from app.gui.theme import FONT_BODY, FONT_H2, FONT_TITLE


# 字段定义：key, 标签, 占位示例, 说明, 是否密码, 是否整数
FIELDS_SUB2 = [
    ("sub2api_base", "服务器地址", "http://your-server-ip",
     "你的 sub2api 网关地址。带 http:// 或 https://，别带末尾斜杠。", False, False),
    ("sub2api_email", "管理员邮箱", "admin@example.com",
     "登录 sub2api 后台用的管理员邮箱。", False, False),
    ("sub2api_password", "管理员密码", "",
     "登录 sub2api 后台用的密码（只存在本机 data/config.json）。", True, False),
    ("sub2api_group_id", "Grok 分组 ID", "1",
     "号导入到哪个分组。在 sub2api 后台「分组」里看 ID，grok 分组通常是 1。", False, True),
    ("sub2api_proxy_id", "代理 ID", "0",
     "导入后绑哪个代理，填 0 表示不绑定。在 sub2api 后台「代理」里看 ID。", False, True),
    ("sub2api_safe_suffix", "安全邮箱后缀", "@your-domain.com",
     "只操作邮箱是此后缀的号（你批量注册用的域名）。留空=管全部账号（谨慎）。", False, False),
]

FIELDS_CF = [
    ("cf_api_base", "邮箱服务地址", "https://mail.yourdomain.com",
     "你部署的 Cloudflare 临时邮箱地址（见「CF 教程」页）。", False, False),
    ("cf_admin_token", "邮箱管理密码", "",
     "临时邮箱 Worker 里设置的 ADMIN_PASSWORDS（见「CF 教程」页）。", True, False),
    ("cf_domain", "邮箱域名", "yourdomain.com",
     "收信用的域名，例如 yourdomain.com。", False, False),
    ("cf_auth_mode", "鉴权方式", "x-admin-auth",
     "一般填 x-admin-auth；若创建邮箱报 401，依次试 bearer / x-api-key / query-key / none。", False, False),
]

FIELDS_REG = [
    ("external_register_cmd", "外部注册命令", "C:\\grok-register\\.venv\\Scripts\\python.exe grok_register_ttk.py cli",
     "可选。想自动刷号就填你本机 grok-register 的启动命令；不填就只导入已有凭证。", False, False),
    ("external_register_cwd", "外部注册工作目录", "C:\\grok-register",
     "上一条命令的运行目录（grok-register 的根目录）。", False, False),
    ("register_count", "每批注册数量", "3",
     "每次循环注册几个号，浏览器自动化比较慢，建议 1~5。", False, True),
    ("proxy", "HTTP 代理", "http://127.0.0.1:7897",
     "可选。注册时走的本地代理，不需要就留空。", False, False),
]

FIELDS_CLEAN = [
    ("test_concurrency", "测活并发", "8",
     "同时测几个号，太大会被限速，建议 4~12。", False, True),
    ("max_tokens_probe", "冒烟 token 数", "8",
     "冒烟测试时输出的 token 上限，free 号建议 ≤ 16，否则容易 400。", False, True),
    ("clean_interval_min", "清理间隔(分钟)", "120",
     "预留：自动清理的间隔。", False, True),
]


class SettingsPage(ctk.CTkScrollableFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.vars: dict[str, ctk.StringVar | ctk.BooleanVar] = {}
        self.entries: dict[str, ctk.CTkEntry] = {}
        self._build()
        self.reload()

    def _field(self, parent, key, label, example, tip, secret=False, integer=False, width=460):
        box = ctk.CTkFrame(parent, fg_color="transparent")
        box.pack(fill="x", padx=10, pady=6)
        head = ctk.CTkFrame(box, fg_color="transparent")
        head.pack(fill="x")
        ctk.CTkLabel(head, text=label, font=FONT_BODY, anchor="w").pack(side="left")
        star = "（整数）" if integer else ("（密码）" if secret else "")
        if star:
            ctk.CTkLabel(head, text=star, font=FONT_BODY).pack(side="left", padx=4)
        var = ctk.StringVar()
        entry = ctk.CTkEntry(
            box, textvariable=var, show="*" if secret else "", width=width,
            placeholder_text=f"示例：{example}" if example else "",
        )
        entry.pack(fill="x", pady=(2, 2))
        if tip:
            ctk.CTkLabel(box, text=tip, font=FONT_BODY, anchor="w",
                         text_color=("gray40", "gray60")).pack(fill="x")
        self.vars[key] = var
        self.entries[key] = entry
        return var

    def _check(self, parent, key, label, tip=""):
        box = ctk.CTkFrame(parent, fg_color="transparent")
        box.pack(fill="x", padx=10, pady=4)
        var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(box, text=label, variable=var, font=FONT_BODY).pack(anchor="w")
        if tip:
            ctk.CTkLabel(box, text=tip, font=FONT_BODY, anchor="w",
                         text_color=("gray40", "gray60")).pack(anchor="w", padx=18)
        self.vars[key] = var
        return var

    def _section(self, title, subtitle="") -> ctk.CTkFrame:
        box = ctk.CTkFrame(self)
        box.pack(fill="x", padx=16, pady=10)
        ctk.CTkLabel(box, text=title, font=FONT_H2).pack(anchor="w", padx=10, pady=(8, 0))
        if subtitle:
            ctk.CTkLabel(box, text=subtitle, font=FONT_BODY, anchor="w",
                         text_color=("gray40", "gray60")).pack(anchor="w", padx=10, pady=(0, 6))
        return box

    def _build(self) -> None:
        ctk.CTkLabel(self, text="设置", font=FONT_TITLE).pack(anchor="w", padx=16, pady=(16, 2))
        ctk.CTkLabel(
            self,
            text="照着灰色示例填。密码只保存在本机 data/config.json，不会上传。",
            font=FONT_BODY,
        ).pack(anchor="w", padx=16, pady=(0, 4))
        ctk.CTkLabel(
            self,
            text="👉 必填的是【1. sub2api 服务器】。其它根据需要再填。",
            font=FONT_BODY,
        ).pack(anchor="w", padx=16, pady=(0, 8))

        s1 = self._section("1. sub2api 服务器（必填）", "号要导入到哪台服务器、哪个分组。")
        for f in FIELDS_SUB2:
            self._field(s1, *f)

        s2 = self._section("2. Cloudflare 临时邮箱（注册才需要）",
                           "注册新号要收验证码时用。不注册、只导入已有号可跳过。具体看「CF 教程」页。")
        for f in FIELDS_CF:
            self._field(s2, *f)

        s3 = self._section("3. 自动注册（可选）",
                           "想让它自己刷号才填。需要本机已装好 grok-register。")
        for f in FIELDS_REG:
            self._field(s3, *f)
        self._check(s3, "register_enabled", "农场循环里启用自动注册",
                    "勾上后，启动农场时会先跑外部注册命令再导入。")
        self._check(s3, "cpa_export_enabled", "注册时导出 CPA 凭证",
                    "一般保持勾选，导出的凭证才能被导入。")

        s4 = self._section("4. 测活 / 清理（一般用默认）")
        for f in FIELDS_CLEAN:
            self._field(s4, *f)
        self._check(s4, "auto_kill_bad", "测活失败自动删号",
                    "勾上后，402/403/quota 等失效号会自动从服务器删除。")

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
        if hasattr(self, "msg"):
            self.msg.configure(text="已加载本机配置")

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
                    self.msg.configure(text=f"「{key}」必须是整数")
                    return
            elif isinstance(var, ctk.BooleanVar):
                cfg[key] = bool(val)
            else:
                cfg[key] = str(val).strip()
        save_config(cfg)
        self.msg.configure(text="已保存 ✓  回仪表盘点「测试连接」验证")
