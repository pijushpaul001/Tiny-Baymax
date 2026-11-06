import json
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from baymax import __version__
from baymax.llm.fake import FakeLLM
from baymax.config import Settings
from server.app import make_server


class WebIntegrationTests(unittest.TestCase):
    def start_server(self, user_controls=False):
        tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(tempdir.cleanup)
        cfg = Settings(
            data_dir=Path(tempdir.name) / "data",
            llm="fake",
            tokens={"good-token": "u1"},
            host="127.0.0.1",
            port=0,
            user_controls=user_controls,
        )
        server = make_server(cfg, llm=FakeLLM())
        self.addCleanup(server.baymax_api.store.close)
        self.addCleanup(server.server_close)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(thread.join, 3)
        self.addCleanup(server.shutdown)
        return server, f"http://127.0.0.1:{server.server_address[1]}"

    def setUp(self):
        self.server, self.base = self.start_server(user_controls=False)

    def request(self, path, method="GET", payload=None, token=None, base=None):
        body = None if payload is None else json.dumps(payload).encode()
        headers = {}
        if token:
            headers["X-Baymax-Token"] = token
        if body is not None:
            headers["Content-Type"] = "application/json"
        req = Request((base or self.base) + path, data=body, headers=headers, method=method)
        try:
            with urlopen(req, timeout=3) as response:
                return response.status, response.headers.get("Content-Type", ""), response.read()
        except HTTPError as exc:
            return exc.code, exc.headers.get("Content-Type", ""), exc.read()

    def test_web_assets_are_served_with_expected_types(self):
        for path, expected in (("/", "text/html"), ("/app.js", "javascript"),
                               ("/face.js", "javascript"), ("/speech.js", "javascript"), ("/styles.css", "text/css"), ("/manifest.webmanifest", "application/manifest+json")):
            with self.subTest(path=path):
                status, ctype, body = self.request(path)
                self.assertEqual(status, 200)
                self.assertIn(expected, ctype)
                self.assertTrue(body)


    def test_face_is_in_chat_and_updates_from_live_emotion_only(self):
        _, _, html_bytes = self.request("/")
        _, _, app_bytes = self.request("/app.js")
        html = html_bytes.decode()
        script = app_bytes.decode()
        self.assertIn('id="baymax-face"', html)
        self.assertIn('src="/face.js"', html)
        self.assertIn("session.emotion", script)
        self.assertIn('hasOwnProperty.call(result, "emotion")', script)
        self.assertIn("result.emotion", script)


    def test_voice_controls_only_speak_live_replies_and_cancel_on_send(self):
        _, _, html_bytes = self.request("/")
        _, _, script_bytes = self.request("/app.js")
        html = html_bytes.decode()
        script = script_bytes.decode()
        self.assertIn('id="voice-toggle"', html)
        self.assertIn('src="/speech.js"', html)
        self.assertIn("speechSynthesis", script)
        self.assertIn("utterance.rate = 0.85", script)
        self.assertIn("utterance.pitch = 0.9", script)
        history_start = script.index("function renderHistory")
        history_end = script.index("function clearTools", history_start)
        self.assertNotIn("speakReply", script[history_start:history_end])


    def test_optional_microphone_fills_composer_without_sending(self):
        _, _, html_bytes = self.request("/")
        _, _, script_bytes = self.request("/app.js")
        html = html_bytes.decode()
        script = script_bytes.decode()
        self.assertIn('id="mic-button"', html)
        self.assertIn('id="speech-error"', html)
        self.assertIn("window.SpeechRecognition || window.webkitSpeechRecognition", script)
        self.assertIn("recognition.lang = navigator.language || \"en-US\"", script)
        self.assertIn('byId("message-input").value = transcript', script)
        self.assertIn("Microphone permission was denied.", script)
        self.assertNotIn("sendMessage(transcript)", script)
        self.assertIn("cancelSpeech();", script)

    def test_index_has_no_inline_scripts_or_style_attributes(self):
        _, _, html_bytes = self.request("/")
        html = html_bytes.decode()
        self.assertNotRegex(html, r"(?i)\sstyle\s*=")
        self.assertNotRegex(html, r"(?is)<script(?![^>]*\bsrc=)[^>]*>")


    def test_service_worker_caches_face_and_speech_assets(self):
        _, _, sw_bytes = self.request("/sw.js")
        sw = sw_bytes.decode()
        self.assertIn('tiny-baymax-static-v2', sw)
        self.assertIn('"/face.js"', sw)
        self.assertIn('"/speech.js"', sw)

    def test_default_closed_friends_web_has_no_user_controls_or_consent_ui(self):
        _, _, html_bytes = self.request("/")
        _, _, script_bytes = self.request("/app.js")
        html = html_bytes.decode()
        script = script_bytes.decode()
        for forbidden in ("Care &amp; privacy", "settings-panel", "show-memories", "show-ratings",
                           "export-data", "reset-emotion", "delete-all", "clear-history",
                           "consent-dialog", "review-consent", "consent-form"):
            self.assertNotIn(forbidden, html)
        for forbidden in ("CONSENT_KEY", "consented_version", "consentDialog"):
            self.assertNotIn(forbidden, script)
        self.assertIn('"tiny-baymax-speak"', script)
        self.assertNotIn('localStorage.setItem("token"', script)
        self.assertNotIn('localStorage.setItem("passcode"', script)
        self.assertNotIn('localStorage.setItem("X-Baymax-Token"', script)
        self.assertIn('id="offline-card"', html)
        self.assertIn("In an emergency, contact your local emergency number.", html)
        self.assertIn("Baymax is an AI companion, not a doctor or emergency service.", html)

    def test_default_server_locks_management_routes_and_commands(self):
        for method, path, payload in (
            ("GET", "/api/state", None), ("GET", "/api/memories", None),
            ("GET", "/api/ratings", None), ("POST", "/api/settings", {"auto_memory": False}),
            ("POST", "/api/clear", {}), ("POST", "/api/emotion/reset", {}),
            ("GET", "/api/export", None), ("DELETE", "/api/data", {"confirm": "DELETE"}),
        ):
            status, _, body = self.request(path, method=method, payload=payload, token="good-token")
            self.assertEqual(status, 403)
            self.assertEqual(json.loads(body)["code"], "not_available")
        status, _, body = self.request("/api/chat", method="POST", payload={"message": "/help"}, token="good-token")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["reply"], "That command is not available.")

    def test_chat_rating_and_shutdown_work_with_default_controls_locked(self):
        status, _, session_bytes = self.request("/api/session", token="good-token")
        session = json.loads(session_bytes)
        self.assertEqual(status, 200)
        self.assertTrue(any("personal healthcare companion" in item["content"].lower()
                            for item in session["history"] if item["role"] == "assistant"))
        status, _, chat_bytes = self.request("/api/chat", method="POST",
                                              payload={"message": "My head hurts"}, token="good-token")
        chat = json.loads(chat_bytes)
        self.assertEqual(status, 200)
        self.assertIn("from 0 to 10", chat["reply"])
        self.assertTrue(chat["ui"]["rating"]["skippable"])
        status, _, rating_bytes = self.request("/api/chat", method="POST",
                                                payload={"message": "8"}, token="good-token")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(rating_bytes)["kind"], "chat")
        status, _, end_bytes = self.request("/api/session/end", method="POST", payload={}, token="good-token")
        end = json.loads(end_bytes)
        self.assertEqual(status, 200)
        self.assertEqual(end["reply"], "Are you satisfied with my care today?")
        status, _, close_bytes = self.request("/api/chat", method="POST",
                                              payload={"message": "yes"}, token="good-token")
        self.assertTrue(json.loads(close_bytes)["ended"])

    def test_legacy_user_controls_flag_preserves_old_management_behaviour(self):
        server, base = self.start_server(user_controls=True)
        def req(path, method="GET", payload=None):
            return self.request(path, method, payload, token="good-token", base=base)
        status, _, settings = req("/api/settings", "POST", {"consented_version": "1"})
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(settings)["settings"]["consented_version"], "1")
        status, _, chat = req("/api/chat", "POST", {"message": "My head hurts"})
        self.assertEqual(status, 200)
        status, _, rating = req("/api/chat", "POST", {"message": "8"})
        self.assertEqual(status, 200)
        status, _, ratings = req("/api/ratings")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(ratings)["ratings"][-1]["rating"], 8)

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


if __name__ == "__main__":
    unittest.main()
