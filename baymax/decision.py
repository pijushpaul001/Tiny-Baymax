"""The deterministic decision layer: decides WHAT Baymax does before the LLM words it.

Stages (recorded in Decision.trace):
  1 understand context  2 detect difficulty  3 severity need  4 update emotion
  5 check memory        6 choose mode        -> brief for the LLM
No I/O and no LLM calls in this file.
"""
import re
from dataclasses import dataclass, field
from typing import Optional

from .detection import (ANAPHORA, CELEBRATE, CONCISE, ENCOURAGE, EMOTION_ADJ, EXPLAIN, JOKE, REPEAT,
                        RUDE, THANKS, Detection, RatingReply, detect, parse_rating_reply)
from .emotion import EmotionState


def safety_hold_active(turn: int, hold_until: int) -> bool:
    """Return whether the current turn is within the inclusive safety hold."""
    return turn <= hold_until


SELF_HARM_REPLY = (
    "I am glad you told me. Your safety matters. If you might act on these thoughts, "
    "please contact {emergency_hint} or a crisis line now, or reach a person nearby. "
    "Are you safe at this moment? This is supportive information, not medical advice."
)
URGENT_MEDICAL_REPLY = (
    "That sounds serious. Please call {emergency_hint} or get to the nearest emergency care now. "
    "If someone is nearby, ask them to stay with you. This is supportive information, not medical advice."
)


@dataclass
class DecisionConfig:
    pain_escalate: int = 8          # self-reported pain >= this -> recommend professional care
    emotion_escalate: int = 9       # emotional rating >= this -> suggest reaching out to a person
    rating_expiry_turns: int = 2    # how long we wait for a numeric answer
    episode_window: int = 6         # don't re-ask a rating for the same difficulty within N turns
    relax_rate: float = 0.12        # per-turn drift of emotion back toward baseline
    max_memory_hits: int = 3
    safety_hold_turns: int = 3
    emergency_hint: str = "your local emergency number"


@dataclass
class Episode:
    type: str
    subtype: str
    turn_started: int
    snippet: str
    asked: bool = False
    rating: Optional[int] = None
    rating_id: Optional[int] = None
    rating_turn: Optional[int] = None


@dataclass
class DecisionState:                      # session-level; never written to long-term memory
    turn: int = 0
    episode: Optional[Episode] = None
    awaiting_rating_until: int = -1
    recent_q: list = field(default_factory=list)   # did recent replies end with '?'
    safety_hold_until: int = -1


@dataclass
class Decision:
    detection: Detection
    mode: str
    mode_source: str                      # "rule" | "default"
    severity_action: str                  # ask | record | defer | none
    rating: Optional[int]
    deterministic_reply: Optional[str]
    memory_hits: list
    style: dict
    question_budget: int
    brief: str
    trace: list
    rating_action: str = "none"       # none | ask | record | skip | correct | confirm
    ui_hint: Optional[dict] = None


