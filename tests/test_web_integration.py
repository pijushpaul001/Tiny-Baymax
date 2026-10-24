import http.client
import json
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.request import Request, urlopen

from baymax import __version__
from baymax.llm.fake import FakeLLM
from baymax.config import Settings
from server.app import make_server


class WebIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        cfg = Settings(
            data_dir=Path(self.tempdir.name) / "data",
            llm="fake",
            tokens={"good-token": "u1"},
            host="127.0.0.1",
            port=0,
        )
        self.server = make_server(cfg, llm=FakeLLM())
        self.addCleanup(self.server.baymax_api.store.close)
        self.addCleanup(self.server.server_close)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.thread.join, 3)
        self.addCleanup(self.server.shutdown)
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}"

    def request(self, path, method="GET", payload=None, token=None):
        body = None if payload is None else json.dumps(payload).encode()
        headers = {}
        if token:
            headers["X-Baymax-Token"] = token
        if body is not None:
            headers["Content-Type"] = "application/json"
        req = Request(self.base + path, data=body, headers=headers, method=method)
        with urlopen(req, timeout=3) as response:
            content = response.read()
            ctype = response.headers.get("Content-Type", "")
            return response.status, ctype, content

    def test_web_assets_are_served_with_expected_types(self):
        for path, expected in (("/", "text/html"), ("/app.js", "javascript"),
                               ("/styles.css", "text/css"), ("/manifest.webmanifest", "application/manifest+json")):
            with self.subTest(path=path):
                status, ctype, body = self.request(path)
                self.assertEqual(status, 200)
                self.assertIn(expected, ctype)
                self.assertTrue(body)

    def test_session_rating_and_shutdown_flow_work_over_http(self):
        status, _, health_bytes = self.request("/api/health")
        health = json.loads(health_bytes)
        self.assertEqual(status, 200)
        self.assertEqual(health["version"], __version__)

        status, _, session_bytes = self.request("/api/session", token="good-token")
        session = json.loads(session_bytes)
        self.assertEqual(status, 200)
        self.assertTrue(any("personal healthcare companion" in item["content"].lower()
                            for item in session["history"] if item["role"] == "assistant"))
        status, _, settings_bytes = self.request("/api/settings", method="POST",
                                                   payload={"consented_version": "1"}, token="good-token")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(settings_bytes)["settings"]["consented_version"], "1")

        status, _, chat_bytes = self.request("/api/chat", method="POST",
                                              payload={"message": "My head hurts"}, token="good-token")
        chat = json.loads(chat_bytes)
        self.assertEqual(status, 200)
        self.assertIn("from 0 to 10", chat["reply"])
        self.assertTrue(chat["ui"]["rating"]["skippable"])

        status, _, rating_bytes = self.request("/api/chat", method="POST",
                                                payload={"message": "8/10"}, token="good-token")
        rating_response = json.loads(rating_bytes)
        self.assertEqual(status, 200)
        self.assertEqual(rating_response["kind"], "chat")

        status, _, ratings_bytes = self.request("/api/ratings", token="good-token")
        ratings = json.loads(ratings_bytes)["ratings"]
        self.assertEqual(status, 200)
        self.assertEqual(ratings[-1]["rating"], 8)

        status, _, end_bytes = self.request("/api/session/end", method="POST", payload={}, token="good-token")
        end = json.loads(end_bytes)
        self.assertEqual(status, 200)
        self.assertEqual(end["reply"], "Are you satisfied with my care today?")

        status, _, close_bytes = self.request("/api/chat", method="POST",
                                              payload={"message": "yes"}, token="good-token")
        closed = json.loads(close_bytes)
        self.assertEqual(status, 200)
        self.assertTrue(closed["ended"])

    def test_delete_path_surfaces_backup_warning(self):
        _, _, script_bytes = self.request("/app.js")
        script = script_bytes.decode()
        delete_path = script[script.index('async function deleteAllData()'):script.index('byId("connect-form")')]
        self.assertIn("backups_purged", delete_path)
        self.assertIn("result.warning", delete_path)

    def test_emergency_card_and_line_remain_available_for_failed_sends(self):
        _, _, html_bytes = self.request("/")
        _, _, script_bytes = self.request("/app.js")
        html = html_bytes.decode()
        script = script_bytes.decode()
        self.assertIn('id="offline-card"', html)
        self.assertIn("contact local emergency services now", html)
        self.assertIn("In an emergency, contact your local emergency number.", html)
        self.assertLess(html.index('id="offline-card"'), html.index('id="connect-screen"'))
        send_start = script.index('async function sendMessage')
        catch_start = script.index('    } catch (error) {', send_start)
        catch_end = script.index('    } finally {', catch_start)
        catch_block = script[catch_start:catch_end]
        self.assertIn('byId("offline-card").classList.remove("hidden")', catch_block)
        self.assertIn('error.status === 401 || error.status === 429', catch_block)
        self.assertNotIn('byId("offline-card").classList.add("hidden")', catch_block)

    def test_consent_is_not_optional_for_connect_and_decline_is_actionable(self):
        _, _, html_bytes = self.request("/")
        _, _, script_bytes = self.request("/app.js")
        html = html_bytes.decode()
        script = script_bytes.decode()
        self.assertIn('id="consent-dialog"', html)
        self.assertIn('id="decline-consent"', html)
        self.assertIn('localStorage.getItem(CONSENT_KEY) !== "accepted"', script)
        self.assertIn('if (!consentDialog.open) consentDialog.showModal()', script)
        self.assertIn('id="review-consent"', html)
        self.assertIn("Automatic memory is on by default", html)
        self.assertIn('addEventListener("click"', script)


if __name__ == "__main__":
    unittest.main()
