"""Secret redaction and the long-term memory gate. Deterministic, no LLM involved."""
import re

from .detection import rx

# ---- secrets: removed before anything is sent to the LLM or stored
SECRET_RX = re.compile(
    r"\b(api[ _-]?key|password|passcode|secret|token|otp)\b\s*"
    r"(?:(?:is|=|:)\s*|\s+(?!was\b|were\b|are\b|got\b|received\b|rejected\b|"
    r"invalid\b|expired\b|missing\b|rotated\b|leaked\b|created\b|generated\b|"
    r"needed\b|works\b|failed\b|fails\b|sent\b|stored\b))\S+"
    r"|\bpin\s*(?:is|=|:)\s*\d+|AIza[\w-]{20,}", re.I
)
# Find a full formatted number run first, then decide based on its digit groups.
# This avoids leaving the tail of very long IDs and avoids treating six two-digit
# values ("10 20 30 40 50 60") as a secret solely because their sum is 12 digits.
_NUMBER_GROUP_RX = re.compile(r"(?<!\d)\d[\d -]{10,}\d(?!\d)")
SECRET_NOTE = "I can't accept or store keys or passwords, so I hid that part. Please don't share them here."


def redact_secrets(text: str):
    """Returns (safe_text, found_secret)."""
    safe = SECRET_RX.sub(lambda m: (m.group(1) + " [REDACTED]") if m.group(1) else "[REDACTED]", text)

    def redact_number(match):
        groups = re.findall(r"\d+", match.group(0))
        digits = sum(len(group) for group in groups)
        if digits >= 12 and any(len(group) >= 3 for group in groups):
            return "[REDACTED]"
        return match.group(0)

    safe = _NUMBER_GROUP_RX.sub(redact_number, safe)
    return safe, safe != text


def is_only_secret(safe_text: str) -> bool:
    """True when, after redaction, nothing meaningful is left of the message."""
    rest = re.sub(r"\[REDACTED\]|\b(?:my|the|is|api|key|password|passcode|secret|token|otp)\b|[^\w\s]", " ",
                  safe_text, flags=re.I)
    return len(rest.split()) < 3


# ---- long-term memory gate
BLOCK = rx("|".join([
    r"password|passcode|\bpin\b|\botp\b|api[ _-]?key|secret|token|AIza[\w-]{20,}",
    r"(?<!\d)(?:\d[ -]?){11,18}\d(?!\d)|\bcvv\b|credit card|debit card|bank|salary|income|loan|debt|\$|₹",
    r"\b(street|road|apartment|flat no|house no|pincode|zip ?code)\b|\blives? at\b",
    r"diagnos|medication|medicine|prescri|\bmg\b|tablet|surgery|symptom|allerg|injur|\bpain\b|infection|diabet|cancer|asthma",
    r"depress|anxiety|anxious|stressed|\bsad\b|lonely|suicid|self[- ]harm|kill myself|want to die",
    r"politic|\bvote\b|election|\bparty\b|divorce|affair|cheat|breakup|break up",
    r"\b(relationship|wife|husband|partner|girlfriend|boyfriend)\b|phone number|precise location",
]))


def memory_gate(fact: str, existing: list, enabled: bool = True, explicit: bool = False):
    """Deterministic last word on what may become a long-term memory."""
    f = (fact or "").strip()
    if not enabled and not explicit:
        return False, "auto-memory is off"
    if not f or len(f) > 200:
        return False, "empty or too long"
    if re.search(r"password|passcode|api[ _-]?key|secret|token|AIza[\w-]{20,}|(?<!\d)(?:\d[ -]?){11,18}\d(?!\d)", f, re.I):
        return False, "looks like a secret"
    # Explicit saves may enable user-requested stable facts, but never bypass the
    # sensitive-category blocklist (per the project architecture decision F-4).
    if BLOCK.search(f):
        return False, "sensitive/temporary category"
    if f.lower() in {e.lower() for e in existing}:
        return False, "duplicate"
    return True, "ok"
