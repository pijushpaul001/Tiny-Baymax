"""BaymaxBrain: decision layer -> LLM -> validation. Knows nothing about HTTP or storage."""
import json
import re
from dataclasses import dataclass
from typing import Optional

from .constants import DIFF_TYPES, MODES, SIGNALS
from .llm.base import classify_llm_error
from .decision import Decision, DecisionConfig, DecisionLayer, DecisionState
from .detection import rx
from .emotion import EmotionState
from .persona import PERSONA, RESPONSE_SCHEMA
from .safety import memory_gate

FILLER = rx(r"\bi am listening\b|\bi understand\b|how can i help|always here for you|would you like to tell me more")
CLINGY = rx(r"always be here|you need me|don'?t go\b|cannot leave|can'?t leave|don'?t want you to leave")
FALLBACK = "Sorry, I lost my train of thought for a moment. Could you say that again?"


def validate_output(raw: str):
    """Returns (dict | None, warnings). Never raises."""
    w = []
    try:
        data = json.loads(re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.M).strip())
        assert isinstance(data, dict) and isinstance(data.get("reply"), str) and data["reply"].strip()
    except Exception as e:
        return None, [f"invalid JSON/shape: {type(e).__name__}"]
    if data.get("interaction_mode") not in MODES:
        data["interaction_mode"] = None
        w.append("bad mode")
    if data.get("signal") not in SIGNALS:
        data["signal"] = "neutral"
    diff = data.get("difficulty") if isinstance(data.get("difficulty"), dict) else {}
    diff.setdefault("detected", False)
    diff["type"] = diff.get("type") if diff.get("type") in DIFF_TYPES else "none"
    data["difficulty"] = diff
    mem = data.get("memory") if isinstance(data.get("memory"), dict) else {}
    data["memory"] = {"save": bool(mem.get("save")), "fact": str(mem.get("fact") or "")}
    return data, w


@dataclass
class TurnResult:
    reply: str
    mode: str
    signal: Optional[str]            # None when Python answered without the LLM
    decision: Decision
    memory_to_save: Optional[str]
    rating_event: Optional[dict]
    warnings: list
    llm_error_code: Optional[str] = None
    llm_error_type: Optional[str] = None

    @property
    def llm_failed(self) -> bool:
        return any(w.startswith("llm error") for w in self.warnings)

    @property
    def used_fallback(self) -> bool:
        return self.reply == FALLBACK and not self.decision.deterministic_reply


class BaymaxBrain:
    def __init__(self, llm, persona: str = PERSONA, cfg: DecisionConfig = None, history_turns: int = 24):
        self.llm, self.persona, self.history_turns = llm, persona, history_turns
        self.layer = DecisionLayer(cfg)

    def turn(self, user_msg: str, history: list, memories: list, emotion: EmotionState,
             st: DecisionState, memory_enabled: bool = True, extra_system: str = "",
             raw_detection_text: Optional[str] = None) -> TurnResult:
        d = self.layer.decide(user_msg, emotion, memories, st, raw_detection_text=raw_detection_text)
        warnings, mem_fact, signal = [], None, None
        llm_error_code = llm_error_type = None
        mode = d.mode
        rating_event = None
        if d.rating_action in {"record", "correct"} and d.rating is not None and st.episode:
            rating_event = {
                "action": d.rating_action,
                "id": st.episode.rating_id if d.rating_action == "correct" else None,
                "type": st.episode.type,
                "subtype": st.episode.subtype,
                "rating": d.rating,
                "turn": st.turn,
            }

        if d.deterministic_reply:                        # Python-enforced; the LLM is not consulted
            reply = d.deterministic_reply
        else:
            reply = FALLBACK
            try:
                system, data = self.persona + "\n\n" + d.brief + extra_system, None
                for attempt in range(2):                 # 2nd attempt only if style rules were broken
                    raw = self.llm.generate(system, history[-self.history_turns:], user_msg, RESPONSE_SCHEMA)
                    data, w = validate_output(raw)
                    warnings += w
                    if data and attempt == 0 and (CLINGY.search(data["reply"]) or FILLER.search(data["reply"])):
                        system += ("\n- Your previous draft used banned filler or clingy wording. "
                                   "Rewrite it naturally without it.")
                        warnings.append("style retry")
                        continue
                    break
                if data:
                    reply, signal = data["reply"].strip(), data["signal"]
                    if d.mode_source == "default" and data["interaction_mode"]:
                        mode = data["interaction_mode"]  # LLM may refine only when no rule fired
                    if d.question_budget == 0 and reply.endswith("?"):
                        parts = re.split(r"(?<=[.!])\s+", reply)
                        if len(parts) > 1:
                            reply = " ".join(parts[:-1])
                            warnings.append("trimmed trailing question")
                    if CLINGY.search(reply):
                        warnings.append("clingy phrasing")
                    if data["memory"]["save"] and d.detection.type == "none":   # never auto-save during a difficulty
                        ok, why = memory_gate(data["memory"]["fact"], memories, memory_enabled)
                        mem_fact = data["memory"]["fact"].strip() if ok else None
                        if not ok:
                            warnings.append(f"memory blocked: {why}")
            except Exception as e:                       # an API failure must never crash the app
                llm_error_code = classify_llm_error(e)
                llm_error_type = getattr(e, "exception_type", None) or type(e).__name__
                warnings.append(f"llm error: code={llm_error_code} type={llm_error_type}")

        st.recent_q = (st.recent_q + [reply.rstrip().endswith("?")])[-4:]
        return TurnResult(reply, mode, signal, d, mem_fact, rating_event, warnings,
                          llm_error_code=llm_error_code, llm_error_type=llm_error_type)
