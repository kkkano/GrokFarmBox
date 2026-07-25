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
    kill_on_cooldown: bool = True,
    log: LogCb = None,
) -> dict:
    """扫描 cpa 目录并导入。

    不再整池 list_accounts 查重(号多时会卡死 UI/农场)。
    重复号由 sub2api 返回错误后跳过; 本轮内存 known 防重复文件。
    """
    known: set[str] = set()
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
                if t.get("permanent"):  # 永久失效: 必删
                    client.delete_account(aid)
                    item["deleted"] = True
                    stats["deleted"] += 1
                    _move_cpa_to_dead(src.get("_file"))
                    _log(log, f"导入后永久失效已删: {email}")
                elif t.get("cooldown"):  # 冷却(额度用尽/限流)
                    if kill_on_cooldown:
                        client.delete_account(aid)
                        item["deleted"] = True; stats["deleted"] += 1
                        _move_cpa_to_dead(src.get("_file"))
                        _log(log, f"导入后冷却已删: {email}")
                    else:
                        client.set_account_status(aid, "inactive")
                        stats["imported"] += 1; known.add(email)
                        _log(log, f"导入成功(冷却暂停): {email}")
                elif not t.get("ok"):  # 其它失败
                    if kill_on_cooldown:
                        client.delete_account(aid)
                        item["deleted"] = True; stats["deleted"] += 1
                        _move_cpa_to_dead(src.get("_file"))
                        _log(log, f"导入后测活失败已删: {email}")
                    else:
                        stats["imported"] += 1; known.add(email)
                        _log(log, f"导入成功(测活未过保留): {email}")
                else:
                    stats["imported"] += 1; known.add(email)
                    _log(log, f"导入成功: {email} id={aid}")
            else:
                stats["imported"] += 1
                known.add(email)
                _log(log, f"导入成功(未测): {email} id={aid}")
            stats["items"].append(item)
        except Exception as e:
            err = str(e)
            low = err.lower()
            # 已存在/重复: 当跳过, 不记 failed
            if any(k in low for k in ("already", "exist", "duplicate", "冲突", "已存在", "unique", "409")):
                stats["skipped"] += 1
                known.add(email)
                _log(log, f"已存在跳过: {email}")
                continue
            stats["failed"] += 1
            stats["items"].append({"email": email, "ok": False, "error": err[:200]})
            _log(log, f"导入失败 {email}: {e}")
    return stats


def clean_pool(
    client: Sub2ApiClient,
    safe_suffix: str = "",
    concurrency: int = 8,
    auto_kill: bool = True,
    kill_on_cooldown: bool = True,
    log: LogCb = None,
) -> dict:
    """一键测活: 永久失效必删, 冷却号按 kill_on_cooldown(删/暂停), 其它失败可选删。"""
    items = client.list_accounts(platform="grok", only_suffix=safe_suffix, only_active=True)
    _log(log, f"开始清理，active 安全账号: {len(items)} (冷却号{'删' if kill_on_cooldown else '标记暂停'})")
    kept = 0; deleted = 0; paused = 0
    details = []

    def one(acc: dict) -> dict:
        aid = acc.get("id")
        nm = acc.get("name")
        t = client.test_account(aid)
        row = {
            "id": aid, "name": nm, "ok": t.get("ok"),
            "permanent": t.get("permanent"), "cooldown": t.get("cooldown"),
            "status": t.get("status"), "snip": (t.get("text") or "")[:100],
        }
        if not auto_kill:
            return row
        if t.get("permanent"):  # 永久失效: 必删
            try:
                client.delete_account(aid); row["deleted"] = True
            except Exception as e:
                row["delete_err"] = str(e)[:80]
        elif t.get("cooldown"):  # 冷却(额度用尽/限流)
            if kill_on_cooldown:
                try:
                    client.delete_account(aid); row["deleted"] = True
                except Exception as e:
                    row["delete_err"] = str(e)[:80]
            else:
                try:
                    client.set_account_status(aid, "inactive"); row["paused"] = True
                except Exception as e:
                    row["pause_err"] = str(e)[:80]
        elif not t.get("ok"):  # 其它失败(非永久非冷却)
            if kill_on_cooldown:
                try:
                    client.delete_account(aid); row["deleted"] = True
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
            if row.get("deleted"): deleted += 1
            elif row.get("paused"): paused += 1
            else: kept += 1
            if done % 10 == 0 or done == len(items):
                _log(log, f"测活进度 {done}/{len(items)} 保留={kept} 暂停={paused} 删除={deleted}")
    return {"total": len(items), "kept": kept, "paused": paused, "deleted": deleted, "details": details}


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
    """号池概况(轻量, 秒回)。

    只拉 platform=grok 第 1 页:
    - total 用接口 total
    - safe_active 用本页 active 比例粗估(避免 status=active 过滤在 sub2api 上超时)
    - accounts 用本页匹配后缀号
    """
    client.login()
    data = client._req(
        "get",
        "/api/v1/admin/accounts?platform=grok&page=1&page_size=50",
        timeout=45,
    ).get("data") or {}
    total = int(data.get("total") or 0)
    items = data.get("items") or []
    if safe_suffix:
        accounts = [a for a in items if str(a.get("name") or "").endswith(safe_suffix)]
        other_in_page = len(items) - len(accounts)
    else:
        accounts = list(items)
        other_in_page = 0
    active_in_page = sum(1 for a in accounts if a.get("status") == "active")
    # 用本页 active 比例估算全池可用数
    if accounts:
        ratio = active_in_page / max(1, len(accounts))
        safe_active = int(round(total * ratio)) if not other_in_page else active_in_page
    else:
        safe_active = 0
    try:
        accounts = sorted(accounts, key=lambda x: int(x.get("id") or 0), reverse=True)
    except Exception:
        pass
    return {
        "safe_total": total if not other_in_page else max(0, total - other_in_page),
        "other_total": other_in_page,
        "by_status": {"active": safe_active},
        "safe_active": safe_active,
        "accounts": accounts[:50],
        "listed": min(50, len(accounts)),
        "approx": True,
    }
