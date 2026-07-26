"""pywebview JS 桥：把 FarmController / 配置 / 教程暴露给前端。

约定：每个方法返回可 JSON 序列化对象；出错尽量返回 {ok:false,error}，
避免前端拿到 rejected promise 不好定位。
"""
from __future__ import annotations

import sys
import threading
import time
import traceback
from pathlib import Path
from typing import Any


def _resource_root() -> Path:
    """打包后资源在 _MEIPASS；开发时在项目根。"""
    base = getattr(sys, "_MEIPASS", None)
    if base:
        return Path(base)
    return Path(__file__).resolve().parent.parent


def web_dir() -> Path:
    return _resource_root() / "app" / "web"


def guide_md_path() -> Path:
    return _resource_root() / "docs" / "cloudflare_temp_email.md"


class LogBus:
    """内存日志环，前端轮询 take。"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._q: list[dict] = []

    def push(self, msg: str, kind: str = "") -> None:
        if not isinstance(msg, str):
            msg = str(msg)
        with self._lock:
            self._q.append({"msg": msg, "kind": kind})

    def take(self) -> list[dict]:
        with self._lock:
            out = self._q
            self._q = []
        return out


INT_KEYS = {
    "sub2api_group_id",
    "sub2api_proxy_id",
    "register_count",
    "test_concurrency",
    "max_tokens_probe",
    "clean_interval_min",
}


class Api:
    def __init__(self) -> None:
        from app.config import CPA_DIR  # noqa: F401  确保初始化
        from app.services.farm import FarmController

        self.farm = FarmController()
        self.bus = LogBus()
        self._log("后端就绪")

    # ---------- 内部 ----------
    def _log(self, msg: str, kind: str = "") -> None:
        self.bus.push(msg, kind)

    def _logcb(self):
        def cb(m: str):
            self._log(m)
        return cb

    # ---------- 配置 ----------
    def get_config(self) -> dict:
        from app.config import load_config
        try:
            return load_config()
        except Exception as e:
            return {"_error": str(e)}

    def save_config(self, cfg: dict) -> dict:
        from app.config import load_config, save_config
        try:
            merged = load_config()
            for k, v in (cfg or {}).items():
                if k in INT_KEYS:
                    try:
                        merged[k] = int(str(v).strip() or "0")
                    except ValueError:
                        return {"ok": False, "error": f"「{k}」必须是整数"}
                elif isinstance(v, bool):
                    merged[k] = v
                else:
                    merged[k] = str(v).strip()
            save_config(merged)
            self._log("配置已保存", "ok")
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def cpa_dir(self) -> str:
        from app.config import CPA_DIR, load_config
        cfg = load_config()
        if cfg.get("external_register_cwd"):
            ext = Path(cfg["external_register_cwd"]) / "cpa_auths"
            if ext.exists():
                return str(ext)
        return str(CPA_DIR)

    def open_cpa_dir(self) -> dict:
        import os
        import subprocess
        try:
            p = Path(self.cpa_dir())
            p.mkdir(parents=True, exist_ok=True)
            if os.name == "nt":
                os.startfile(str(p))  # type: ignore[attr-defined]
            else:
                subprocess.Popen(["xdg-open", str(p)])
            self._log(f"已打开凭证目录：{p}")
            return {"ok": True, "path": str(p)}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    # ---------- 号池操作 ----------
    def _wrap(self, fn) -> dict:
        try:
            return {"ok": True, "data": fn()}
        except Exception as e:
            self._log(f"出错：{e}", "err")
            return {"ok": False, "error": str(e), "tb": traceback.format_exc()[-400:]}

    def test_connection(self) -> dict:
        try:
            ov = self.farm.once_overview()
            self._log(
                f"连接成功：匹配 {ov.get('safe_total')} / 其它 {ov.get('other_total')}", "ok"
            )
            return {"ok": True, "overview": ov}
        except Exception as e:
            self._log(f"连接失败：{e}", "err")
            return {"ok": False, "error": str(e)}

    def overview(self) -> dict:
        try:
            return {"ok": True, "overview": self.farm.once_overview()}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def import_cpa(self) -> dict:
        try:
            stats = self.farm.once_import(log=self._logcb())
            return {"ok": True, "stats": stats}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def clean(self, opts: dict = None) -> dict:
        try:
            koc = (opts or {}).get("kill_on_cooldown")
            stats = self.farm.once_clean(
                log=self._logcb(),
                kill_on_cooldown=(None if koc is None else bool(koc)),
            )
            return {"ok": True, "stats": stats}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def purge_error(self, opts: dict = None) -> dict:
        try:
            status = (opts or {}).get("status") or "error"
            stats = self.farm.once_purge_dead(log=self._logcb(), status=status)
            self._log(
                f"清理死号({status})完成: 删除 {stats.get('deleted')} / 失败 {stats.get('failed')}",
                "ok",
            )
            return {"ok": True, "stats": stats}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def quota(self) -> dict:
        try:
            return {"ok": True, "quota": self.farm.once_quota(log=self._logcb())}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def smoke(self) -> dict:
        try:
            return {"ok": True, "result": self.farm.once_smoke()}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    # ---------- 农场 ----------
    def start_farm(self) -> dict:
        try:
            self.farm.start(log=self._logcb())
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def stop_farm(self) -> dict:
        self.farm.stop()
        return {"ok": True}

    def farm_state(self) -> dict:
        return dict(self.farm.state)

    # ---------- 日志 ----------
    def take_logs(self) -> list:
        return self.bus.take()

    # ---------- 教程 ----------
    def get_guide_md(self) -> str:
        try:
            p = guide_md_path()
            if p.exists():
                return p.read_text(encoding="utf-8")
            return "# 教程缺失\n找不到 docs/cloudflare_temp_email.md"
        except Exception as e:
            return f"# 读取失败\n{e}"