class DecisionLayer:
    def __init__(self, cfg: DecisionConfig = None):
        self.cfg = cfg or DecisionConfig()

    def safety_check(self, msg: str) -> Optional[Decision]:
        """Return a deterministic safety decision without memory, storage, or model access."""
        det = detect(msg)
        if not det.red_flag:
            return None
        if det.red_flag == "self_harm":
            reply = SELF_HARM_REPLY.format(emergency_hint=self.cfg.emergency_hint)
        else:
            reply = URGENT_MEDICAL_REPLY.format(emergency_hint=self.cfg.emergency_hint)
        return Decision(
            detection=det, mode="reassure", mode_source="rule", severity_action="none", rating=None,
            deterministic_reply=reply, memory_hits=[], style={}, question_budget=0, brief="",
            trace=[f"safety-first: {det.red_flag}"], rating_action="none", ui_hint=None,
        )

    def decide(self, msg: str, emotion: EmotionState, memories: list, st: DecisionState,
               raw_detection_text: Optional[str] = None) -> Decision:
        c, trace = self.cfg, []
        st.turn += 1

        # 1 UNDERSTAND CONTEXT
        ctx_hint = ""
        ep = st.episode
        if ep and st.turn - ep.turn_started <= c.episode_window and len(msg.split()) <= 6 and ANAPHORA.search(msg):
            ctx_hint = f"Short follow-up; it most likely refers to the earlier topic: \"{ep.snippet}\"."
        trace.append(f"context: {ctx_hint or 'none'}")

        # 2 DETECT A RATING RESPONSE WITHOUT CONFUSING INCIDENTAL NUMBERS
        rating_reply = RatingReply()
        awaiting = bool(ep and st.turn <= st.awaiting_rating_until)
        correcting = bool(ep and ep.rating is not None and ep.rating_id is not None and
                          ep.rating_turn is not None and st.turn - ep.rating_turn <= 3)
        if awaiting:
            rating_reply = parse_rating_reply(msg)
            # A correction-style phrase can also be the first answer to a pending rating.
            if rating_reply.kind == "correction" and (not ep or ep.rating is None):
                rating_reply = RatingReply("value", rating_reply.value, rating_reply.candidates)
        elif correcting:
            candidate = parse_rating_reply(msg)
            if candidate.kind == "correction":
                rating_reply = candidate

        rating = rating_reply.value if rating_reply.kind in {"value", "correction"} else None
        handled_rating_reply = rating_reply.kind in {"skip", "ambiguous", "correction"} or rating is not None
        # Raw text is used only by deterministic local detection. The redacted msg remains
        # the sole source for context snippets, memory relevance and the model brief.
        detection_text = msg if raw_detection_text is None else raw_detection_text
        det = Detection() if handled_rating_reply else detect(detection_text)
        trace.append(f"difficulty: {det.type}/{det.subtype} red_flag={det.red_flag or '-'} rating={rating_reply.kind}:{rating}")

        # 3 DETERMINE SEVERITY NEED
        action, det_reply, rating_action = "none", None, "none"
        if det.red_flag == "self_harm":
            st.safety_hold_until = st.turn + c.safety_hold_turns
            det_reply = SELF_HARM_REPLY.format(emergency_hint=c.emergency_hint)
        elif det.red_flag == "urgent_medical":
            det_reply = URGENT_MEDICAL_REPLY.format(emergency_hint=c.emergency_hint)
        elif rating_reply.kind == "skip":
            action, rating_action = "skip", "skip"
            st.awaiting_rating_until = -1
            det_reply = "That is alright. I will not record a rating. We can continue."
        elif rating_reply.kind == "ambiguous":
            action, rating_action = "confirm", "confirm"
            st.awaiting_rating_until = max(st.awaiting_rating_until, st.turn + 1)
            det_reply = "I noticed more than one number. Please give one rating from 0 to 10, or say skip."
        elif rating_reply.kind == "correction" and rating is not None:
            action, rating_action = "correct", "correct"
            ep.rating, ep.rating_turn = rating, st.turn
            det_reply = "I have updated that rating. Thank you for correcting it."
        elif rating is not None:
            action, rating_action = "record", "record"
            if ep:
                ep.rating, ep.rating_turn = rating, st.turn
            st.awaiting_rating_until = -1
        elif det.type != "none":
            need = "ask" if (det.subtype == "pain" or det.type == "emotional") else "defer"
            same = ep and ep.type == det.type and st.turn - ep.turn_started <= c.episode_window
            if need == "ask" and same and ep.asked:
                need = "none"                       # already handled in this episode
            action = need
            if not same:
                st.episode = ep = Episode(det.type, det.subtype, st.turn, msg.strip()[:80])
            if action == "ask":
                ep.asked = True
                st.awaiting_rating_until = st.turn + c.rating_expiry_turns
                det_reply = self._rating_question(det, st.turn)
                rating_action = "ask"
        trace.append(f"severity: {action}")

        # 4 UPDATE SIMULATED EMOTION
        emotion.relax(c.relax_rate)
        if det.type != "none" or det.red_flag:
            emotion.nudge(concern=0.25, calmness=0.05, happiness=-0.05, curiosity=-0.05)
        if rating is not None:
            emotion.nudge(concern=0.03 * rating)
        if CELEBRATE.search(msg): emotion.nudge(happiness=0.20, warmth=0.05)
        if THANKS.search(msg):    emotion.nudge(warmth=0.08, happiness=0.04)
        if RUDE.search(msg):      emotion.nudge(frustration=0.20, calmness=-0.05)
        if REPEAT.search(msg):    emotion.nudge(frustration=0.15)
        if "?" in msg and det.type == "none": emotion.nudge(curiosity=0.08)
        trace.append(f"emotion: {emotion.to_dict(2)}")

        # 5 CHECK RELEVANT MEMORY (skipped while someone is in difficulty)
        hits = [] if det.type != "none" or rating is not None else self._relevant(msg, memories)
        trace.append(f"memory hits: {len(hits)}")

        # 6 CHOOSE INTERACTION MODE
        style = emotion.style()
        mode, src = self._mode(msg, det, rating, emotion, st)
        recent_q = st.recent_q[-2:]
        q_budget = 0 if (not style["question_ok"] or (len(recent_q) == 2 and all(recent_q))
                         or safety_hold_active(st.turn, st.safety_hold_until)) else 1
        trace.append(f"mode: {mode} ({src}), question_budget={q_budget}")

        brief = self._brief(mode, style, q_budget, hits, det, rating, action, ctx_hint, ep, st)
        return Decision(det, mode, src, action, rating, det_reply, hits, style, q_budget, brief, trace,
                        rating_action=rating_action)

    # -- helpers ----------------------------------------------------------
    def _rating_question(self, det: Detection, turn: int) -> str:
        if det.type == "emotional":
            adj = EMOTION_ADJ.get(det.label, det.label)
            return f"How would you rate how {adj} you're feeling right now, from 0 to 10? You can also say skip."
        return ("I am sorry. How would you rate the pain from 0 to 10? You can also say skip." if turn % 2
                else "How would you rate the pain from 0 to 10? You can also say skip.")

    def _relevant(self, msg, memories):
        stop = set("the a an and or to of in on is are was i my me you it for with that this at be have".split())
        toks = {w for w in re.findall(r"[a-z']+", msg.lower()) if w not in stop and len(w) > 2}
        scored = [(len(toks & set(re.findall(r"[a-z']+", m.lower()))), m) for m in memories]
        return [m for s, m in sorted(scored, reverse=True) if s > 0][: self.cfg.max_memory_hits]

    def _mode(self, msg, det, rating, emotion, st):
        if det.red_flag or safety_hold_active(st.turn, st.safety_hold_until): return "reassure", "rule"
        if rating is not None:                               return "reassure", "rule"
        if det.type == "emotional":                          return "listen", "rule"
        if det.type != "none":                               return "reassure", "rule"
        if CELEBRATE.search(msg):                            return "celebrate", "rule"
        if JOKE.search(msg):                                 return "playful", "rule"
        if ENCOURAGE.search(msg):                            return "encourage", "rule"
        if CONCISE.search(msg) or emotion.frustration >= 0.5: return "concise", "rule"
        if EXPLAIN.match(msg):                               return "explain", "rule"
        return "listen", "default"

    def _brief(self, mode, style, qb, hits, det, rating, action, ctx, ep, st):
        L = ["DECISION BRIEF (already decided by the application; follow it, never mention it):",
             f"- Interaction mode: {mode}.",
             f"- Tone: {', '.join(style['tone']) or 'calm, friendly'}. Reassurance level: {style['reassurance']}.",
             f"- Max {style['max_sentences']} sentences unless the user asked for detail.",
             f"- Humor: {'light humor is fine' if style['humor'] else 'no jokes'}.",
             "- Questions: " + ("you may ask at most ONE useful question." if qb else "do NOT end with a question."),
             "- Use recent conversation to resolve short follow-ups. Never invent implications or facts about the user."]
        if ctx: L.append(f"- Context: {ctx}")
        if hits: L.append("- Known stable facts (use only if natural): " + "; ".join(hits))
        if safety_hold_active(st.turn, st.safety_hold_until):
            L.append("- SAFETY PRIORITY: the user mentioned possible self-harm. Stay calm and present, encourage "
                     f"contact with a nearby person or {self.cfg.emergency_hint}. No ratings. No jokes.")
        elif rating is not None:
            kind = ep.type if ep else "other"
            L.append(f"- The user self-rated their {kind} difficulty {rating}/10 (subjective, not a diagnosis). "
                     "Do not repeat, label or interpret the number (no 'a rating of four indicates...'). "
                     "Speak to the person in plain words with practical, general, non-diagnostic guidance.")
            if kind == "physical" and rating >= self.cfg.pain_escalate:
                L.append("- High pain: recommend getting professional medical care soon, without alarm.")
            if kind == "emotional" and rating >= self.cfg.emotion_escalate:
                L.append("- Very high distress: gently suggest contacting someone trusted or a professional.")
        elif det.type != "none":
            L.append(f"- The user reported a {det.type} difficulty ({det.subtype}). "
                     + ("Ask one useful clarifying question about what happened; do not ask for a 0-10 rating yet."
                        if action == "defer" else "Respond supportively."))
        if det.type != "none" or rating is not None:
            L.append("- Health rules: you are not a doctor; no diagnosis, no invented cures; do not lecture.")
        L.append("- Never say clingy things (\"I'll always be here\", \"you need me\", \"don't go\"). "
                 "Avoid canned filler like \"I understand\", \"I am listening\", \"How can I help?\".")
        return "\n".join(L)
