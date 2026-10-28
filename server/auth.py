"""Passcode auth with constant-time comparison and per-client failed-attempt lockout."""
import hmac
import threading
import time
from typing import Optional


class Auth:
    def __init__(self, tokens: dict, allow_no_auth: bool = False, *, max_failures: int = 5,
                 lockout_seconds: float = 60.0, clock=time.monotonic):
        self.tokens = dict(tokens)           # token -> user id
        self.allow_no_auth = allow_no_auth
        self.max_failures = max(1, int(max_failures))
        self.lockout_seconds = max(0.0, float(lockout_seconds))
        self.clock = clock
        self._failures = {}                  # client -> [count, blocked_until]
        self._lock = threading.Lock()

    def is_locked(self, client_id: str = "unknown") -> bool:
        now = self.clock()
        key = client_id or "unknown"
        with self._lock:
            state = self._failures.get(key)
            if not state:
                return False
            if state[1] > 0 and state[1] <= now:
                self._failures.pop(key, None)
                return False
            return state[1] > now

    def user_for(self, headers, client_id: str = "unknown") -> Optional[str]:
        if self.allow_no_auth and not self.tokens:
            return "local"
        key = client_id or "unknown"
        now = self.clock()
        with self._lock:
            state = self._failures.get(key)
            if state and state[1] > now:
                return None
            if state and state[1] > 0 and state[1] <= now:
                self._failures.pop(key, None)

        given = (headers.get("X-Baymax-Token") or "").strip()
        found = None
        for token, user in self.tokens.items():      # no early exit: same work for every attempt
            if hmac.compare_digest(given.encode(), token.encode()):
                found = user
        if found is not None:
            with self._lock:
                self._failures.pop(key, None)
            return found

        with self._lock:
            state = self._failures.get(key)
            failures = state[0] + 1 if state and state[1] == 0 else 1
            blocked_until = now + self.lockout_seconds if failures >= self.max_failures else 0.0
            self._failures[key] = [failures, blocked_until]
        return None
