import http.client
import json
import sqlite3
import tempfile
import threading
import unittest
from pathlib import Path

from baymax.llm.fake import FakeLLM
from baymax.service import ChatService
from baymax.storage import Store
from server.api import Api
from server.auth import Auth
from server.app import make_handler
from http.server import ThreadingHTTPServer


class FakeClock:
    def __init__(self):
        self.value = 100.0
    def __call__(self):
        return self.value
    def advance(self, seconds):
        self.value += seconds


class ApiAuthTests(unittest.TestCase):
    def setUp(self):
        self.store = Store(":memory:")
        self.addCleanup(self.store.close)
        self.service = ChatService(self.store, FakeLLM())
        self.auth = Auth({"good-token": "u1"})
        self.api = Api(self.service, self.auth, allowed_origins=("https://app.example",))
        self.headers = {"X-Baymax-Token": "good-token"}

    def test_health_is_public_and_includes_storage(self):
        status, body = self.api.dispatch("GET", "/api/health", {}, b"")
        self.assertEqual(status, 200)
        self.assertEqual(body["storage"], "ok")
        self.assertIn("version", body)

    def test_wrong_passcode_is_rate_limited_after_threshold(self):
        clock = FakeClock()
        auth = Auth({"good": "user"}, max_failures=2, lockout_seconds=10, clock=clock)
        api = Api(self.service, auth)
        self.assertEqual(api.dispatch("GET", "/api/session", {}, b"", client_id="192.0.2.2")[0], 401)
        status, body = api.dispatch("GET", "/api/session", {}, b"", client_id="192.0.2.2")
        self.assertEqual(status, 429)
        self.assertEqual(body["code"], "too_many_attempts")

    def test_rating_patch_and_delete_are_scoped(self):
        rid = self.store.add_rating("u1", "physical", "pain", 7)
        status, body = self.api.dispatch("PATCH", f"/api/ratings/{rid}", self.headers,
                                         json.dumps({"rating": 4}).encode())
        self.assertEqual(status, 200)
        self.assertEqual(body["ratings"][0]["rating"], 4)
        status, _ = self.api.dispatch("DELETE", f"/api/ratings/{rid}", self.headers, b"")
        self.assertEqual(status, 200)
        self.assertEqual(self.store.ratings("u1"), [])

    def test_bad_rating_patch_is_rejected(self):
        rid = self.store.add_rating("u1", "physical", "pain", 7)
        status, _ = self.api.dispatch("PATCH", f"/api/ratings/{rid}", self.headers,
                                      json.dumps({"rating": 11}).encode())
        self.assertEqual(status, 400)

    def test_session_end_enters_satisfaction_ritual(self):
        status, body = self.api.dispatch("POST", "/api/session/end", self.headers, b"")
        self.assertEqual(status, 200)
        self.assertEqual(body["reply"], "Are you satisfied with my care today?")
        self.assertEqual(body["closing"], "asked")

    def test_cors_is_exact_allowlist(self):
        allowed = self.api.cors_headers("https://app.example")
        denied = self.api.cors_headers("https://evil.example")
        self.assertEqual(allowed["Access-Control-Allow-Origin"], "https://app.example")
        self.assertEqual(denied, {})


    def test_handler_returns_400_for_invalid_content_length(self):
        with tempfile.TemporaryDirectory() as td:
            api = Api(self.service, self.auth, allowed_origins=("https://app.example",))
            server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(api))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                conn = http.client.HTTPConnection("127.0.0.1", server.server_address[1], timeout=3)
                conn.putrequest("GET", "/api/health")
                conn.putheader("Content-Length", "invalid")
                conn.endheaders()
                response = conn.getresponse()
                payload = json.loads(response.read().decode())
                self.assertEqual(response.status, 400)
                self.assertEqual(payload["code"], "invalid_content_length")
                conn.close()
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)

    def test_http_options_adds_cors_only_for_allowed_origins(self):
        api = Api(self.service, self.auth, allowed_origins=("https://app.example",))
        server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(api))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            conn = http.client.HTTPConnection("127.0.0.1", server.server_address[1], timeout=3)
            conn.request("OPTIONS", "/api/chat", headers={
                "Origin": "https://app.example", "Access-Control-Request-Method": "POST"
            })
            response = conn.getresponse()
            response.read()
            self.assertEqual(response.status, 204)
            self.assertEqual(response.getheader("Access-Control-Allow-Origin"), "https://app.example")
            conn.close()

            conn = http.client.HTTPConnection("127.0.0.1", server.server_address[1], timeout=3)
            conn.request("OPTIONS", "/api/chat", headers={"Origin": "https://evil.example"})
            response = conn.getresponse()
            response.read()
            self.assertEqual(response.status, 204)
            self.assertIsNone(response.getheader("Access-Control-Allow-Origin"))
            conn.close()
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    def test_handler_converts_sqlite_and_unexpected_errors_to_json(self):
        for exception, expected_status, expected_code in (
            (sqlite3.OperationalError("db unavailable"), 503, "storage_unavailable"),
            (RuntimeError("unexpected"), 500, "server_error"),
        ):
            with self.subTest(code=expected_code):
                api = Api(self.service, self.auth)
                def explode(*args, **kwargs):
                    raise exception
                api.dispatch = explode
                server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(api))
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()
                try:
                    conn = http.client.HTTPConnection("127.0.0.1", server.server_address[1], timeout=3)
                    conn.request("GET", "/api/anything", headers=self.headers)
                    response = conn.getresponse()
                    payload = json.loads(response.read().decode())
                    self.assertEqual(response.status, expected_status)
                    self.assertEqual(payload["code"], expected_code)
                    conn.close()
                finally:
                    server.shutdown()
                    server.server_close()
                    thread.join(timeout=2)

    def test_auth_lockout_is_per_client_and_expires(self):
        clock = FakeClock()
        auth = Auth({"good": "user"}, max_failures=3, lockout_seconds=10, clock=clock)
        self.assertIsNone(auth.user_for({}, "ip-a"))
        self.assertIsNone(auth.user_for({}, "ip-a"))
        self.assertIsNone(auth.user_for({}, "ip-a"))
        self.assertTrue(auth.is_locked("ip-a"))
        self.assertEqual(auth.user_for({"X-Baymax-Token": "good"}, "ip-a"), None)
        self.assertEqual(auth.user_for({"X-Baymax-Token": "good"}, "ip-b"), "user")
        clock.advance(11)
        self.assertEqual(auth.user_for({"X-Baymax-Token": "good"}, "ip-a"), "user")


if __name__ == "__main__":
    unittest.main()
