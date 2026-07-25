"""号池运维：批量测活、自动杀号、额度汇总、CPA 凭证导入。"""
from __future__ import annotations

import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Callable, Optional

from app.services.sub2api import Sub2ApiClient

LogCb = Optional[Callable[[str], None]]


def _log(cb: LogCb, msg: str) -> None:
    if cb:
        cb(msg)


def build_credentials_from_cpa(src: dict) -> dict:
    """把 cpa_auths/*.json 转成 sub2api oauth credentials。"""
    exp_ts = int(src.get("expires_in") or 21600)
    email = src.get("email") or ""
    return {
        "access_token": src.get("access_token", ""),
        "refresh_token": src.get("refresh_token", ""),
        "id_token": src.get("id_token", ""),
        "token_type": src.get("token_type", "Bearer"),
        "expires_in": exp_ts,
        "expires_at": src.get("expired")
        or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() + exp_ts)),
        "base_url": src.get("base_url", "https://cli-chat-proxy.grok.com/v1"),
        "client_id": src.get("client_id", "b1a00492-073a-47ea-816f-4c329264a828"),
        "token_endpoint": src.get("token_endpoint", "https://auth.x.ai/oauth2/token"),
        "scope": src.get(
            "scope",
            "openid profile email offline_access grok-cli:access api:access",
        ),
        "sub": src.get("sub", ""),
        "email": email,
        "team_id": src.get("team_id", ""),
        "auth_kind": src.get("auth_kind", "oauth"),
    }


