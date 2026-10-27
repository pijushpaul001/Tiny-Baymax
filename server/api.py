"""Framework-free JSON API. `dispatch` maps (method, path, headers, body) -> (status, dict).

Kept separate from the HTTP server so it can be tested without sockets, and so the
server can later be swapped for FastAPI/Flask without touching any logic.
"""
import json
import re

from baymax import __version__

MAX_BODY = 16 * 1024
KNOWN_COMMANDS = {
    "/help", "/state", "/memories", "/remember", "/forget", "/clear",
    "/emotion-reset", "/memory-on", "/memory-off", "/ratings", "/debug",
}


class Api:
    def __init__(self, service, auth, allowed_origins=(), trusted_proxy=False, user_controls=True):
        self.service, self.store, self.auth = service, service.store, auth
        self.allowed_origins = frozenset(str(x).rstrip("/") for x in allowed_origins if str(x).strip())
        self.trusted_proxy = bool(trusted_proxy)
        self.user_controls = bool(user_controls)

    def cors_headers(self, origin: str = "") -> dict:
        origin = (origin or "").rstrip("/")
        if not origin or origin not in self.allowed_origins:
            return {}
        return {
            "Access-Control-Allow-Origin": origin,
            "Vary": "Origin",
            "Access-Control-Allow-Methods": "GET, POST, PATCH, DELETE, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, X-Baymax-Token, X-Baymax-TZ",
            "Access-Control-Max-Age": "600",
        }

    def dispatch(self, method: str, path: str, headers, body: bytes, client_id: str = "unknown"):
        path = path.split("?", 1)[0].rstrip("/") or "/"
        if path == "/api/health":
            health = self.store.health()
            return (200 if health["ok"] else 503), {
                "ok": health["ok"], "version": __version__, "storage": "ok" if health["ok"] else "unavailable"
            }
        uid = self.auth.user_for(headers, client_id=client_id)
        if uid is None:
            if self.auth.is_locked(client_id):
                return 429, {"error": "Too many failed passcode attempts. Try again later.", "code": "too_many_attempts"}
            return 401, {"error": "Passcode needed.", "code": "authentication_required"}
        if len(body or b"") > MAX_BODY:
            return 413, {"error": "Request too large.", "code": "request_too_large"}
        if not self.user_controls and (
            path == "/api/state"
            or path == "/api/memories"
            or path.startswith("/api/memories/")
            or path == "/api/ratings"
            or path.startswith("/api/ratings/")
            or path == "/api/settings"
            or path == "/api/clear"
            or path == "/api/emotion/reset"
            or path == "/api/export"
            or path == "/api/data"
        ):
            return 403, {"error": "That feature is not available.", "code": "not_available"}
        data = {}
        if method in ("POST", "PATCH", "DELETE") and body:
            try:
                data = json.loads(body.decode("utf-8"))
                if not isinstance(data, dict):
                    raise ValueError
            except (ValueError, UnicodeDecodeError):
                return 400, {"error": "Body must be a JSON object.", "code": "invalid_json_body"}

        svc, st = self.service, self.store
        if (method, path) == ("GET", "/api/session"):
            return 200, svc.open_session(uid)
        if (method, path) == ("POST", "/api/session/end"):
            return 200, svc.end_session(uid)
        if (method, path) == ("POST", "/api/chat"):
            msg = data.get("message")
            if not isinstance(msg, str):
                return 400, {"error": "'message' must be text.", "code": "invalid_message"}
            if not self.user_controls and msg.strip().startswith("/"):
                command_name = msg.strip().split(None, 1)[0].lower()
                if command_name in KNOWN_COMMANDS:
                    return 200, {"reply": "That command is not available."}
            return 200, svc.handle(uid, msg)
        if (method, path) == ("GET", "/api/state"):
            from baymax.emotion import EmotionState
            e = EmotionState.from_dict(st.get_emotion(uid))
            return 200, {"emotion": e.to_dict(), "dominant": e.dominant(), "tone": e.style()["tone"],
                         "settings": st.get_settings(uid)}
        if path == "/api/memories":
            if method == "GET":
                return 200, {"memories": st.memories(uid)}
            if method == "POST":
                fact = data.get("fact", "")
                if not isinstance(fact, str):
                    return 400, {"error": "'fact' must be text.", "code": "invalid_fact"}
                reply = svc.remember(uid, fact)
                return 200, {"reply": reply["reply"], "memories": st.memories(uid)}
            if method == "DELETE":
                st.clear_memories(uid)
                return 200, {"memories": []}
        m = re.fullmatch(r"/api/memories/(\d+)", path)
        if m and method == "DELETE":
            ok = st.delete_memory(uid, int(m.group(1)))
            return (200, {"memories": st.memories(uid)}) if ok else (404, {"error": "Not found.", "code": "not_found"})
        if (method, path) == ("GET", "/api/ratings"):
            return 200, {"ratings": st.ratings(uid, 50)}
        m = re.fullmatch(r"/api/ratings/(\d+)", path)
        if m and method == "DELETE":
            ok = st.delete_rating(uid, int(m.group(1)))
            return (200, {"ratings": st.ratings(uid, 50)}) if ok else (404, {"error": "Not found.", "code": "not_found"})
        if m and method == "PATCH":
            rating = data.get("rating")
            if isinstance(rating, bool) or not isinstance(rating, int) or not 0 <= rating <= 10:
                return 400, {"error": "'rating' must be an integer from 0 to 10.", "code": "invalid_rating"}
            ok = st.update_rating(uid, int(m.group(1)), rating)
            return (200, {"ratings": st.ratings(uid, 50)}) if ok else (404, {"error": "Not found.", "code": "not_found"})
        if (method, path) == ("POST", "/api/settings"):
            return 200, {"settings": st.save_settings(uid, data)}
        if (method, path) == ("POST", "/api/clear"):
            return 200, svc.clear_history(uid)
        if (method, path) == ("POST", "/api/emotion/reset"):
            return 200, svc.reset_emotion(uid)
        if (method, path) == ("GET", "/api/export"):
            return 200, st.export(uid)
        if (method, path) == ("DELETE", "/api/data"):
            if data.get("confirm") != "DELETE":
                return 400, {"error": 'Send {"confirm": "DELETE"} to delete everything.', "code": "confirmation_required"}
            return 200, svc.forget_user(uid)
        return 404, {"error": "Not found.", "code": "not_found"}
