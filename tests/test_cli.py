import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from baymax.cli import main
from baymax.config import Settings


class TraceService:
    def __init__(self, *args, **kwargs):
        self.calls = 0

    def open_session(self, uid):
        return {"history": [{"content": "Hello from Baymax."}]}

    def handle(self, uid, text):
        self.calls += 1
        if self.calls == 1:
            return {"reply": "A reply.", "ended": False, "trace": ["debug trace line"]}
        return {"reply": "Goodbye.", "ended": True}


class CliTraceTests(unittest.TestCase):
    def test_cli_prints_response_trace_after_reply(self):
        with tempfile.TemporaryDirectory() as temp:
            cfg = Settings(data_dir=Path(temp), llm="fake")
            output = io.StringIO()
            with patch("baymax.cli.Settings.from_env", return_value=cfg), \
                 patch("baymax.cli.Store"), \
                 patch("baymax.cli.ChatService", TraceService), \
                 patch("builtins.input", side_effect=["hello", "bye"]), \
                 contextlib.redirect_stdout(output):
                main()
            rendered = output.getvalue()
            reply_position = rendered.index("Baymax: A reply.")
            trace_position = rendered.index("Trace: ['debug trace line']")
            self.assertLess(reply_position, trace_position)


if __name__ == "__main__":
    unittest.main()
