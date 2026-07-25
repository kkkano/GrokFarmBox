"""仪表盘：连接状态条 / 一键操作 / 号池列表 / 额度 / 日志。"""
from __future__ import annotations

import os
import subprocess
import threading
import webbrowser
from typing import TYPE_CHECKING

import customtkinter as ctk

from app.config import CPA_DIR, load_config
from app.gui.theme import FONT_BODY, FONT_H2, FONT_MONO, FONT_TITLE

if TYPE_CHECKING:
    from app.services.farm import FarmController


class DashboardPage(ctk.CTkFrame):
    def __init__(self, master, farm: "FarmController", **kwargs):
        super().__init__(master, **kwargs)
        self.farm = farm
        self._build()

    # ---------------- 构建 ----------------
    def _build(self) -> None:
        ctk.CTkLabel(self, text="Grok 号池仪表盘", font=FONT_TITLE).pack(
            anchor="w", padx=16, pady=(16, 4)
        )

        self._build_status_bar()
        self._build_actions()
        self._build_kpi()
        self._build_list()
        self._build_quota()
        self._build_log()
        self.refresh_status()

    def _build_status_bar(self) -> None:
        """顶部连接状态条：服务器 / 凭证目录 / 安全后缀 / 连接结果。"""
        bar = ctk.CTkFrame(self)
        bar.pack(fill="x", padx=16, pady=8)
        ctk.CTkLabel(bar, text="当前连接", font=FONT_H2).pack(anchor="w", padx=10, pady=(8, 2))

        info = ctk.CTkFrame(bar, fg_color="transparent")
        info.pack(fill="x", padx=10, pady=(0, 6))
        self.lbl_server = ctk.CTkLabel(info, text="服务器：未设置", font=FONT_BODY, anchor="w")
        self.lbl_server.grid(row=0, column=0, sticky="w", padx=8)
        self.lbl_suffix = ctk.CTkLabel(info, text="安全后缀：—", font=FONT_BODY, anchor="w")
        self.lbl_suffix.grid(row=0, column=1, sticky="w", padx=8)
        self.lbl_group = ctk.CTkLabel(info, text="分组：—  代理：—", font=FONT_BODY, anchor="w")
        self.lbl_group.grid(row=1, column=0, sticky="w", padx=8, pady=2)
        self.lbl_cpa = ctk.CTkLabel(info, text="凭证目录：—", font=FONT_BODY, anchor="w")
        self.lbl_cpa.grid(row=1, column=1, sticky="w", padx=8, pady=2)

        row = ctk.CTkFrame(bar, fg_color="transparent")
        row.pack(fill="x", padx=10, pady=(0, 8))
        ctk.CTkButton(row, text="测试连接", command=self._do_test_conn, width=110).pack(side="left", padx=4)
        ctk.CTkButton(
            row, text="打开凭证目录", command=self._open_cpa_dir, width=130
        ).pack(side="left", padx=4)
        ctk.CTkButton(
            row, text="去设置填写", command=self._goto_settings, width=120
        ).pack(side="left", padx=4)
        self.lbl_conn = ctk.CTkLabel(row, text="（点「测试连接」看服务器能不能连上）", font=FONT_BODY)
        self.lbl_conn.pack(side="left", padx=10)

    def _build_actions(self) -> None:
        act = ctk.CTkFrame(self)
        act.pack(fill="x", padx=16, pady=8)
        ctk.CTkLabel(act, text="一键操作", font=FONT_H2).pack(anchor="w", padx=8, pady=4)
        ctk.CTkLabel(
            act,
            text=(
                "① 刷新概况：从服务器拉号池  ② 把号导入服务器：读凭证目录里的号写进 sub2api\n"
                "③ 一键测活并清理失效号  ④ 抽样看额度  ⑤ 用业务 key 冒烟测试 grok-4.5"
            ),
            font=FONT_BODY,
            justify="left",
        ).pack(anchor="w", padx=10, pady=(0, 6))
        row = ctk.CTkFrame(act, fg_color="transparent")
        row.pack(fill="x", padx=4, pady=4)
        buttons = [
            ("① 刷新概况", self._do_overview),
            ("② 把号导入服务器", self._do_import),
            ("③ 一键测活/杀号", self._do_clean),
            ("④ 抽样额度", self._do_quota),
            ("⑤ 冒烟 grok-4.5", self._do_smoke),
            ("启动农场循环", self._do_start_farm),
            ("停止农场", self._do_stop_farm),
        ]
        for i, (text, cmd) in enumerate(buttons):
            b = ctk.CTkButton(row, text=text, command=cmd, width=140)
            b.grid(row=i // 4, column=i % 4, padx=6, pady=6, sticky="ew")

    def _build_kpi(self) -> None:
        kpi = ctk.CTkFrame(self)
        kpi.pack(fill="x", padx=16, pady=8)
        self.lbl_active = self._kpi(kpi, "匹配后缀·可用", "—")
        self.lbl_total = self._kpi(kpi, "匹配后缀·总计", "—")
        self.lbl_other = self._kpi(kpi, "其它账号·只读", "—")
        self.lbl_farm = self._kpi(kpi, "农场状态", "停止")
        for w in (self.lbl_active, self.lbl_total, self.lbl_other, self.lbl_farm):
            w.pack(side="left", expand=True, fill="x", padx=6, pady=6)

    def _build_list(self) -> None:
        mid = ctk.CTkFrame(self)
        mid.pack(fill="both", expand=True, padx=16, pady=8)
        ctk.CTkLabel(mid, text="账号列表（仅显示匹配安全后缀的号）", font=FONT_H2).pack(
            anchor="w", padx=8, pady=4
        )
        self.tree_box = ctk.CTkTextbox(mid, font=FONT_MONO, height=150)
        self.tree_box.pack(fill="both", expand=True, padx=8, pady=6)
        self.tree_box.insert("1.0", "点「① 刷新概况」从服务器拉取账号列表")

    def _build_quota(self) -> None:
        qf = ctk.CTkFrame(self)
        qf.pack(fill="x", padx=16, pady=8)
        ctk.CTkLabel(qf, text="额度摘要（抽样）", font=FONT_H2).pack(anchor="w", padx=8, pady=4)
        self.lbl_quota = ctk.CTkLabel(
            qf,
            text="尚未查询（单号常见上限：21 次请求 / 100 万 token / 窗口）",
            font=FONT_BODY,
            justify="left",
        )
        self.lbl_quota.pack(anchor="w", padx=12, pady=6)

    def _build_log(self) -> None:
        lf = ctk.CTkFrame(self)
        lf.pack(fill="both", expand=True, padx=16, pady=(0, 12))
        ctk.CTkLabel(lf, text="运行日志", font=FONT_H2).pack(anchor="w", padx=8, pady=4)
        self.log_box = ctk.CTkTextbox(lf, font=FONT_MONO, height=130)
        self.log_box.pack(fill="both", expand=True, padx=8, pady=6)

    # ---------------- 辅助 ----------------
    def _kpi(self, parent, title: str, value: str) -> ctk.CTkFrame:
        f = ctk.CTkFrame(parent)
        ctk.CTkLabel(f, text=title, font=FONT_BODY).pack(pady=(8, 0))
        lab = ctk.CTkLabel(f, text=value, font=FONT_H2)
        lab.pack(pady=(0, 8))
        f.value_label = lab  # type: ignore[attr-defined]
        return f

    def log(self, msg: str) -> None:
        def _append():
            self.log_box.insert("end", msg + "\n")
            self.log_box.see("end")
        self.after(0, _append)

    def _bg(self, fn) -> None:
        threading.Thread(target=fn, daemon=True).start()

    def _set_kpi(self, frame, text: str) -> None:
        self.after(0, lambda: frame.value_label.configure(text=text))

    def _goto_settings(self) -> None:
        master = self.master
        # container -> app
        root = self.winfo_toplevel()
        show = getattr(root, "show", None)
        if show:
            show("settings")

    def _open_cpa_dir(self) -> None:
        path = self._cpa_dir()
        path.mkdir(parents=True, exist_ok=True)
        try:
            if os.name == "nt":
                os.startfile(str(path))  # type: ignore[attr-defined]
            else:
                subprocess.Popen(["xdg-open", str(path)])
        except Exception as e:
            self.log(f"打开目录失败: {e}")
        self.log(f"凭证目录：{path}（把 grok-register 的 cpa_auths/*.json 放这里）")

    def _cpa_dir(self):
        cfg = load_config()
        if cfg.get("external_register_cwd"):
            from pathlib import Path
            ext = Path(cfg["external_register_cwd"]) / "cpa_auths"
            if ext.exists():
                return ext
        return CPA_DIR

    def refresh_status(self) -> None:
        cfg = load_config()
        self.lbl_server.configure(
            text=f"服务器：{cfg.get('sub2api_base') or '未设置'}"
        )
        self.lbl_suffix.configure(
            text=f"安全后缀：{cfg.get('sub2api_safe_suffix') or '（空=管全部，谨慎）'}"
        )
        self.lbl_group.configure(
            text=f"分组ID：{cfg.get('sub2api_group_id')}   代理ID：{cfg.get('sub2api_proxy_id')}"
        )
        self.lbl_cpa.configure(text=f"凭证目录：{self._cpa_dir()}")
        self.lbl_conn.configure(text="（改完设置记得点「测试连接」）")

    # ---------------- 操作 ----------------
    def _do_test_conn(self) -> None:
        def work():
            try:
                self.lbl_conn.configure(text="连接中…")
                ov = self.farm.once_overview()
                self.lbl_conn.configure(
                    text=f"✅ 连接成功：服务器共 {ov.get('safe_total',0)} 个匹配号 / {ov.get('other_total',0)} 个其它号"
                )
                self.log("连接测试成功")
                self._apply_overview(ov)
            except Exception as e:
                self.lbl_conn.configure(text=f"❌ 连接失败：{e}")
                self.log(f"连接失败: {e}")
        self._bg(work)

    def _apply_overview(self, ov: dict) -> None:
        self._set_kpi(self.lbl_active, str(ov.get("safe_active", 0)))
        self._set_kpi(self.lbl_total, str(ov.get("safe_total", 0)))
        self._set_kpi(self.lbl_other, str(ov.get("other_total", 0)))
        lines = ["ID        状态      名称"]
        for a in (ov.get("accounts") or [])[:200]:
            lines.append(f"{str(a.get('id')):<9} {str(a.get('status') or '-'):<8} {a.get('name')}")
        text = "\n".join(lines) if len(lines) > 1 else "(暂无匹配安全后缀的号)"

        def ui():
            self.tree_box.delete("1.0", "end")
            self.tree_box.insert("1.0", text)
        self.after(0, ui)

    def _do_overview(self) -> None:
        def work():
            try:
                self.log("刷新号池概况…")
                ov = self.farm.once_overview()
                self._apply_overview(ov)
                self.log(f"概况完成 status={ov.get('by_status')}")
            except Exception as e:
                self.log(f"概况失败: {e}")
        self._bg(work)

    def _do_import(self) -> None:
        def work():
            try:
                cpa = self._cpa_dir()
                self.log(f"开始导入：读取 {cpa} 里的凭证 → 写入 sub2api…")
                st = self.farm.once_import(log=self.log)
                self.log(
                    f"导入完成：扫描 {st.get('scanned')} / 新增 {st.get('imported')} / "
                    f"测活失败已删 {st.get('deleted')} / 失败 {st.get('failed')} / 跳过 {st.get('skipped')}"
                )
                self._do_overview()
            except Exception as e:
                self.log(f"导入失败: {e}")
        self._bg(work)

    def _do_clean(self) -> None:
        def work():
            try:
                self.log("开始测活并清理失效号…")
                st = self.farm.once_clean(log=self.log)
                self.log(
                    f"清理完成：总数 {st.get('total')} / 保留 {st.get('kept')} / 删除 {st.get('deleted')}"
                )
                self._do_overview()
            except Exception as e:
                self.log(f"清理失败: {e}")
        self._bg(work)

    def _do_quota(self) -> None:
        def work():
            try:
                self.log("抽样读取额度…")
                q = self.farm.once_quota(log=self.log)
                text = (
                    f"匹配可用号：{q.get('active_total')}   抽样：{q.get('sampled')}\n"
                    f"平均剩余请求次数：{q.get('avg_remaining_requests')}\n"
                    f"平均剩余 token：{q.get('avg_remaining_tokens')}\n"
                    f"（单号常见上限：21 次请求 / 100 万 token / 窗口）"
                )
                self.after(0, lambda: self.lbl_quota.configure(text=text))
                self.log("额度摘要已更新")
            except Exception as e:
                self.log(f"额度失败: {e}")
        self._bg(work)

    def _do_smoke(self) -> None:
        def work():
            try:
                self.log("冒烟测试 grok-4.5…")
                r = self.farm.once_smoke()
                self.log(f"冒烟结果：{r}")
            except Exception as e:
                self.log(f"冒烟失败: {e}")
        self._bg(work)

    def _do_start_farm(self) -> None:
        self.farm.start(log=self.log, on_state=self._on_farm_state)
        self._set_kpi(self.lbl_farm, "运行中")
        self.log("已请求启动农场循环")

    def _do_stop_farm(self) -> None:
        self.farm.stop()
        self._set_kpi(self.lbl_farm, "停止中…")
        self.log("已请求停止农场")

    def _on_farm_state(self, st: dict) -> None:
        running = st.get("running")
        self._set_kpi(self.lbl_farm, "运行中" if running else "已停止")