def load_cpa_files(cpa_dir: Path) -> list[dict]:
    out = []
    if not cpa_dir.exists():
        return out
    for fp in sorted(cpa_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            data = json.loads(fp.read_text(encoding="utf-8"))
            data["_file"] = str(fp)
            out.append(data)
        except Exception:
            continue
    return out


def _move_cpa_to_dead(fp) -> None:
    """把失效 cpa 文件移到 _dead/ 子目录, 避免下次循环重复导入删除。"""
    try:
        src = Path(fp)
        if not src or not src.exists():
            return
        dead_dir = src.parent / "_dead"
        dead_dir.mkdir(parents=True, exist_ok=True)
        target = dead_dir / src.name
        i = 0
        while target.exists():
            i += 1
            target = dead_dir / f"{src.stem}_dup{i}{src.suffix}"
        src.rename(target)
    except Exception:
        pass


def import_cpa_dir(
    client: Sub2ApiClient,
    cpa_dir: Path,
    group_id: int,
    proxy_id: int = 0,
    safe_suffix: str = "",
    test_after: bool = True,
    auto_kill_bad: bool = True,
    log: LogCb = None,
) -> dict:
    """扫描 cpa 目录，导入未存在的账号，可选测活+杀坏号。"""
    known = {
        str(a.get("name") or "")
        for a in client.list_accounts(platform="grok", only_suffix=safe_suffix)
    }
    files = load_cpa_files(cpa_dir)
    stats = {"scanned": len(files), "imported": 0, "skipped": 0, "deleted": 0, "failed": 0, "items": []}
    for src in files:
        email = str(src.get("email") or "").strip()
        if not email:
            stats["skipped"] += 1
            continue
        if safe_suffix and not email.endswith(safe_suffix):
            _log(log, f"跳过非安全后缀: {email}")
            stats["skipped"] += 1
            continue
        if email in known:
            stats["skipped"] += 1
            continue
        try:
            creds = build_credentials_from_cpa(src)
            res = client.import_oauth_account(
                email=email,
                credentials=creds,
                group_id=group_id,
                proxy_id=proxy_id,
            )
            aid = res["id"]
            item = {"email": email, "id": aid, "ok": True}
            if test_after:
                t = client.test_account(aid)
                item["test_ok"] = t.get("ok")
                item["test"] = t.get("text", "")[:120]
                if auto_kill_bad and (t.get("hard_fail") or not t.get("ok")):
                    client.delete_account(aid)
                    item["deleted"] = True
                    stats["deleted"] += 1
                    _move_cpa_to_dead(src.get("_file"))
                    _log(log, f"导入后测活失败已删: {email} (凭证移入 _dead)")
                else:
                    stats["imported"] += 1
                    known.add(email)
                    _log(log, f"导入成功: {email} id={aid}")
            else:
                stats["imported"] += 1
                known.add(email)
                _log(log, f"导入成功(未测): {email} id={aid}")
            stats["items"].append(item)
        except Exception as e:
            stats["failed"] += 1
            stats["items"].append({"email": email, "ok": False, "error": str(e)[:200]})
            _log(log, f"导入失败 {email}: {e}")
    return stats


def clean_pool(
    client: Sub2ApiClient,
    safe_suffix: str = "",
    concurrency: int = 8,
    auto_kill: bool = True,
    log: LogCb = None,
) -> dict:
    """一键测活；不通则可选删除。只动 safe_suffix 账号。"""
    items = client.list_accounts(platform="grok", only_suffix=safe_suffix, only_active=True)
    _log(log, f"开始清理，active 安全账号: {len(items)}")
    kept = 0
    deleted = 0
    details = []

    def one(acc: dict) -> dict:
        aid = acc.get("id")
        nm = acc.get("name")
        t = client.test_account(aid)
        row = {
            "id": aid,
            "name": nm,
            "ok": t.get("ok"),
            "hard_fail": t.get("hard_fail"),
            "status": t.get("status"),
            "snip": (t.get("text") or "")[:100],
        }
        if auto_kill and (t.get("hard_fail") or not t.get("ok")):
            try:
                client.delete_account(aid)
                row["deleted"] = True
            except Exception as e:
                row["delete_err"] = str(e)[:80]
        return row

    with ThreadPoolExecutor(max_workers=max(1, concurrency)) as ex:
        futs = {ex.submit(one, it): it for it in items}
        done = 0
        for f in as_completed(futs):
            done += 1
            row = f.result()
            details.append(row)
            if row.get("deleted"):
                deleted += 1
            else:
                kept += 1
            if done % 10 == 0 or done == len(items):
                _log(log, f"测活进度 {done}/{len(items)} 保留={kept} 删除={deleted}")
    return {"total": len(items), "kept": kept, "deleted": deleted, "details": details}


def summarize_quota(
    client: Sub2ApiClient,
    safe_suffix: str = "",
    sample: int = 20,
    log: LogCb = None,
) -> dict:
    """抽样读取额度快照，汇总 remaining tokens/requests。"""
    items = client.list_accounts(platform="grok", only_suffix=safe_suffix, only_active=True)
    sample_items = items[: max(1, sample)]
    rows = []
    req_rem = []
    tok_rem = []
    for acc in sample_items:
        snap = client.get_usage_snapshot(acc.get("id"))
        s = snap.get("snapshot") or {}
        # 兼容多种结构
        headers = s.get("headers") or {}
        requests_info = s.get("requests") or {}
        tokens_info = s.get("tokens") or {}
        rr = (
            requests_info.get("remaining")
            or headers.get("x-ratelimit-remaining-requests")
            or s.get("remaining_requests")
        )
        tr = (
            tokens_info.get("remaining")
            or headers.get("x-ratelimit-remaining-tokens")
            or s.get("remaining_tokens")
        )
        rl = (
            requests_info.get("limit")
            or headers.get("x-ratelimit-limit-requests")
            or s.get("limit_requests")
        )
        tl = (
            tokens_info.get("limit")
            or headers.get("x-ratelimit-limit-tokens")
            or s.get("limit_tokens")
        )
        try:
            if rr is not None:
                req_rem.append(int(rr))
            if tr is not None:
                tok_rem.append(int(tr))
        except Exception:
            pass
        rows.append(
            {
                "id": acc.get("id"),
                "name": acc.get("name"),
                "status": acc.get("status"),
                "remaining_requests": rr,
                "remaining_tokens": tr,
                "limit_requests": rl,
                "limit_tokens": tl,
            }
        )
    _log(log, f"额度抽样 {len(rows)}/{len(items)}")
    return {
        "active_total": len(items),
        "sampled": len(rows),
        "avg_remaining_requests": (sum(req_rem) / len(req_rem)) if req_rem else None,
        "avg_remaining_tokens": (sum(tok_rem) / len(tok_rem)) if tok_rem else None,
        "rows": rows,
    }


def pool_overview(client: Sub2ApiClient, safe_suffix: str = "") -> dict[str, Any]:
    all_acc = client.list_accounts(platform="grok")
    safe = [a for a in all_acc if str(a.get("name") or "").endswith(safe_suffix)] if safe_suffix else all_acc
    other = [a for a in all_acc if a not in safe]
    by_status: dict[str, int] = {}
    for a in safe:
        st = str(a.get("status") or "unknown")
        by_status[st] = by_status.get(st, 0) + 1
    return {
        "safe_total": len(safe),
        "other_total": len(other),
        "by_status": by_status,
        "safe_active": by_status.get("active", 0),
        "accounts": safe,
    }
