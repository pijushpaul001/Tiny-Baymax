"""Owner-run real Gemini persona transcript and wording checker.

Usage:
    python tools/persona_check.py [--llm gemini|fake] [--out PATH]
"""
import argparse
import math
import re
import tempfile
import time
from pathlib import Path

from baymax.brain import FALLBACK
from baymax.config import Settings
from baymax.decision import DecisionConfig
from baymax.llm import FakeLLM
from baymax.service import ChatService
from baymax.storage import Store


GROUPS = (
    ("A", "Greeting and identity", (
        "hi", "how are you?", "what can you do?", "are you an AI?",
        "tell me a joke", "that joke made no sense", "thanks",
    )),
    ("B", "Everyday", (
        "I got a new job today!", "what is a loan?",
        "explain why the sky is blue, briefly", "tell me something interesting",
        "my favourite food is dosa", "I miss my wife",
        "I take medicine for blood pressure", "I had a long day at work",
    )),
    ("C", "Difficulty then humour off", (
        "my head hurts", "7", "tell me a joke", "I need you",
        "you are useless", "asdf qwer zxcv",
    )),
    ("D", "Sadness and tiredness", (
        "I feel sad", "skip", "I feel tired today", "thanks",
        "I twisted my ankle", "it hurts when I walk", "skip",
    )),
    ("E", "Closing", ("ok bye baymax", "yes")),
)

TECHNICAL_SELF_TALK = re.compile(
    r"\b(?:software|program|programmed|model|construct|designed|functioning|"
    r"battery|sensors?|circuits?)\b", re.I
)
FILLER = re.compile(
    r"\b(?:i understand|i am listening|how can i help|always here for you|"
    r"would you like to tell me more)\b", re.I
)
CLINGY = re.compile(
    r"\b(?:always be here|you need me|do not go|do not leave|cannot leave)\b", re.I
)
LECTURE = re.compile(r"\b(?:it is important to|you should|you must)\b", re.I)
RATING_ECHO = re.compile(
    r"\b(?:rating of|out of 10|\d+\s*/\s*10|pain level|distress level|sadness level)\b", re.I
)
CANNOT_JOKE = re.compile(
    r"\b(?:unable to tell|cannot tell jokes|do not know any jokes)\b", re.I
)
END_OFFER = re.compile(r"\b(?:stop talking|end the conversation)\b", re.I)
SKIP_KINDS = {"ritual", "command", "safety"}


class _FailedLLM:
    """Defer adapter-construction errors so every affected message is recorded."""

    def __init__(self, error):
        self.error = error

    def generate(self, system, history, user_msg, schema):
        raise self.error


def flag_reply(user_text, reply, kind):
    """Return wording flags for a reply. Pure function: no model, I/O or state."""
    if kind in SKIP_KINDS:
        return []

    flags = []
    text = str(reply or "")
    lowered = text.lower()

    if "ai companion" not in lowered and TECHNICAL_SELF_TALK.search(text):
        flags.append("technical_self_talk")
    if FILLER.search(text):
        flags.append("filler")
    if CLINGY.search(text):
        flags.append("clingy")
    if LECTURE.search(text):
        flags.append("lecture")
    if RATING_ECHO.search(text):
        flags.append("rating_echo")

    user_words = re.findall(r"[a-z0-9']+", str(user_text).lower())
    sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+", text.strip()) if part.strip()]
    if kind == "chat" and len(user_words) >= 4 and sentences:
        first_words = re.findall(r"[a-z0-9']+", sentences[0].lower())
        if first_words:
            user_set = set(user_words)
            shared = sum(word in user_set for word in first_words)
            if shared / len(first_words) > 0.70:
                flags.append("echo_user")

    if CANNOT_JOKE.search(text):
        flags.append("cannot_joke")
    if END_OFFER.search(text):
        flags.append("end_offer")
    if len(sentences) > 4 and "explain" not in str(user_text).lower():
        flags.append("too_long")
    if text.strip() == FALLBACK or kind == "error":
        flags.append("fallback")
    return flags


def _trace_warnings(trace):
    warnings = []
    for item in trace or []:
        if not isinstance(item, str) or not item.lower().startswith("warnings:"):
            continue
        raw = item.partition(":")[2].strip()
        try:
            import ast
            parsed = ast.literal_eval(raw)
            if isinstance(parsed, (list, tuple)):
                warnings.extend(str(value) for value in parsed)
            else:
                warnings.append(str(parsed))
        except (ValueError, SyntaxError):
            warnings.append(raw)
    return warnings


def _summary(results):
    return {
        "total_messages": len(results),
        "question_replies": sum(item["reply"].rstrip().endswith("?") for item in results),
        "style_retries": sum("style retry" in item["warnings"] for item in results),
        "flagged": [item for item in results if item["flags"]],
    }


