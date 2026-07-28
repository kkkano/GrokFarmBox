"""号池运维：批量测活、自动杀号、额度汇总、CPA 凭证导入。"""
from __future__ import annotations

import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Callable, Optional

from app.services.sub2api import Sub2ApiClient

LogCb = Optional[Callable[[str], None]]

RETEST_QUEUE_FILE = Path(__file__).resolve().parent.parent.parent / "data" / "retest_queue.jsonl"


def _log(cb: LogCb, msg: str) -> None:
    if cb:
        cb(msg)


def _retest_queue_append(account_id: int, email: str, reason: str) -> None:
    """将冷却/临时失败的账号加入延迟复测队列。"""
    try:
        RETEST_QUEUE_FILE.parent.mkdir(parents=True, exist_ok=True)
        entry = {"id": account_id, "email": email, "reason": reason, "isolated_at": time.time()}
        with RETEST_QUEUE_FILE.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass


def _retest_queue_read() -> list[dict]:
    """读取复测队列文件。"""
    if not RETEST_QUEUE_FILE.exists():
        return []
    entries = []
    try:
        for line in RETEST_QUEUE_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    except Exception:
        return []
    return entries


def _retest_queue_write(entries: list[dict]) -> None:
    """重写复测队列文件。"""
    try:
        RETEST_QUEUE_FILE.write_text(
            "".join(json.dumps(e, ensure_ascii=False) + "\n" for e in entries),
            encoding="utf-8",
        )
    except Exception:
        pass


def retest_isolated_accounts(
    client: Sub2ApiClient,
    retest_delay_hours: int = 6,
    concurrency: int = 8,
    auto_kill_bad: bool = True,
    log: LogCb = None,
) -> dict:
    """对延迟复测队列中到期的账号重新测活。

    - 成功: 开放调度
    - 永久失效: 删除
    - 仍冷却/临时: 更新隔离时间, 等待下次复测
    """
    entries = _retest_queue_read()
    now = time.time()
    due = [e for e in entries if now - e.get("isolated_at", 0) >= retest_delay_hours * 3600]
    not_due = [e for e in entries if now - e.get("isolated_at", 0) < retest_delay_hours * 3600]

    _log(log, f"复测队列: 到期={len(due)}, 等待={len(not_due)}")
    if not due:
        return {"due": 0, "not_due": len(not_due), "activated": 0, "deleted": 0, "re_isolated": 0}

    activated = deleted = re_isolated = 0

    def one(entry: dict) -> str:
        nonlocal activated, deleted, re_isolated
        aid = entry.get("id")
        try:
            t = client.test_account(aid)
        except Exception:
            re_isolated += 1
            return "error"
        if t.get("ok"):
            try:
                client.activate_after_test(aid)
            except Exception:
                pass
            activated += 1
            return "activated"
        if t.get("permanent") and auto_kill_bad:
            try:
                client.delete_account(aid)
            except Exception:
                pass
            deleted += 1
            return "deleted"
        entry["isolated_at"] = now
        entry["reason"] = t.get("text", "")[:200]
        re_isolated += 1
        return "re_isolated"

    if due:
        with ThreadPoolExecutor(max_workers=max(1, concurrency)) as ex:
            futs = {ex.submit(one, e): e for e in due}
            done = 0
            for f in as_completed(futs):
                done += 1
                f.result()
                if done % 20 == 0 or done == len(due):
                    _log(log, f"复测进度 {done}/{len(due)} 激活={activated} 删={deleted} 再隔离={re_isolated}")

    remaining = not_due + [e for e in due if e.get("isolated_at") == now]
    _retest_queue_write(remaining)

    return {"due": len(due), "not_due": len(not_due), "activated": activated, "deleted": deleted, "re_isolated": re_isolated}


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
        "expires_at": src.get("expires_at")
        or src.get("expired")
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
                if t.get("ok"):  # 成功: 开放调度
                    client.activate_after_test(aid)
                    stats["imported"] += 1; known.add(email)
                    _log(log, f"导入成功: {email} id={aid}")
                elif t.get("permanent"):  # 永久失效: 必删
                    client.delete_account(aid)
                    item["deleted"] = True
                    stats["deleted"] += 1
                    _move_cpa_to_dead(src.get("_file"))
                    _log(log, f"导入后永久失效已删: {email}")
                elif t.get("cooldown") or t.get("transient"):  # 额度/临时: 隔离保留
                    client.isolate_after_failure(aid, reason=t.get("text", ""))
                    _retest_queue_append(aid, email, t.get("text", ""))
                    stats["imported"] += 1; known.add(email)
                    _log(log, f"导入成功(冷却/临时隔离): {email}")
                else:  # 其它失败: 隔离保留, 不删
                    client.isolate_after_failure(aid, reason=t.get("text", ""))
                    _retest_queue_append(aid, email, t.get("text", ""))
                    stats["imported"] += 1; known.add(email)
                    _log(log, f"导入成功(测活未过隔离): {email}")
            else:
                # 不测活: 保持隔离状态, 等待后续 clean_pool 或手动测活
                stats["imported"] += 1
                known.add(email)
                _log(log, f"导入成功(隔离未测): {email} id={aid}")
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
        elif t.get("ok"):  # 成功: 开放调度
            try:
                client.activate_after_test(aid)
            except Exception as e:
                row["activate_err"] = str(e)[:80]
        elif t.get("cooldown") or t.get("transient"):  # 额度/临时: 隔离保留
            if kill_on_cooldown:
                try:
                    client.delete_account(aid); row["deleted"] = True
                except Exception as e:
                    row["delete_err"] = str(e)[:80]
            else:
                try:
                    client.isolate_after_failure(aid, reason=t.get("text", ""))
                    row["paused"] = True
                except Exception as e:
                    row["pause_err"] = str(e)[:80]
        elif not t.get("ok"):  # 其它失败: 隔离保留, 不删
            try:
                client.isolate_after_failure(aid, reason=t.get("text", ""))
                row["paused"] = True
            except Exception as e:
                row["pause_err"] = str(e)[:80]
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


