"""注册桥：可选调用外部 grok 注册机，或只消费本地 CPA 凭证目录。

傻瓜式 EXE 默认不强绑浏览器自动化依赖；
若用户本机已有 grok-register，可在设置里填 external_register_cmd。
"""
from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path
from typing import Callable, Optional

LogCb = Optional[Callable[[str], None]]


def _log(cb: LogCb, msg: str) -> None:
    if cb:
        cb(msg)


def run_external_register(
    cmd: str,
    cwd: str = "",
    count: int = 3,
    timeout_sec: int = 45 * 60,
    config_path: str = "",
    log: LogCb = None,
    silent: bool = False,
) -> dict:
    """执行外部注册命令。

    约定：
      - cmd 可以是 `python grok_register_ttk.py cli` 这类完整命令
      - 若提供 config_path 且为 json，会尝试写入 register_count
      - stdin 发送 start\\n（兼容现有 cli）
    """
    if not cmd or not cmd.strip():
        return {"ok": False, "error": "未配置 external_register_cmd"}
    workdir = cwd.strip() or None
    if config_path and Path(config_path).exists():
        try:
            p = Path(config_path)
            cfg = json.loads(p.read_text(encoding="utf-8"))
            cfg["register_count"] = int(count)
            cfg["browser_silent"] = bool(silent)
            p.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
            _log(log, f"已写入 register_count={count} browser_silent={bool(silent)} -> {config_path}")
        except Exception as e:
            _log(log, f"写外部 config 失败: {e}")

    _log(log, f"启动外部注册: {cmd} (cwd={workdir or '.'})")
    t0 = time.time()
    try:
        proc = subprocess.run(
            cmd,
            cwd=workdir,
            shell=True,
            input="start\n",
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_sec,
            capture_output=True,
        )
        out = (proc.stdout or "")[-2000:]
        err = (proc.stderr or "")[-1000:]
        _log(log, f"外部注册结束 rc={proc.returncode} 耗时={int(time.time()-t0)}s")
        return {
            "ok": proc.returncode == 0,
            "returncode": proc.returncode,
            "stdout_tail": out,
            "stderr_tail": err,
            "elapsed": int(time.time() - t0),
        }
    except subprocess.TimeoutExpired:
        _log(log, "外部注册超时")
        return {"ok": False, "error": "timeout", "elapsed": int(time.time() - t0)}
    except Exception as e:
        _log(log, f"外部注册异常: {e}")
        return {"ok": False, "error": str(e), "elapsed": int(time.time() - t0)}
