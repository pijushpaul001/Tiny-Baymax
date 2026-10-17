"""Simulated emotional state. These are computational variables, not real feelings."""
from dataclasses import dataclass

from .constants import BASELINE

# What Gemini's per-message `signal` does to the state.
SIGNAL_DELTAS = {
    "positive":   dict(happiness=0.08, calmness=0.02, frustration=-0.03),
    "negative":   dict(happiness=-0.04, concern=0.06, calmness=-0.02),
    "distress":   dict(concern=0.14, calmness=-0.04, warmth=0.06),
    "curiosity":  dict(curiosity=0.10),
    "connection": dict(warmth=0.09, happiness=0.03, calmness=0.01),
    "conflict":   dict(frustration=0.10, calmness=-0.05, warmth=-0.02),
}


@dataclass
class EmotionState:
    calmness: float = BASELINE["calmness"]
    happiness: float = BASELINE["happiness"]
    concern: float = BASELINE["concern"]
    curiosity: float = BASELINE["curiosity"]
    warmth: float = BASELINE["warmth"]
    frustration: float = BASELINE["frustration"]

    def _clamp(self):
        for k in BASELINE:
            setattr(self, k, min(1.0, max(0.0, getattr(self, k))))

    def nudge(self, **deltas):
        for k, v in deltas.items():
            if k in BASELINE:
                setattr(self, k, getattr(self, k) + v)
        self._clamp()

    def apply_signal(self, signal: str):
        self.nudge(**SIGNAL_DELTAS.get(signal, {}))

    def relax(self, rate: float):
        """Drift back toward baseline."""
        for k, b in BASELINE.items():
            v = getattr(self, k)
            setattr(self, k, v + (b - v) * rate)
        self._clamp()

    def to_dict(self, digits: int = 3):
        return {k: round(getattr(self, k), digits) for k in BASELINE}

    @classmethod
    def from_dict(cls, d):
        vals = dict(BASELINE)
        if isinstance(d, dict):
            for k in BASELINE:
                try:
                    vals[k] = float(d[k])
                except (KeyError, TypeError, ValueError):
                    pass
        e = cls(**vals)
        e._clamp()
        return e

    def dominant(self) -> str:
        v = self.to_dict()
        return max(v, key=v.get)

    def style(self) -> dict:
        """Turn the numbers into behaviour the user can notice."""
        s = dict(tone=[], humor=False, max_sentences=3, question_ok=True, reassurance="normal")
        if self.concern >= 0.5:
            s.update(reassurance="high", humor=False)
            s["tone"] += ["calm", "attentive", "steady", "not playful"]
        elif self.concern >= 0.3:
            s.update(reassurance="moderate")
            s["tone"].append("gentle")
        elif self.happiness >= 0.5:
            s["humor"] = True
        if self.happiness >= 0.7 and self.concern < 0.3:
            s["humor"] = True
            s["tone"] += ["upbeat", "playful"]
        if self.curiosity >= 0.7 and self.concern < 0.5:
            s["max_sentences"] = 4
            s["tone"].append("curious about the topic, but never interrogating")
        if self.warmth >= 0.7:
            s["tone"].append("familiar and warm, never clingy")
        if self.frustration >= 0.5:
            s.update(max_sentences=2, question_ok=False, humor=False)
            s["tone"] += ["patient", "plain", "gently invite short, specific messages", "never hostile"]
        return s

    def report(self) -> str:
        v = self.to_dict(2)
        return (f"Calmness   : {v['calmness']:.2f}\nHappiness  : {v['happiness']:.2f}\n"
                f"Concern    : {v['concern']:.2f}\nCuriosity  : {v['curiosity']:.2f}\n"
                f"Warmth     : {v['warmth']:.2f}\nFrustration: {v['frustration']:.2f}\n"
                f"Dominant   : {self.dominant()}\n"
                f"Style      : {', '.join(self.style()['tone']) or 'relaxed, balanced'}")
