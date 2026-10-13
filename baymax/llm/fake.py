"""A scriptable fake model for tests and for trying the UI without an API key."""
import json


class FakeLLM:
    def __init__(self, replies=None, signal="neutral", mode="listen", memory_fact=""):
        self.replies = list(replies or [])
        self.signal, self.mode, self.memory_fact = signal, mode, memory_fact
        self.calls = []            # (system, history, user_msg) for assertions

    def generate(self, system, history, user_msg, schema):
        self.calls.append((system, list(history), user_msg))
        reply = self.replies.pop(0) if self.replies else f"I hear you. You said: {user_msg}"
        if isinstance(reply, Exception):
            raise reply
        return json.dumps({"reply": reply, "signal": self.signal, "interaction_mode": self.mode,
                           "memory": {"save": bool(self.memory_fact), "fact": self.memory_fact}})
