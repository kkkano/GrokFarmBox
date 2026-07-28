"""GrokFarmBox 配置模型：默认值、加载、保存、校验。"""
from __future__ import annotations

import json
import os
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any


def app_dir() -> Path:
    """打包成 exe 后写到 exe 同目录；开发时写到项目根。"""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


DATA_DIR = app_dir() / "data"
CONFIG_PATH = DATA_DIR / "config.json"
LOG_DIR = DATA_DIR / "logs"
CPA_DIR = DATA_DIR / "cpa_auths"

DEFAULT_CONFIG: dict[str, Any] = {
    # --- sub2api ---
    "sub2api_base": "http://127.0.0.1:8080",
    "sub2api_email": "admin@example.com",
    "sub2api_password": "",
    "sub2api_group_id": 1,
    "sub2api_proxy_id": 0,
    "sub2api_safe_suffix": "",
    # --- Cloudflare 临时邮箱 ---
    "cf_api_base": "",
    "cf_admin_token": "",
    "cf_domain": "",
    "cf_auth_mode": "x-admin-auth",  # none | bearer | x-api-key | x-admin-auth | query-key
    # --- 注册 ---
    "proxy": "",
    "register_count": 3,
    "register_enabled": True,
    "register_silent": True,
    "cpa_export_enabled": True,
    "cpa_base_url": "https://cli-chat-proxy.grok.com/v1",
    "cpa_headless": False,
    "external_register_cmd": ".venv\\Scripts\\python.exe grok_register_ttk.py cli",
    "external_register_cwd": "vendor/grok-register",
    # --- 农场 / 清理 ---
    "auto_kill_bad": True,
    "kill_on_cooldown": False,  # 冷却号(额度用尽/限流)也删; False=只设inactive暂停等恢复. 永久失效号始终删
    "import_test_after": False,  # 导入时是否测活(调grok占用上游, 业务高峰建议关, 靠failover+定期清理)
    "retest_delay_hours": 6,  # 冷却/临时失败账号的延迟复测间隔(小时)
    "clean_interval_min": 120,
    "test_concurrency": 8,
    "test_model": "grok-4.5",
    "max_tokens_probe": 8,
    # --- UI ---
    "theme": "dark",
    "accent": "blue",
    "refresh_sec": 30,
}


class ConfigError(RuntimeError):
    pass


def ensure_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    CPA_DIR.mkdir(parents=True, exist_ok=True)


def load_config() -> dict[str, Any]:
    ensure_dirs()
    if not CONFIG_PATH.exists():
        cfg = deepcopy(DEFAULT_CONFIG)
        save_config(cfg)
        return cfg
    try:
        raw = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception as e:
        raise ConfigError(f"配置文件损坏: {e}") from e
    if not isinstance(raw, dict):
        raise ConfigError("配置根节点必须是 JSON 对象")
    cfg = {**DEFAULT_CONFIG, **raw}
    return cfg


def save_config(cfg: dict[str, Any]) -> None:
    ensure_dirs()
    merged = {**DEFAULT_CONFIG, **(cfg or {})}
    tmp = CONFIG_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, CONFIG_PATH)


def mask_secret(value: str, keep: int = 4) -> str:
    text = str(value or "")
    if len(text) <= keep:
        return "*" * len(text)
    return text[:keep] + "*" * (len(text) - keep)
