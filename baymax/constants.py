"""Shared constants. No logic and no imports from the rest of the package."""

MODES = ("listen", "reassure", "explain", "celebrate", "encourage", "playful", "concise")
DIFF_TYPES = ("physical", "emotional", "other", "none")
SIGNALS = ("positive", "negative", "distress", "curiosity", "connection", "conflict", "neutral")

# Resting values of the simulated emotion state (all 0.0 - 1.0).
BASELINE = dict(calmness=0.80, happiness=0.50, concern=0.10, curiosity=0.50, warmth=0.50, frustration=0.05)

GREETING = ["Hello. I am Baymax, your personal healthcare companion.",
            "How are you feeling today?"]
