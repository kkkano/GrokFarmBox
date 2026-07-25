"""仪表盘：号池概况 / 一键操作 / 额度 / 日志。"""
from __future__ import annotations

import threading
import tkinter as tk
from typing import TYPE_CHECKING

import customtkinter as ctk

from app.gui.theme import FONT_BODY, FONT_H2, FONT_MONO, FONT_TITLE

if TYPE_CHECKING:
    from app.services.farm import FarmController


class DashboardPage(ctk.CTkFrame):
    def __init__(self, master, farm: "FarmController", **kwargs):
        super().__init__(master, **kwargs)
        self.farm = farm
        self._build()

    def _build(self) -> None:
        head = ctk.CTkLabel(self, text="Grok 号池仪表盘", font=FONT_TITLE)
        head.pack(anchor="w", padx=16, pady=(16, 8))

        # KPI row
        kpi = ctk.CTkFrame(self)
        kpi.pack(fill="x", padx=16, pady=8)
        self.lbl_active = self._kpi(kpi, "匹配后缀·可用", "—")
        self.lbl_total = self._kpi(kpi, "匹配后缀·总计", "—")
        self.lbl_other = self._kpi(kpi, "其它账号·只读", "—")
        self.lbl_farm = self._kpi(kpi, "农场状态", "停止")
        for w in (self.lbl_active, self.lbl_total, self.lbl_other, self.lbl_farm):
            w.pack(side="left", expand=True, fill="x", padx=6, pady=6)

        # actions
        act = ctk.CTkFrame(self)
        act.pack(fill="x", padx=16, pady=8)
        ctk.CTkLabel(act, text="一键操作", font=FONT_H2).pack(anchor="w", padx=8, pady=4)
        row = ctk.CTkFrame(act, fg_color="transparent")
        row.pack(fill="x", padx=4, pady=4)
        buttons = [
            ("刷新概况", self._do_overview),
            ("导入 CPA → sub2api", self._do_import),
            ("一键测活/杀号", self._do_clean),
            ("抽样额度", self._do_quota),
            ("冒烟 grok-4.5", self._do_smoke),
            ("启动农场循环", self._do_start_farm),
            ("停止农场", self._do_stop_farm),
        ]
        for i, (text, cmd) in enumerate(buttons):
            b = ctk.CTkButton(row, text=text, command=cmd, width=140)
            b.grid(row=i // 4, column=i % 4, padx=6, pady=6, sticky="ew")

        # quota panel
        qf = ctk.CTkFrame(self)
        qf.pack(fill="x", padx=16, pady=8)
        ctk.CTkLabel(qf, text="额度摘要（抽样）", font=FONT_H2).pack(anchor="w", padx=8, pady=4)
        self.lbl_quota = ctk.CTkLabel(qf, text="尚未查询", font=FONT_BODY, justify="left")
        self.lbl_quota.pack(anchor="w", padx=12, pady=6)

        # account list
        mid = ctk.CTkFrame(self)
        mid.pack(fill="both", expand=True, padx=16, pady=8)
        ctk.CTkLabel(mid, text="账号列表（安全后缀）", font=FONT_H2).pack(anchor="w", padx=8, pady=4)
        self.tree_box = ctk.CTkTextbox(mid, font=FONT_MONO, height=160)
        self.tree_box.pack(fill="both", expand=True, padx=8, pady=6)

        # log
        lf = ctk.CTkFrame(self)
        lf.pack(fill="both", expand=True, padx=16, pady=(0, 12))
        ctk.CTkLabel(lf, text="运行日志", font=FONT_H2).pack(anchor="w", padx=8, pady=4)
        self.log_box = ctk.CTkTextbox(lf, font=FONT_MONO, height=160)
        self.log_box.pack(fill="both", expand=True, padx=8, pady=6)

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

    def _do_overview(self) -> None:
        def work():
            try:
                self.log("刷新号池概况…")
                ov = self.farm.once_overview()
                self._set_kpi(self.lbl_active, str(ov.get("safe_active", 0)))
                self._set_kpi(self.lbl_total, str(ov.get("safe_total", 0)))
                self._set_kpi(self.lbl_other, str(ov.get("other_total", 0)))
                lines = [f"{'ID':<8} {'状态':<10} 名称"]
                for a in (ov.get("accounts") or [])[:200]:
                    lines.append(
                        f"{str(a.get('id')):<8} {str(a.get('status') or '-'):<10} {a.get('name')}"
                    )
                text = "\n".join(lines) if len(lines) > 1 else "(暂无安全后缀账号)"

                def ui():
                    self.tree_box.delete("1.0", "end")
                    self.tree_box.insert("1.0", text)

                self.after(0, ui)
                self.log(
                    f"概况完成 active={ov.get('safe_active')} total={ov.get('safe_total')} "
                    f"status={ov.get('by_status')}"
                )
            except Exception as e:
                self.log(f"概况失败: {e}")

        self._bg(work)

    def _do_import(self) -> None:
        def work():
            try:
                self.log("开始导入 CPA…")
                st = self.farm.once_import(log=self.log)
                self.log(
                    f"导入完成 scanned={st.get('scanned')} imported={st.get('imported')} "
                    f"deleted={st.get('deleted')} failed={st.get('failed')} skipped={st.get('skipped')}"
                )
                self._do_overview()
            except Exception as e:
                self.log(f"导入失败: {e}")

        self._bg(work)

    def _do_clean(self) -> None:
        def work():
            try:
                self.log("开始一键测活/杀号…")
                st = self.farm.once_clean(log=self.log)
                self.log(
                    f"清理完成 total={st.get('total')} kept={st.get('kept')} deleted={st.get('deleted')}"
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
                    f"active={q.get('active_total')}  sampled={q.get('sampled')}\n"
                    f"avg remaining requests: {q.get('avg_remaining_requests')}\n"
                    f"avg remaining tokens  : {q.get('avg_remaining_tokens')}\n"
                    f"(单号常见上限: 21 requests / 1,000,000 tokens / 窗口)"
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
                self.log(f"冒烟结果: {r}")
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