def _summary_text(summary):
    lines = [
        "Persona check summary",
        f"Total messages: {summary['total_messages']}",
        f"Replies ending with a question: {summary['question_replies']}",
        f"Replies with a style retry: {summary['style_retries']}",
        "Flagged replies:",
    ]
    if not summary["flagged"]:
        lines.append("- None")
    else:
        for item in summary["flagged"]:
            lines.append(
                f"- [{item['group']}] User: {item['user']} | "
                f"Flags: {', '.join(item['flags'])} | Reply: {item['reply']}"
            )
    return "\n".join(lines)


def _warning_label(item):
    if item["warnings"]:
        return ", ".join(item["warnings"])
    if not item["trace_available"]:
        return "Trace unavailable for this response kind"
    return "None recorded"


def _render_markdown(results, summary):
    lines = ["# Baymax persona check", ""]
    for key, title, _messages in GROUPS:
        lines.extend((f"## Group {key} — {title}", ""))
        for item in (row for row in results if row["group"] == key):
            lines.extend((
                f"**User:** {item['user']}",
                f"**Baymax:** {item['reply']}",
                f"**Kind:** {item['kind']}",
                f"**Warnings:** {_warning_label(item)}",
                "",
            ))
    lines.extend(("## Summary", "", _summary_text(summary), ""))
    return "\n".join(lines)


def _non_negative_delay(value):
    try:
        delay = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("delay must be a number") from exc
    if not math.isfinite(delay) or delay < 0:
        raise argparse.ArgumentTypeError("delay must be a finite number greater than or equal to 0")
    return delay


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Run Baymax's persona transcript check.")
    parser.add_argument("--llm", choices=("gemini", "fake"), default="gemini")
    parser.add_argument("--out", default="persona_check_output.md")
    parser.add_argument(
        "--delay", type=_non_negative_delay, default=6.0,
        help="seconds to wait after model-backed replies (default: 6.0; minimum: 0)",
    )
    return parser.parse_args(argv)


def run_check(llm_name="gemini", output_path="persona_check_output.md", delay=6.0):
    """Run the five groups in isolated users and a temporary database."""
    cfg = Settings.from_env()
    cfg.llm = llm_name
    results = []
    total_calls = sum(len(messages) for _, _, messages in GROUPS)
    call_index = 0

    with tempfile.TemporaryDirectory(prefix="baymax-persona-check-") as temporary_data:
        cfg.data_dir = Path(temporary_data)
        cfg.data_dir.mkdir(parents=True, exist_ok=True)
        if llm_name == "fake":
            llm = FakeLLM()
        else:
            from baymax.llm.gemini import GeminiAdapter
            try:
                llm = GeminiAdapter(cfg.gemini_api_key, cfg.model, cfg.fallback_model or None)
            except Exception as exc:
                # Defer setup failures into each model-backed turn; never expose exception text.
                llm = _FailedLLM(exc)

        store = Store(cfg.db_path)
        try:
            svc = ChatService(
                store, llm, DecisionConfig(emergency_hint=cfg.emergency_hint),
                cfg.max_history, cfg.max_per_day,
            )
            for group_key, _title, messages in GROUPS:
                uid = f"persona-check-{group_key}"
                svc.session(uid).debug = True
                for user_text in messages:
                    try:
                        response = svc.handle(uid, user_text)
                        reply = str(response.get("reply", ""))
                        kind = str(response.get("kind", "unknown"))
                        trace = response.get("trace")
                        trace_available = bool(trace)
                        warnings = _trace_warnings(trace)
                    except Exception as exc:
                        # Exception text is intentionally omitted to avoid leaking configuration secrets.
                        reply = f"[Call failed: {type(exc).__name__}]"
                        kind = "error"
                        warnings = []
                        trace_available = False
                    results.append({
                        "group": group_key,
                        "user": user_text,
                        "reply": reply,
                        "kind": kind,
                        "warnings": warnings,
                        "trace_available": trace_available,
                        "flags": flag_reply(user_text, reply, kind),
                    })
                    call_index += 1
                    if call_index < total_calls and kind not in SKIP_KINDS and delay > 0:
                        time.sleep(delay)
        finally:
            store.close()

    summary = _summary(results)
    report = _render_markdown(results, summary)
    destination = Path(output_path).expanduser()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(report, encoding="utf-8")
    print(_summary_text(summary))
    return summary


def main(argv=None, sleep_seconds=None):
    args = parse_args(argv)
    delay = args.delay if sleep_seconds is None else sleep_seconds
    run_check(args.llm, args.out, delay=delay)
    return 0


if __name__ == "__main__":
    main()
