"""ChatService: the app's front door. Commands, shutdown ritual, sessions, persistence.

Both the HTTP API and any future client (CLI, voice, robot) talk only to this class.
"""
import re
import threading
import time
from dataclasses import dataclass, field

from .brain import BaymaxBrain
from .constants import GREETING
from .decision import DecisionConfig, DecisionState
from .emotion import EmotionState
from .persona import PERSONA
from .safety import SECRET_NOTE, is_only_secret, memory_gate, redact_secrets
from .storage import Store

MAX_MESSAGE_CHARS = 2000
GREET_AFTER_SECONDS = 6 * 3600

YES = re.compile(
    r"(?:y|yes|yeah|yep|yup|sure|of course|definitely|satisfied|very satisfied|"
    r"i'?m (?:very )?satisfied|i am (?:very )?satisfied|"
    r"no problem(?: i am satisfied| i'm satisfied)?|no worries(?: i am satisfied| i'm satisfied)?)", re.I
)
NO = re.compile(
    r"(?:n|no|nope|nah|not really|not (?:very )?satisfied|i'?m not(?: (?:very )?satisfied)?|"
    r"i am not(?: (?:very )?satisfied)?|very disappointed|disappointed|unsatisfied|dissatisfied)", re.I
)
KEEP = re.compile(r"^(?:continue|keep going|go on|stay|not yet|carry on)(?:[.! ]*)$", re.I)
QUIT_WORDS = {"/quit", "/exit", "bye", "quit", "exit"}
EXIT_PHRASES = {
    "goodbye", "good night", "goodnight", "i'm done", "im done", "i am done",
    "that's all", "thats all", "see you", "see ya", "bye", "quit", "exit", "stop",
    "shut down", "shutdown", "/quit", "/exit",
}


def is_exit_intent(text: str) -> bool:
    """Recognize a short, whole-message exit request without catching ordinary prose."""
    normalized = re.sub(r"[.!?]+$", "", (text or "").strip().lower())
    return len(normalized.split()) <= 5 and normalized in EXIT_PHRASES


def _closing_reply_matches(pattern: re.Pattern, text: str) -> bool:
    """Accept only a short, complete answer to the satisfaction question."""
    normalized = re.sub(r"[,;:!? .]+$", "", (text or "").strip().lower())
    normalized = re.sub(r"\s+", " ", normalized)
    words = normalized.split()
    # These are complete affirmative replies despite their slightly greater length.
    extended_yes = {
        "no problem i am satisfied", "no problem i'm satisfied",
        "no worries i am satisfied", "no worries i'm satisfied",
    }
    if len(words) > 4 and normalized not in extended_yes:
        return False
    return bool(pattern.fullmatch(normalized))


HELP = """Commands
/help          Show this help.
/state         Show Baymax's simulated emotional state.
/memories      Show saved long-term memories.
/remember <f>  Save one non-sensitive fact.
/forget        Delete all long-term memories.
/clear         Clear conversation history and reset emotion.
/emotion-reset Reset only the simulated emotional state.
/memory-on     Enable automatic memory.
/memory-off    Disable automatic memory.
/ratings       Show your recent self-reported 0-10 ratings.
/debug         Show the decision trace with each reply.
/quit          Finish (Baymax asks for feedback first)."""


@dataclass
class Session:
    dstate: DecisionState = field(default_factory=DecisionState)
    closing: str = None            # None -> "asked" -> ("feedback" -> "decide")
    greeted_at: float = 0.0
    debug: bool = False
    invalidated: bool = False
    lock: threading.Lock = field(default_factory=threading.Lock)


