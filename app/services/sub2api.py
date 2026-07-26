"""sub2api 管理端客户端：登录、账号 CRUD、测活、额度读取。"""
from __future__ import annotations

import time
from typing import Any, Callable, Optional

from curl_cffi import requests as cr

ProgressCb = Optional[Callable[[str], None]]


class Sub2ApiError(RuntimeError):
    pass


class Sub2ApiClient:
    def __init__(
        self,
        base: str,
        email: str,
        password: str,
        timeout: int = 30,
        impersonate: str = "chrome110",
    ):
        self.base = (base or "").rstrip("/")
        self.email = email
        self.password = password
        self.timeout = timeout
        self.impersonate = impersonate
        self._token: str = ""
        self._token_at: float = 0.0

    # ---------- low level ----------
    def _headers(self, auth: bool = True) -> dict[str, str]:
        h = {"Accept": "application/json", "Content-Type": "application/json"}
        if auth and self._token:
            h["Authorization"] = f"Bearer {self._token}"
        return h

    def _req(self, method: str, path: str, **kwargs) -> Any:
        url = f"{self.base}{path}"
        kwargs.setdefault("timeout", self.timeout)
        kwargs.setdefault("impersonate", self.impersonate)
        kwargs.setdefault("headers", self._headers())
        try:
            r = getattr(cr, method.lower())(url, **kwargs)
        except Exception as e:
            raise Sub2ApiError(f"网络错误 {method} {path}: {e}") from e
        if r.status_code == 401 and path != "/api/v1/auth/login":
            self.login(force=True)
            kwargs["headers"] = self._headers()
            r = getattr(cr, method.lower())(url, **kwargs)
        if r.status_code >= 400:
            raise Sub2ApiError(f"{method} {path} -> {r.status_code}: {(r.text or '')[:240]}")
        try:
            return r.json()
        except Exception:
            return {"raw": r.text, "status": r.status_code}

    def login(self, force: bool = False) -> str:
        if self._token and not force and time.time() - self._token_at < 50 * 60:
            return self._token
        data = self._req(
            "post",
            "/api/v1/auth/login",
            json={"email": self.email, "password": self.password},
            headers=self._headers(auth=False),
        )
        tok = ((data.get("data") or {}).get("access_token")) or ""
        if not tok:
            raise Sub2ApiError(f"登录失败: {data}")
        self._token = tok
        self._token_at = time.time()
        return tok

    # ---------- accounts ----------
    def list_accounts(
        self,
        platform: str = "grok",
        page_size: int = 100,
        max_pages: int = 40,
        only_suffix: str = "",
        only_active: bool = False,
    ) -> list[dict]:
        """列出账号。先拉第 1 页拿 total, 再并发拉剩余页, 避免串行超时像「按钮没反应」。"""
        from concurrent.futures import ThreadPoolExecutor, as_completed

        self.login()

        def _fetch(page: int) -> dict:
            last_err: Exception | None = None
            for attempt in range(3):
                try:
                    return self._req(
                        "get",
                        f"/api/v1/admin/accounts?platform={platform}&page={page}&page_size={page_size}",
                        timeout=45,
                    ).get("data") or {}
                except Exception as e:
                    last_err = e
                    time.sleep(0.4 * (attempt + 1))
            raise Sub2ApiError(f"list_accounts page={page} 失败: {last_err}")

        def _filter(items: list) -> list[dict]:
            out: list[dict] = []
            for it in items or []:
                nm = str(it.get("name") or "")
                if only_suffix and not nm.endswith(only_suffix):
                    continue
                if only_active and it.get("status") != "active":
                    continue
                out.append(it)
            return out

        first = _fetch(1)
        total = int(first.get("total") or 0)
        pages = max(1, min(max_pages, (total + page_size - 1) // page_size if total else 1))
        by_page: dict[int, list] = {1: _filter(first.get("items") or [])}

        if pages > 1:
            with ThreadPoolExecutor(max_workers=min(8, pages - 1)) as ex:
                futs = {ex.submit(_fetch, p): p for p in range(2, pages + 1)}
                for fut in as_completed(futs):
                    p = futs[fut]
                    data = fut.result()
                    by_page[p] = _filter(data.get("items") or [])

        out: list[dict] = []
        for p in range(1, pages + 1):
            out.extend(by_page.get(p) or [])
        return out

    def import_oauth_account(
        self,
        email: str,
        credentials: dict,
        group_id: int,
        proxy_id: int = 0,
        notes: str = "GrokFarmBox",
        concurrency: int = 5,
    ) -> dict:
        self.login()
        body = {
            "name": email,
            "notes": notes,
            "platform": "grok",
            "type": "oauth",
            "credentials": credentials,
            "extra": {"email": email, "source": "GrokFarmBox"},
            "group_ids": [group_id],
            "concurrency": concurrency,
            "priority": 1,
            "auto_pause_on_expired": True,
        }
        data = self._req("post", "/api/v1/admin/accounts", json=body)
        aid = (data.get("data") or {}).get("id")
        if not aid:
            raise Sub2ApiError(f"导入失败: {data}")
        if proxy_id:
            try:
                self._req("put", f"/api/v1/admin/accounts/{aid}", json={"proxy_id": proxy_id})
            except Exception:
                pass
        return {"id": aid, "email": email, "raw": data.get("data")}

    def delete_account(self, account_id: int | str) -> None:
        self.login()
        self._req("delete", f"/api/v1/admin/accounts/{account_id}")

    def list_ids_by_status(
        self, platform: str = "grok", status: str = "error", page_size: int = 100, max_pages: int = 60
    ) -> list:
        """拉取指定 status 的全部账号 id(批量清理死号用)。"""
        self.login()
        ids = []
        page = 1
        while page <= max_pages:
            d = self._req(
                "get",
                f"/api/v1/admin/accounts?platform={platform}&status={status}&page={page}&page_size={page_size}",
                timeout=45,
            ).get("data") or {}
            items = d.get("items") or []
            if not items:
                break
            ids.extend(it.get("id") for it in items if it.get("id") is not None)
            if len(items) < page_size:
                break
            page += 1
        return ids

    def test_account(self, account_id: int | str) -> dict:
        """调用管理端 test 接口，返回 {ok, text, status}。"""
        self.login()
        url = f"{self.base}/api/v1/admin/accounts/{account_id}/test"
        try:
            r = cr.post(
                url,
                headers=self._headers(),
                timeout=max(self.timeout, 60),
                impersonate=self.impersonate,
            )
            text = r.text or ""
        except Exception as e:
            # 超时/网络异常: 当冷却(保守不杀), 避免误杀慢号
            return {"ok": False, "text": f"timeout/err: {e}", "status": 0, "hard_fail": False, "permanent": False, "cooldown": True}
        low = text.lower()
        # 永久失效(权限没了/号被删): 必杀
        permanent_keys = [
            "permission-denied",
            "runtime has been deleted",
            "forbidden",
            "unauthorized",
            "access to the chat endpoint is denied",
            "invalid_grant",
            "refresh token has been revoked",
            "token refresh failed",
        ]
        # 冷却(额度用尽/限流): 可选杀或标记暂停
        cooldown_keys = [
            "spending-limit",
            "payment required",
            '"code":402',
            '"status":402',
            "out of credits",
            "quota",
            "rate limit",
            "rate-limit",
            "too many requests",
        ]
        permanent = any(k in low for k in permanent_keys) or r.status_code in (401, 403)
        cooldown = any(k in low for k in cooldown_keys) or r.status_code in (402, 429)
        soft_ok = r.status_code < 400 and '"type":"error"' not in text.replace(" ", "")
        ok = soft_ok and not permanent and not cooldown
        return {
            "ok": ok,
            "text": text[:400],
            "status": r.status_code,
            "hard_fail": permanent,  # 兼容旧字段: 永久失效=hard
            "permanent": permanent,
            "cooldown": cooldown,
        }

    def set_account_status(self, account_id: int | str, status: str) -> None:
        """设置账号状态(active/inactive/error)。冷却号可设 inactive 暂停, 不删。"""
        self.login()
        self._req("put", f"/api/v1/admin/accounts/{account_id}", json={"status": status})

    def get_usage_snapshot(self, account_id: int | str) -> dict:
        """尽量读取账号额度快照（字段因 sub2api 版本而异）。"""
        self.login()
        try:
            data = self._req("get", f"/api/v1/admin/accounts/{account_id}")
            acc = data.get("data") or data
        except Exception as e:
            return {"error": str(e)}
        # 常见挂载点
        snap = (
            acc.get("grok_usage_snapshot")
            or acc.get("usage_snapshot")
            or acc.get("rate_limit")
            or acc.get("extra")
            or {}
        )
        if not isinstance(snap, dict):
            snap = {"raw": snap}
        return {
            "id": acc.get("id"),
            "name": acc.get("name"),
            "status": acc.get("status"),
            "proxy_id": acc.get("proxy_id"),
            "snapshot": snap,
            "updated_at": acc.get("updated_at") or acc.get("last_used_at"),
        }

    def list_keys(self, group_id: int | None = None) -> list[dict]:
        self.login()
        data = self._req("get", "/api/v1/keys?page=1&page_size=100").get("data") or {}
        items = data.get("items") or []
        if group_id is None:
            return items
        return [k for k in items if k.get("group_id") == group_id]

    def smoke_chat(
        self,
        api_key: str,
        model: str = "grok-4.5",
        max_tokens: int = 8,
        content: str = "ping",
    ) -> dict:
        """用业务 key 走 /v1/chat/completions 冒烟。"""
        url = f"{self.base}/v1/chat/completions"
        try:
            r = cr.post(
                url,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": content}],
                    "max_tokens": max_tokens,
                },
                timeout=60,
                impersonate=self.impersonate,
            )
            return {
                "ok": r.status_code == 200,
                "status": r.status_code,
                "text": (r.text or "")[:300],
                "headers": {
                    k: r.headers.get(k)
                    for k in (
                        "x-ratelimit-limit-requests",
                        "x-ratelimit-limit-tokens",
                        "x-ratelimit-remaining-requests",
                        "x-ratelimit-remaining-tokens",
                    )
                    if r.headers.get(k) is not None
                },
            }
        except Exception as e:
            return {"ok": False, "status": 0, "text": str(e), "headers": {}}
