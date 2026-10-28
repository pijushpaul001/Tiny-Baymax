"""Tiny dependency-free HTTP server: JSON API + the static web app."""
import ipaddress
import json
import mimetypes
import sqlite3
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from baymax.config import Settings
from baymax.decision import DecisionConfig
from baymax.llm import FakeLLM
from baymax.service import ChatService
from baymax.storage import Store

from .api import MAX_BODY, Api
from .auth import Auth

WEB_DIR = Path(__file__).resolve().parent.parent / "web"
STATIC_OK = {".html", ".css", ".js", ".webmanifest", ".svg", ".png", ".ico", ".json"}
SECURITY_HEADERS = {
    "Content-Security-Policy": "default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; "
                               "connect-src 'self'; base-uri 'none'; frame-ancestors 'none'",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "X-Frame-Options": "DENY",
}


def build_llm(cfg: Settings):
    if cfg.llm == "fake":
        return FakeLLM()
    from baymax.llm.gemini import GeminiAdapter
    return GeminiAdapter(cfg.gemini_api_key, cfg.model, cfg.fallback_model or None)


def resolve_client_id(peer_ip: str, forwarded_for: str = "", trusted_proxy: bool = False) -> str:
    """Use X-Forwarded-For only when explicitly enabled and the peer is loopback."""
    peer = (peer_ip or "unknown").strip()
    if not trusted_proxy:
        return peer
    try:
        if not ipaddress.ip_address(peer).is_loopback:
            return peer
    except ValueError:
        return peer
    forwarded = (forwarded_for or "").split(",")[-1].strip()
    if not forwarded:
        return peer
    try:
        return str(ipaddress.ip_address(forwarded))
    except ValueError:
        return peer


def build_api(cfg: Settings, llm=None) -> Api:
    cfg.data_dir.mkdir(parents=True, exist_ok=True)
    service = ChatService(Store(cfg.db_path, backup_keep=cfg.backup_keep), llm or build_llm(cfg),
                          DecisionConfig(emergency_hint=cfg.emergency_hint),
                          max_history=cfg.max_history, max_per_day=cfg.max_per_day)
    return Api(service, Auth(cfg.tokens, cfg.allow_no_auth),
               allowed_origins=cfg.allowed_origins, trusted_proxy=cfg.trusted_proxy,
               user_controls=cfg.user_controls)


def make_handler(api: Api):
    class Handler(BaseHTTPRequestHandler):
        server_version = "TinyBaymax"
        sys_version = ""
        timeout = 15

        def log_message(self, fmt, *args):
            pass

        def _send(self, status, payload: bytes, ctype: str, extra=None):
            try:
                self.send_response(status)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(payload)))
                for k, v in {**SECURITY_HEADERS, **(extra or {})}.items():
                    self.send_header(k, v)
                self.end_headers()
                self.wfile.write(payload)
            except (BrokenPipeError, ConnectionResetError):
                return

        def _json(self, status, obj, extra=None):
            headers = {"Cache-Control": "no-store", **api.cors_headers(self.headers.get("Origin", "")), **(extra or {})}
            self._send(status, json.dumps(obj).encode(), "application/json", headers)

        def _api(self, method):
            try:
                raw_length = self.headers.get("Content-Length")
                length = int(raw_length or 0)
                if length < 0:
                    return self._json(400, {"error": "Invalid Content-Length.", "code": "invalid_content_length"})
            except (ValueError, OverflowError):
                return self._json(400, {"error": "Invalid Content-Length.", "code": "invalid_content_length"})
            if length > MAX_BODY:
                return self._json(413, {"error": "Request too large.", "code": "request_too_large"})
            body = self.rfile.read(length) if length else b""
            try:
                peer_ip = self.client_address[0] if self.client_address else "unknown"
                client_id = resolve_client_id(
                    peer_ip, self.headers.get("X-Forwarded-For", ""), api.trusted_proxy
                )
                status, obj = api.dispatch(method, self.path, self.headers, body, client_id=client_id)
            except sqlite3.Error:
                return self._json(503, {"error": "Storage is temporarily unavailable.", "code": "storage_unavailable"})
            except Exception as exc:
                print(f"[error] API request failed: {type(exc).__name__}")
                return self._json(500, {"error": "An unexpected server error occurred.", "code": "server_error"})
            self._json(status, obj)

        def do_OPTIONS(self):
            if not self.path.startswith("/api/"):
                return self._json(404, {"error": "Not found.", "code": "not_found"})
            headers = api.cors_headers(self.headers.get("Origin", ""))
            self._send(204, b"", "text/plain", headers)

        def _static(self):
            rel = self.path.split("?", 1)[0].lstrip("/") or "index.html"
            target = (WEB_DIR / rel).resolve()
            if WEB_DIR not in target.parents or not target.is_file() or target.suffix not in STATIC_OK:
                return self._json(404, {"error": "Not found.", "code": "not_found"})
            ctype = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
            if target.suffix == ".webmanifest":
                ctype = "application/manifest+json"
            cache = "no-cache" if target.name in ("sw.js", "index.html") else "max-age=3600"
            self._send(200, target.read_bytes(), ctype, {"Cache-Control": cache})

        def do_GET(self):
            self._api("GET") if self.path.startswith("/api/") else self._static()

        def do_POST(self):
            self._api("POST") if self.path.startswith("/api/") else self._json(404, {"error": "Not found.", "code": "not_found"})

        def do_DELETE(self):
            self._api("DELETE") if self.path.startswith("/api/") else self._json(404, {"error": "Not found.", "code": "not_found"})

        def do_PATCH(self):
            self._api("PATCH") if self.path.startswith("/api/") else self._json(404, {"error": "Not found.", "code": "not_found"})

    return Handler


def make_server(cfg: Settings, llm=None) -> ThreadingHTTPServer:
    api = build_api(cfg, llm)
    server = ThreadingHTTPServer((cfg.host, cfg.port), make_handler(api))
    server.baymax_api = api
    return server


def main():
    cfg = Settings.from_env()
    if not cfg.tokens and not cfg.allow_no_auth:
        sys.exit("Set BAYMAX_TOKENS (e.g. BAYMAX_TOKENS=me=choose-a-long-random-passcode) in .env, "
                 "or BAYMAX_ALLOW_NO_AUTH=1 for local testing only.")
    if cfg.llm == "gemini" and not cfg.gemini_api_key:
        sys.exit("Set GEMINI_API_KEY in .env, or BAYMAX_LLM=fake to try the app without Gemini.")
    try:
        server = make_server(cfg)
    except (OSError, sqlite3.Error, RuntimeError) as exc:
        sys.exit(f"Baymax could not start safely: {type(exc).__name__}: {exc}")
    print(f"Tiny Baymax is running at http://{cfg.host}:{cfg.port}  (model: {cfg.llm}). Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nBaymax stopped.")
    finally:
        server.server_close()
        try:
            server.baymax_api.store.close()
        except Exception:
            pass


if __name__ == "__main__":
    main()