def purge_dead_accounts(
    client: Sub2ApiClient,
    status: str = "error",
    concurrency: int = 12,
    log: LogCb = None,
) -> dict:
    """批量删除指定 status 的账号(默认 error)。

    ⚠️ 注意: 并非所有 error 账号都是真死号。旧版 sub2api 可能因缺少 Grok CLI
    请求头而把正常账号误标为 error。建议先用 clean_pool 测活确认后再清理,
    或确保 sub2api 已升级到包含 PR #4009 的版本。
    """
    ids = client.list_ids_by_status(platform="grok", status=status)
    _log(log, f"待清理 status={status} 死号: {len(ids)}")
    deleted = failed = 0

    def one(aid):
        try:
            client.delete_account(aid)
            return True
        except Exception:
            return False

    if ids:
        with ThreadPoolExecutor(max_workers=max(1, concurrency)) as ex:
            futs = {ex.submit(one, i): i for i in ids}
            done = 0
            for f in as_completed(futs):
                done += 1
                if f.result():
                    deleted += 1
                else:
                    failed += 1
                if done % 200 == 0 or done == len(ids):
                    _log(log, f"清理进度 {done}/{len(ids)} 删={deleted} 失败={failed}")
    return {"status": status, "total": len(ids), "deleted": deleted, "failed": failed}


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
    """号池概况(轻量, 秒回)。优先用 status=active 的准确 total, 超时则用第1页估算。"""
    client.login()

    def _page(status: str = "", page_size: int = 50) -> dict:
        qs = f"/api/v1/admin/accounts?platform=grok&page=1&page_size={page_size}"
        if status:
            qs += f"&status={status}"
        return client._req("get", qs, timeout=45).get("data") or {}

    # 优先: status=active 准确 total
    active_total = None
    try:
        ad = _page(status="active", page_size=5)
        active_total = int(ad.get("total") or 0)
    except Exception:
        active_total = None  # 超时则fallback

    all_data = _page(page_size=50)
    total = int(all_data.get("total") or 0)
    items = all_data.get("items") or []
    if safe_suffix:
        accounts = [a for a in items if str(a.get("name") or "").endswith(safe_suffix)]
        other_in_page = len(items) - len(accounts)
    else:
        accounts = list(items)
        other_in_page = 0

    if active_total is None:
        # fallback: 第1页 active 比例估算(可能不准, 标记 approx)
        active_in_page = sum(1 for a in accounts if a.get("status") == "active")
        ratio = active_in_page / max(1, len(accounts)) if accounts else 0
        active_total = int(round(total * ratio))

    try:
        accounts = sorted(accounts, key=lambda x: int(x.get("id") or 0), reverse=True)
    except Exception:
        pass
    return {
        "safe_total": total,
        "other_total": other_in_page,
        "by_status": {"active": active_total},
        "safe_active": active_total,
        "accounts": accounts[:50],
        "listed": min(50, len(accounts)),
        "approx": active_total is None,  # True=估算(可能不准), False=准确
    }
