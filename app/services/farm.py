"""农场循环：注册(可选) → 导入 sub2api → 测活 → 可选杀号。"""
from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Callable, Optional

from app.config import CPA_DIR, DATA_DIR, app_dir, load_config, save_config
from app.services.pool import clean_pool, import_cpa_dir, pool_overview, retest_isolated_accounts, summarize_quota
from app.services.register_bridge import run_external_register
from app.services.sub2api import Sub2ApiClient


def _resolve_cwd(cwd: str) -> str:
    """external_register_cwd 相对 app_dir 解析(支持 vendor/grok-register 相对路径)。"""
    if not cwd:
        return ""
    p = Path(cwd)
    if not p.is_absolute():
        p = app_dir() / cwd
    return str(p)

LogCb = Optional[Callable[[str], None]]
StateCb = Optional[Callable[[dict], None]]


class FarmController:
    def __init__(self):
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self.state = {
            "running": False,
            "loops": 0,
            "imported_ok": 0,
            "deleted": 0,
            "last_error": "",
            "updated_at": "",
        }
        self._state_path = DATA_DIR / "farm_state.json"
        self._load_state()
        # 新进程: 上次的农场线程不可能存活, 强制 running=False
        # (否则 farm_state.json 残留 running=True 会让 UI 误判农场在跑, 按钮状态反)
        self.state["running"] = False
        self._save_state()

    def _load_state(self) -> None:
        if self._state_path.exists():
            try:
                self.state.update(json.loads(self._state_path.read_text(encoding="utf-8")))
            except Exception:
                pass

    def _save_state(self) -> None:
        self.state["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        self._state_path.write_text(
            json.dumps(self.state, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def is_running(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def start(self, log: LogCb = None, on_state: StateCb = None) -> None:
        if self.is_running():
            if log:
                log("农场已在运行")
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._loop, args=(log, on_state), name="farm-loop", daemon=True
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _client(self, cfg: dict) -> Sub2ApiClient:
        return Sub2ApiClient(
            base=cfg["sub2api_base"],
            email=cfg["sub2api_email"],
            password=cfg["sub2api_password"],
        )

    def _loop(self, log: LogCb, on_state: StateCb) -> None:
        self.state["running"] = True
        self._save_state()
        if log:
            log("农场循环启动")
        try:
            while not self._stop.is_set():
                cfg = load_config()
                self.state["loops"] = int(self.state.get("loops") or 0) + 1
                loop = self.state["loops"]
                if log:
                    log(f"======== LOOP {loop} ========")
                try:
                    client = self._client(cfg)
                    client.login()
                    # 趋势采样放在 LOOP 开头(login 后/注册前), 避免注册卡住导致整轮无点
                    try:
                        from app.services import trend as _trend
                        _trend.append_trend(client)
                    except Exception:
                        pass
                    if cfg.get("register_enabled") and cfg.get("external_register_cmd"):
                        _cwd = _resolve_cwd(cfg.get("external_register_cwd") or "")
                        run_external_register(
                            cmd=cfg["external_register_cmd"],
                            cwd=_cwd,
                            count=int(cfg.get("register_count") or 3),
                            config_path=str(Path(_cwd) / "config.json") if _cwd else "",
                            log=log,
                            silent=bool(cfg.get("register_silent", True)),
                        )
                    cpa_dir = Path(cfg.get("cpa_dir") or CPA_DIR)
                    _icwd = _resolve_cwd(cfg.get("external_register_cwd") or "")
                    if _icwd:
                        ext = Path(_icwd) / "cpa_auths"
                        if ext.exists():
                            cpa_dir = ext
                    stats = import_cpa_dir(
                        client=client,
                        cpa_dir=cpa_dir,
                        group_id=int(cfg.get("sub2api_group_id") or 1),
                        proxy_id=int(cfg.get("sub2api_proxy_id") or 0),
                        safe_suffix=cfg.get("sub2api_safe_suffix") or "",
                        test_after=bool(cfg.get("import_test_after", False)),
                        auto_kill_bad=bool(cfg.get("auto_kill_bad", True)),
                        kill_on_cooldown=bool(cfg.get("kill_on_cooldown", False)),
                        log=log,
                    )
                    self.state["imported_ok"] = int(self.state.get("imported_ok") or 0) + int(
                        stats.get("imported") or 0
                    )
                    self.state["deleted"] = int(self.state.get("deleted") or 0) + int(
                        stats.get("deleted") or 0
                    )
                    self.state["last_error"] = ""
                    # 延迟复测: 对冷却/临时隔离账号到期后重新测活
                    try:
                        rt = retest_isolated_accounts(
                            client=client,
                            retest_delay_hours=int(cfg.get("retest_delay_hours") or 6),
                            concurrency=int(cfg.get("test_concurrency") or 8),
                            auto_kill_bad=bool(cfg.get("auto_kill_bad", True)),
                            log=log,
                        )
                        if rt.get("activated"):
                            self.state["retest_activated"] = int(self.state.get("retest_activated") or 0) + rt["activated"]
                    except Exception:
                        pass
                except Exception as e:
                    self.state["last_error"] = str(e)
                    if log:
                        log(f"loop 异常: {e}")
                self._save_state()
                if on_state:
                    on_state(dict(self.state))
                # 等待间隔，可被 stop 打断
                for _ in range(30):
                    if self._stop.is_set():
                        break
                    time.sleep(1)
        finally:
            self.state["running"] = False
            self._save_state()
            if on_state:
                on_state(dict(self.state))
            if log:
                log("农场循环已停止")

    # 单次操作封装（给 GUI 按钮用）
    def once_import(self, log: LogCb = None) -> dict:
        cfg = load_config()
        client = self._client(cfg)
        client.login()
        cpa_dir = Path(cfg.get("cpa_dir") or CPA_DIR)
        _icwd = _resolve_cwd(cfg.get("external_register_cwd") or "")
        if _icwd:
            ext = Path(_icwd) / "cpa_auths"
            if ext.exists():
                cpa_dir = ext
        return import_cpa_dir(
            client=client,
            cpa_dir=cpa_dir,
            group_id=int(cfg.get("sub2api_group_id") or 1),
            proxy_id=int(cfg.get("sub2api_proxy_id") or 0),
            safe_suffix=cfg.get("sub2api_safe_suffix") or "",
            test_after=bool(cfg.get("import_test_after", False)),
            auto_kill_bad=bool(cfg.get("auto_kill_bad", True)),
            kill_on_cooldown=bool(cfg.get("kill_on_cooldown", False)),
            log=log,
        )

    def once_clean(self, log: LogCb = None, kill_on_cooldown: bool = None) -> dict:
        cfg = load_config()
        if kill_on_cooldown is None:
            kill_on_cooldown = bool(cfg.get("kill_on_cooldown", False))
        client = self._client(cfg)
        client.login()
        return clean_pool(
            client=client,
            safe_suffix=cfg.get("sub2api_safe_suffix") or "",
            concurrency=int(cfg.get("test_concurrency") or 8),
            auto_kill=bool(cfg.get("auto_kill_bad", True)),
            kill_on_cooldown=kill_on_cooldown,
            log=log,
        )

    def once_purge_dead(self, log: LogCb = None, status: str = "error") -> dict:
        """一键清理死号(默认 status=error, refresh token revoked 的尸体)。"""
        from app.services.pool import purge_dead_accounts
        cfg = load_config()
        client = self._client(cfg)
        client.login()
        return purge_dead_accounts(
            client=client,
            status=status,
            concurrency=int(cfg.get("test_concurrency") or 12),
            log=log,
        )

    def once_overview(self) -> dict:
        cfg = load_config()
        client = self._client(cfg)
        client.login()
        # 采样放到后台线程, 不挡 overview 返回(避免打开/刷新变慢)
        try:
            from app.services import trend as _trend

            def _bg():
                try:
                    _trend.append_trend(client)
                except Exception:
                    pass

            threading.Thread(target=_bg, name="trend-sample", daemon=True).start()
        except Exception:
            pass
        return pool_overview(client, safe_suffix=cfg.get("sub2api_safe_suffix") or "")

    def once_quota(self, log: LogCb = None) -> dict:
        cfg = load_config()
        client = self._client(cfg)
        client.login()
        return summarize_quota(
            client=client,
            safe_suffix=cfg.get("sub2api_safe_suffix") or "",
            sample=20,
            log=log,
        )

    def once_smoke(self) -> dict:
        cfg = load_config()
        client = self._client(cfg)
        client.login()
        keys = client.list_keys(group_id=int(cfg.get("sub2api_group_id") or 1))
        key = next((k.get("key") for k in keys if k.get("status") == "active"), None)
        if not key:
            return {"ok": False, "error": "no active key in group"}
        return client.smoke_chat(
            api_key=key,
            model=cfg.get("test_model") or "grok-4.5",
            max_tokens=int(cfg.get("max_tokens_probe") or 8),
        )
