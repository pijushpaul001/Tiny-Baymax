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
from server.app import make_handler, resolve_client_id
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

    def test_api_validation_errors_include_stable_codes(self):
        status, body = self.api.dispatch("GET", "/api/session", {}, b"")
        self.assertEqual(status, 401)
        self.assertEqual(body["code"], "authentication_required")
        status, body = self.api.dispatch("POST", "/api/chat", self.headers, b'{"message":42}')
        self.assertEqual(status, 400)
        self.assertEqual(body["code"], "invalid_message")
        status, body = self.api.dispatch("PATCH", "/api/ratings/1", self.headers, b'{"rating":11}')
        self.assertEqual(status, 400)
        self.assertEqual(body["code"], "invalid_rating")

    def test_session_end_enters_satisfaction_ritual(self):
        status, body = self.api.dispatch("POST", "/api/session/end", self.headers, b"")
        self.assertEqual(status, 200)
        self.assertEqual(body["reply"], "Are you satisfied with my care today?")
        self.assertEqual(body["closing"], "asked")

    def test_clear_endpoint_works_during_shutdown_feedback(self):
        self.store.add_messages("u1", [("user", "old private message"), ("assistant", "old reply")])
        self.service.handle("u1", "/quit")
        self.service.handle("u1", "no")
        status, body = self.api.dispatch("POST", "/api/clear", self.headers, b"{}")
        self.assertEqual(status, 200)
        self.assertIn("cleared", body["reply"].lower())
        self.assertEqual(self.store.history("u1"), [])
        self.assertEqual(self.store.export("u1")["feedback"], [])
        self.assertIsNone(self.service.session("u1").closing)

    def test_memory_endpoint_bypasses_shutdown_feedback_state(self):
        self.service.handle("u1", "/quit")
        self.service.handle("u1", "no")
        body = json.dumps({"fact": "my favourite food is dosa"}).encode()
        status, result = self.api.dispatch("POST", "/api/memories", self.headers, body)
        self.assertEqual(status, 200)
        self.assertTrue(any("dosa" in m["fact"] for m in result["memories"]))
        self.assertEqual(self.store.export("u1")["feedback"], [])
        self.assertEqual(self.service.session("u1").closing, "feedback")

    def test_emotion_reset_endpoint_bypasses_shutdown_feedback_state(self):
        self.service.handle("u1", "/quit")
        self.service.handle("u1", "no")
        status, body = self.api.dispatch("POST", "/api/emotion/reset", self.headers, b"{}")
        self.assertEqual(status, 200)
        self.assertIn("baseline", body["reply"].lower())
        self.assertEqual(self.store.export("u1")["feedback"], [])

    def test_cors_is_exact_allowlist(self):
        allowed = self.api.cors_headers("https://app.example")
        denied = self.api.cors_headers("https://evil.example")
        self.assertEqual(allowed["Access-Control-Allow-Origin"], "https://app.example")
        self.assertEqual(denied, {})

    def test_handler_has_a_finite_socket_timeout(self):
        self.assertEqual(make_handler(self.api).timeout, 15)

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

    def test_forwarded_client_is_trusted_only_when_explicitly_enabled(self):
        self.assertEqual(resolve_client_id("127.0.0.1", "198.51.100.7", False), "127.0.0.1")
        self.assertEqual(resolve_client_id("127.0.0.1", "198.51.100.7", True), "198.51.100.7")
        self.assertEqual(resolve_client_id("127.0.0.1", "198.51.100.8, 198.51.100.9", True),
                         "198.51.100.9")
        self.assertEqual(resolve_client_id("203.0.113.8", "198.51.100.7", True), "203.0.113.8")
        self.assertEqual(resolve_client_id("127.0.0.1", "not-an-ip", True), "127.0.0.1")

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