class ChatService:
    def __init__(self, store: Store, llm, decision_cfg: DecisionConfig = None,
                 max_history: int = 24, max_per_day: int = 200):
        self.store, self.max_history, self.max_per_day = store, max_history, max_per_day
        self.brain = BaymaxBrain(llm, PERSONA, decision_cfg, history_turns=max_history)
        self._sessions, self._guard = {}, threading.Lock()

    # ------------------------------------------------------------ sessions
    def session(self, uid: str) -> Session:
        with self._guard:
            return self._sessions.setdefault(uid, Session())

    def open_session(self, uid: str) -> dict:
        """Called when the app opens. Greets once per session (and again after a long gap)."""
        s = self.session(uid)
        with s.lock:
            if s.invalidated:
                return self.open_session(uid)
            if time.time() - s.greeted_at > GREET_AFTER_SECONDS:
                s.greeted_at = time.time()
                s.closing = None
                self.store.add_messages(uid, [("assistant", " ".join(GREETING))])
        return {"history": self.store.history_with_time(uid, 40), "emotion": self._emotion(uid).to_dict(),
                "settings": self.store.get_settings(uid)}

    # ------------------------------------------------------------ helpers
    def _emotion(self, uid) -> EmotionState:
        return EmotionState.from_dict(self.store.get_emotion(uid))

    def _resp(self, uid, reply, kind="chat", mode=None, ended=False, s=None, **extra):
        out = {"reply": reply, "kind": kind, "mode": mode, "ended": ended,
               "closing": s.closing if s else None, "emotion": self._emotion(uid).to_dict()}
        out.update(extra)
        return out

    def _safety_resp(self, s, decision):
        # This path intentionally does not read SQLite or call the LLM.
        from .emotion import EmotionState
        return {"reply": decision.deterministic_reply, "kind": "safety", "mode": "reassure",
                "ended": False, "closing": s.closing, "emotion": EmotionState().to_dict(),
                "trace": decision.trace}

    def end_session(self, uid: str) -> dict:
        s = self.session(uid)
        with s.lock:
            s.closing = "asked"
            return self._resp(uid, "Are you satisfied with my care today?", kind="ritual", s=s,
                              ui={"quick_replies": ["Yes", "No"]})

    def remember(self, uid: str, fact: str) -> dict:
        """Save a user-requested memory without routing it through the current dialogue state."""
        s = self.session(uid)
        with s.lock:
            fact = (fact or "").strip()[:MAX_MESSAGE_CHARS]
            if not fact:
                reply = "Tell me what you want me to remember."
            else:
                memories = [item["fact"] for item in self.store.memories(uid)]
                ok, _ = memory_gate(fact, memories)
                if ok:
                    self.store.add_memory(uid, fact)
                    reply = "I will remember that."
                else:
                    reply = "I did not save that. It may already exist or contain sensitive information."
            return self._resp(uid, reply, kind="command", s=s)

    def clear_history(self, uid: str) -> dict:
        """Clear the conversation and reset emotion, even during the shutdown ritual."""
        s = self.session(uid)
        with s.lock:
            self.store.clear_history(uid)
            self.store.save_emotion(uid, EmotionState().to_dict())
            s.dstate = DecisionState()
            s.closing = None
            s.greeted_at = time.time()
            return self._resp(uid, "Conversation cleared. Long-term memories remain.", kind="command", s=s)

    def reset_emotion(self, uid: str) -> dict:
        """Reset simulated emotion without consuming the current dialogue as text."""
        s = self.session(uid)
        with s.lock:
            self.store.save_emotion(uid, EmotionState().to_dict())
            return self._resp(uid, "My simulated emotional state is back to baseline.", kind="command", s=s)

    def forget_user(self, uid: str):
        # Keep deletion behavior encapsulated in the service instead of exposing _sessions to the API.
        with self._guard:
            s = self._sessions.get(uid)
            if s is None:
                self.store.delete_all(uid)
            else:
                with s.lock:
                    self.store.delete_all(uid)
                    s.invalidated = True
                    self._sessions.pop(uid, None)

    # ------------------------------------------------------------ main entry
    def handle(self, uid: str, text: str) -> dict:
        text = (text or "").strip()[:MAX_MESSAGE_CHARS]
        s = self.session(uid)
        if not text:
            return self._resp(uid, "", kind="empty", s=s)
        with s.lock:
            if s.invalidated:
                return {"reply": "This session was reset. Please send your message again.", "kind": "error",
                        "mode": None, "ended": False, "closing": None, "emotion": EmotionState().to_dict()}
            return self._handle_locked(uid, text, s)

    def _handle_locked(self, uid, text, s):
        lower = text.lower()

        # Red flags take priority in every conversation state, without storage/model dependencies.
        safety = self.brain.layer.safety_check(text)
        if safety is not None:
            s.dstate.turn += 1
            if safety.detection.red_flag == "self_harm":
                s.dstate.safety_hold_until = s.dstate.turn + self.brain.layer.cfg.safety_hold_turns
            return self._safety_resp(s, safety)

        # ---- shutdown ritual
        if s.closing == "asked":
            # Negative phrases are checked first so "not satisfied" can never count as positive.
            if _closing_reply_matches(NO, lower):
                s.closing = "feedback"
                return self._resp(uid, "I am sorry. What could I have done better?", kind="ritual", s=s)
            if _closing_reply_matches(YES, lower):
                return self._finish(uid, s, "I am glad to hear that. Take care. Goodbye.")
            s.closing = None                         # unclear answer: carry on as normal conversation
        elif s.closing == "feedback":
            safe_feedback, _ = redact_secrets(text)
            self.store.add_feedback(uid, safe_feedback)  # separate table, never long-term memory
            s.closing = "decide"
            return self._resp(uid, "Thank you for telling me. Would you like to keep going, or shall I shut down?",
                              kind="ritual", s=s, ui={"quick_replies": ["Keep going", "Shut down"]})
        elif s.closing == "decide":
            if KEEP.fullmatch(lower):
                s.closing = None
                return self._resp(uid, "Alright. We can continue.", kind="ritual", s=s)
            if is_exit_intent(lower):
                return self._finish(uid, s, "Goodbye. Take care.")
            s.closing = None

        if lower in QUIT_WORDS or is_exit_intent(lower):
            s.closing = "asked"
            return self._resp(uid, "Are you satisfied with my care today?", kind="ritual", s=s,
                              ui={"quick_replies": ["Yes", "No"]})

        # ---- commands
        if lower.startswith("/"):
            cmd = self._command(uid, text, lower, s)
            if cmd is not None:
                return cmd

        return self._chat(uid, text, s)

    def _finish(self, uid, s, reply):
        s.closing = None
        s.greeted_at = 0.0                           # greet again next time the app opens
        return self._resp(uid, reply, kind="ritual", ended=True, s=s)

    # ------------------------------------------------------------ commands
    def _command(self, uid, text, lower, s):
        st = self.store
        r = lambda reply: self._resp(uid, reply, kind="command", s=s)
        if lower == "/help":
            return r(HELP)
        if lower == "/state":
            return r("Baymax simulated emotional state:\n\n" + self._emotion(uid).report())
        if lower == "/memories":
            items = st.memories(uid)
            return r("Long-term memories:\n\n" + ("\n".join(f"{i}. {m['fact']}" for i, m in enumerate(items, 1))
                                                  if items else "None"))
        if lower == "/remember" or lower.startswith("/remember "):
            fact = text[len("/remember"):].strip()
            if not fact:
                return r("Tell me what you want me to remember.")
            ok, _ = memory_gate(fact, [m["fact"] for m in st.memories(uid)])
            if ok:
                st.add_memory(uid, fact)
                return r("I will remember that.")
            return r("I did not save that. It may already exist or contain sensitive information.")
        if lower == "/forget":
            st.clear_memories(uid)
            return r("My saved long-term memories are cleared.")
        if lower == "/clear":
            st.clear_history(uid)
            st.save_emotion(uid, EmotionState().to_dict())
            s.dstate = DecisionState()
            return r("Conversation cleared. Long-term memories remain.")
        if lower == "/emotion-reset":
            st.save_emotion(uid, EmotionState().to_dict())
            return r("My simulated emotional state is back to baseline.")
        if lower in ("/memory-on", "/memory-off"):
            on = lower == "/memory-on"
            st.save_settings(uid, {"auto_memory": on})
            return r("Automatic memory is ON." if on else "Automatic memory is OFF. /remember still works.")
        if lower == "/ratings":
            rows = st.ratings(uid, 10)
            body = "\n".join(f"{x['ts'][:16]}  {x['type']}/{x['subtype']}: {x['rating']}/10" for x in rows) or "None"
            return r("Your recent self-reported ratings (not a diagnosis):\n\n" + body)
        if lower == "/debug":
            s.debug = not s.debug
            return r(f"Debug trace is {'ON' if s.debug else 'OFF'}.")
        return None                                  # unknown "/something": treat as normal text

    # ------------------------------------------------------------ conversation
    def _chat(self, uid, text, s):
        st = self.store
        if st.usage_today(uid) >= self.max_per_day:
            return self._resp(uid, "We have reached today's message limit. Let's talk again tomorrow.",
                              kind="limit", s=s)

        safe, had_secret = redact_secrets(text)
        if had_secret and is_only_secret(safe):      # nothing but a secret: answer without the LLM
            st.add_messages(uid, [("user", safe), ("assistant", SECRET_NOTE)])
            return self._resp(uid, SECRET_NOTE, kind="chat", s=s)

        emotion = self._emotion(uid)
        settings = st.get_settings(uid)
        history = st.history(uid, self.max_history)
        memories = [m["fact"] for m in st.memories(uid)]
        extra = ("\n\nSIMULATED BAYMAX STATE:\n" + emotion.report() + "\n\nLONG-TERM MEMORY:\n"
                 + ("\n".join(f"- {m}" for m in memories) if memories else "No memories are currently saved."))

        r = self.brain.turn(safe, history, memories, emotion, s.dstate, settings["auto_memory"], extra_system=extra)
        trace = r.decision.trace + ([f"warnings: {r.warnings}"] if r.warnings else []) if s.debug else None

        if r.signal and not r.decision.deterministic_reply and r.decision.detection.type == "none" \
                and r.decision.rating is None:
            emotion.apply_signal(r.signal)           # Python already appraised difficulties/ratings itself

        if r.llm_failed:
            # The decision (including a just-entered rating) survives a model outage.
            persisted = st.persist_turn(uid, pairs=None, emotion=emotion.to_dict(),
                                        rating_event=r.rating_event, bump=False)
            self._remember_rating_id(s, r.rating_event, persisted["rating_id"])
            return self._resp(uid, "I had trouble reaching my cloud brain. Please try again in a moment.",
                              kind="error", s=s, detail="; ".join(r.warnings), trace=trace)
        if r.used_fallback:                          # graceful failure: don't pollute history
            persisted = st.persist_turn(uid, pairs=None, emotion=emotion.to_dict(),
                                        rating_event=r.rating_event, bump=False)
            self._remember_rating_id(s, r.rating_event, persisted["rating_id"])
            return self._resp(uid, r.reply, kind="chat", mode=r.mode, s=s, trace=trace)

        memory_fact = None
        if r.memory_to_save and settings["auto_memory"]:
            ok, _ = memory_gate(r.memory_to_save, memories)
            if ok:
                memory_fact = r.memory_to_save
        persisted = st.persist_turn(
            uid, pairs=[("user", safe), ("assistant", r.reply)], emotion=emotion.to_dict(),
            rating_event=r.rating_event, memory=memory_fact, bump=True
        )
        self._remember_rating_id(s, r.rating_event, persisted["rating_id"])
        ui = {}
        if r.decision.rating_action in {"ask", "confirm"}:
            episode = s.dstate.episode
            about = "pain" if episode and episode.type == "physical" else "feeling"
            ui["rating"] = {"min": 0, "max": 10, "about": about, "skippable": True}
        if memory_fact and persisted["memory_id"]:
            ui["memory_saved"] = {"id": persisted["memory_id"], "fact": memory_fact}
        return self._resp(uid, r.reply, kind="chat", mode=r.mode, s=s,
                          memory_saved=memory_fact, trace=trace, **({"ui": ui} if ui else {}))

    @staticmethod
    def _remember_rating_id(s, rating_event, rating_id):
        if rating_event and rating_event.get("action", "record") == "record" and rating_id:
            episode = s.dstate.episode
            if episode and episode.rating == rating_event.get("rating"):
                episode.rating_id = int(rating_id)
