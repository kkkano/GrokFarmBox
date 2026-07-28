"""测试隔离导入与安全分类逻辑。"""
import json
import time
import unittest
from unittest.mock import MagicMock, patch

from app.services.pool import (
    build_credentials_from_cpa,
    _retest_queue_append,
    _retest_queue_read,
    _retest_queue_write,
    RETEST_QUEUE_FILE,
)
from app.services.sub2api import Sub2ApiClient


class TestBuildCredentials(unittest.TestCase):
    """测试 expires_at / expired 兼容性。"""

    def test_expires_at_preferred(self):
        src = {"expires_at": "2026-01-01T00:00:00Z", "expired": "2025-01-01T00:00:00Z"}
        creds = build_credentials_from_cpa(src)
        self.assertEqual(creds["expires_at"], "2026-01-01T00:00:00Z")

    def test_expired_fallback(self):
        src = {"expired": "2026-06-01T00:00:00Z"}
        creds = build_credentials_from_cpa(src)
        self.assertEqual(creds["expires_at"], "2026-06-01T00:00:00Z")

    def test_neither_uses_expires_in(self):
        src = {"expires_in": 3600}
        creds = build_credentials_from_cpa(src)
        self.assertIn("T", creds["expires_at"])  # ISO format


class TestPermanentClassification(unittest.TestCase):
    """测试永久失效判定只认明确凭证吊销。"""

    def _make_client(self, status_code, text):
        client = Sub2ApiClient.__new__(Sub2ApiClient)
        client.base = "http://test"
        client._token = "tok"
        client._token_at = time.time()
        client.timeout = 30
        client.impersonate = "chrome110"
        client.login = MagicMock()
        mock_resp = MagicMock()
        mock_resp.status_code = status_code
        mock_resp.text = text
        return client, mock_resp

    def test_invalid_grant_is_permanent(self):
        client, resp = self._make_client(502, '{"error":"invalid_grant"}')
        with patch("app.services.sub2api.cr.post", return_value=resp):
            result = client.test_account(1)
        self.assertTrue(result["permanent"])
        self.assertFalse(result["ok"])

    def test_403_not_permanent(self):
        client, resp = self._make_client(403, '{"error":"forbidden"}')
        with patch("app.services.sub2api.cr.post", return_value=resp):
            result = client.test_account(1)
        self.assertFalse(result["permanent"])
        self.assertFalse(result["ok"])

    def test_401_not_permanent(self):
        client, resp = self._make_client(401, '{"error":"unauthorized"}')
        with patch("app.services.sub2api.cr.post", return_value=resp):
            result = client.test_account(1)
        self.assertFalse(result["permanent"])

    def test_429_is_cooldown(self):
        client, resp = self._make_client(429, '{"error":"rate limit"}')
        with patch("app.services.sub2api.cr.post", return_value=resp):
            result = client.test_account(1)
        self.assertTrue(result["cooldown"])
        self.assertFalse(result["permanent"])

    def test_500_is_transient(self):
        client, resp = self._make_client(500, '{"error":"server error"}')
        with patch("app.services.sub2api.cr.post", return_value=resp):
            result = client.test_account(1)
        self.assertTrue(result["transient"])
        self.assertFalse(result["permanent"])

    def test_success_is_ok(self):
        client, resp = self._make_client(200, '{"choices":[{"message":{"content":"hi"}}]}')
        with patch("app.services.sub2api.cr.post", return_value=resp):
            result = client.test_account(1)
        self.assertTrue(result["ok"])


class TestRetestQueue(unittest.TestCase):
    """测试延迟复测队列。"""

    def setUp(self):
        self._orig = RETEST_QUEUE_FILE
        import app.services.pool as pool_mod
        self._tmp = pool_mod.RETEST_QUEUE_FILE
        pool_mod.RETEST_QUEUE_FILE = self._tmp.with_name("_test_retest_queue.jsonl")
        if pool_mod.RETEST_QUEUE_FILE.exists():
            pool_mod.RETEST_QUEUE_FILE.unlink()

    def tearDown(self):
        import app.services.pool as pool_mod
        if pool_mod.RETEST_QUEUE_FILE.exists():
            pool_mod.RETEST_QUEUE_FILE.unlink()
        pool_mod.RETEST_QUEUE_FILE = self._orig

    def test_append_and_read(self):
        _retest_queue_append(1, "a@b.c", "quota")
        _retest_queue_append(2, "d@e.f", "timeout")
        entries = _retest_queue_read()
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0]["id"], 1)

    def test_write_and_read(self):
        _retest_queue_write([{"id": 3, "email": "x@y.z", "reason": "", "isolated_at": 100}])
        entries = _retest_queue_read()
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["id"], 3)


if __name__ == "__main__":
    unittest.main()