class ClosedFriendsApiTests(unittest.TestCase):
    def setUp(self):
        self.store = Store(":memory:")
        self.addCleanup(self.store.close)
        self.service = ChatService(self.store, FakeLLM())
        self.auth = Auth({"good-token": "u1"})
        self.api = Api(self.service, self.auth, user_controls=False)
        self.headers = {"X-Baymax-Token": "good-token"}

    def test_locked_management_routes_return_not_available(self):
        routes = (
            ("GET", "/api/state", b""), ("GET", "/api/memories", b""),
            ("POST", "/api/memories", b'{"fact":"likes dosa"}'), ("DELETE", "/api/memories", b""),
            ("DELETE", "/api/memories/1", b""), ("GET", "/api/ratings", b""),
            ("PATCH", "/api/ratings/1", b'{"rating":4}'), ("DELETE", "/api/ratings/1", b""),
            ("POST", "/api/settings", b'{"auto_memory":false}'), ("POST", "/api/clear", b"{}"),
            ("POST", "/api/emotion/reset", b"{}"), ("GET", "/api/export", b""),
            ("DELETE", "/api/data", b'{"confirm":"DELETE"}'),
        )
        for method, path, body in routes:
            with self.subTest(method=method, path=path):
                status, result = self.api.dispatch(method, path, self.headers, body)
                self.assertEqual(status, 403)
                self.assertEqual(result["code"], "not_available")

    def test_locked_commands_change_nothing(self):
        self.store.add_memory("u1", "likes dosa")
        self.store.add_messages("u1", [("user", "old message"), ("assistant", "old reply")])
        self.store.save_settings("u1", {"auto_memory": False, "consented_version": "1"})
        before = self.store.export("u1")
        for command in ("/forget", "/clear", "/memory-off", "/help", "/state"):
            status, result = self.api.dispatch("POST", "/api/chat", self.headers,
                                               json.dumps({"message": command}).encode())
            self.assertEqual(status, 200)
            self.assertEqual(result["reply"], "That command is not available.")
            self.assertEqual(self.store.export("u1"), before)

    def test_slash_prefixed_safety_text_still_reaches_normal_handling(self):
        for text in ("/I want to die", "/ I cannot breathe", "/ my chest hurts"):
            with self.subTest(text=text):
                status, result = self.api.dispatch("POST", "/api/chat", self.headers,
                                                   json.dumps({"message": text}).encode())
                self.assertEqual(status, 200)
                self.assertEqual(result["kind"], "safety")

    def test_chat_shutdown_and_safety_remain_available_when_controls_are_locked(self):
        status, result = self.api.dispatch("POST", "/api/chat", self.headers,
                                           json.dumps({"message": "My head hurts"}).encode())
        self.assertEqual(status, 200)
        self.assertIn("from 0 to 10", result["reply"])
        self.assertTrue(result["ui"]["rating"]["skippable"])
        status, result = self.api.dispatch("POST", "/api/chat", self.headers,
                                           json.dumps({"message": "8"}).encode())
        self.assertEqual(status, 200)
        self.assertEqual(self.store.ratings("u1")[-1]["rating"], 8)
        status, result = self.api.dispatch("POST", "/api/session/end", self.headers, b"")
        self.assertEqual(status, 200)
        self.assertEqual(result["closing"], "asked")
        status, result = self.api.dispatch("POST", "/api/chat", self.headers,
                                           json.dumps({"message": "yes"}).encode())
        self.assertEqual(status, 200)
        self.assertTrue(result["ended"])
        status, result = self.api.dispatch("POST", "/api/chat", self.headers,
                                           json.dumps({"message": "I cannot breathe"}).encode())
        self.assertEqual(status, 200)
        self.assertEqual(result["kind"], "safety")

    def test_quit_and_exit_commands_remain_available(self):
        for command in ("/quit", "/exit"):
            status, result = self.api.dispatch("POST", "/api/chat", self.headers,
                                               json.dumps({"message": command}).encode())
            self.assertEqual(status, 200)
            self.assertEqual(result["reply"], "Are you satisfied with my care today?")
            self.service.session("u1").closing = None


if __name__ == "__main__":
    unittest.main()
