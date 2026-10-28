"""Terminal chat (handy for testing without the web app):  python -m baymax.cli"""
import sys

from .config import Settings
from .decision import DecisionConfig
from .llm import FakeLLM
from .service import ChatService
from .storage import Store


def main():
    cfg = Settings.from_env()
    cfg.data_dir.mkdir(parents=True, exist_ok=True)
    if cfg.llm == "fake":
        llm = FakeLLM()
    else:
        from .llm.gemini import GeminiAdapter
        llm = GeminiAdapter(cfg.gemini_api_key, cfg.model, cfg.fallback_model or None)
    svc = ChatService(Store(cfg.db_path), llm, DecisionConfig(emergency_hint=cfg.emergency_hint),
                      cfg.max_history, cfg.max_per_day)
    uid = "cli"
    for m in svc.open_session(uid)["history"][-1:]:
        print("Baymax:", m["content"])
    while True:
        try:
            text = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not text:
            continue
        out = svc.handle(uid, text)
        print("Baymax:", out["reply"], "\n")
        if out["ended"]:
            break


if __name__ == "__main__":
    sys.exit(main())
