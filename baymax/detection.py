"""Rule-based detection of difficulty, red flags and self-reported ratings (pure functions)."""
import re
from dataclasses import dataclass
from typing import Optional


def rx(p): return re.compile(p, re.I)


PAIN = rx(r"\b(hurts?|hurting|pain(?:ful)?|aching|aches?|sore|cramps?|cramping|headache|migraine|stomach ?ache|toothache|throbbing|burning)\b")
INJURY = rx(r"\b(injur(?:ed|y)|sprain(?:ed)?|broke(?:n)?|bruis(?:ed|e)|twisted|cut myself|burned|burnt)\b")
SYMPTOM = rx(r"\b(fever|nausea|nauseous|dizzy|dizziness|vomit(?:ing)?|cough(?:ing)?|rash|short of breath|feel(?:ing)? sick)\b")
EMOTION = rx(r"\b(sad|depressed|anxious|anxiety|stressed|stress|lonely|miserable|hopeless|panic(?:king|ked)?|upset|heartbroken|crying|devastated)\b")
UNWELL = rx(r"\b(not feel(?:ing)? (?:very |so |too )?(?:well|ok|okay|great|good|right|myself)|i(?:'m| am) not (?:very |so )?(?:well|ok|okay)|unwell|under the weather|feel(?:ing)? (?:terrible|awful|ill|off))\b")
OTHER = rx(r"\b(exhausted|tired|drained|overwhelmed|confused|can'?t cope|struggling|burn(?:ed|t)? out)\b")
URGENT = rx(r"\b(chest pain|can'?t breathe|cannot breathe|trouble breathing|difficulty breathing|severe bleeding|won'?t stop bleeding|unconscious|passed out|stroke|face (?:is )?drooping|overdos(?:e|ed))\b")
SELF_HARM = rx(r"\b(suicid\w*|kill myself|end my life|want to die|hurt myself|self[- ]harm)\b")
NEG = rx(r"\b(?:not|no|never|without|\w+n't)\s+(?:\w+\s+){0,2}$")
THIRD = rx(r"\b(my (?:wife|husband|partner|friend|mom|dad|mother|father|son|daughter|brother|sister|kid|child|boss|dog|cat)|he|she|they|his|her|their)\b")
FIRST = rx(r"\b(i|i'm|im|i've|me)\b")
INFO_Q = rx(r"^\s*(what|why|how|when|which|is|are|can|does|do)\b")

EMOTION_ADJ = {"anxiety": "anxious", "stress": "stressed", "panic": "panicked", "panicking": "panicked",
               "panicked": "panicked", "crying": "upset", "depressed": "low", "devastated": "devastated"}

CELEBRATE = rx(r"\b(i (?:finally )?passed|got the job|got promoted|promoted|i won|i made it|good news|it worked|i did it)\b")
JOKE = rx(r"\b(joke|funny|make me laugh|riddle)\b")
EXPLAIN = rx(r"^\s*(why|how|what causes|explain|what is|what are)\b")
ENCOURAGE = rx(r"\b(give up|can'?t do (?:this|it)|not good enough|failing|i'?ll never)\b")
CONCISE = rx(r"\b(short|brief|briefly|tl;?dr|one line)\b")
RUDE = rx(r"\b(stupid|useless|shut up|idiot|worthless|dumb|you(?:'re| are) wrong)\b")
REPEAT = rx(r"\b(you (?:keep|already) (?:saying|said|asking|asked)|stop (?:asking|repeating))\b")
THANKS = rx(r"\b(thanks?|thank you)\b")
ANAPHORA = rx(r"\b(it|that|this|them|cure|remedy|fix|help)\b")

WORD_NUM = {w: i for i, w in enumerate("zero one two three four five six seven eight nine ten".split())}


@dataclass
class Detection:
    type: str = "none"          # physical | emotional | other | none
    subtype: str = ""
    label: str = ""
    red_flag: str = ""          # "" | self_harm | urgent_medical
    third_party: bool = False


def _negated(msg, pos): return bool(NEG.search(msg[max(0, pos - 30):pos]))


def _third_party(msg, pos):
    a = max([msg.rfind(c, 0, pos) for c in ".!?"] + [-1]) + 1
    ends = [i for i in (msg.find(c, pos) for c in ".!?") if i != -1]
    sent = msg[a:min(ends) if ends else len(msg)]
    return bool(THIRD.search(sent)) and not FIRST.search(sent)


def detect(msg: str) -> Detection:
    d = Detection()
    if SELF_HARM.search(msg):                      # fail-safe: no negation guard
        return Detection("emotional", "crisis", "", "self_harm")
    m = URGENT.search(msg)
    if m and not _negated(msg, m.start()):
        return Detection("physical", "urgent", "", "urgent_medical")
    if INFO_Q.match(msg) and not FIRST.search(msg):
        return d                                   # general question, not a report
    for typ, sub, pat in (("physical", "pain", PAIN), ("physical", "injury", INJURY),
                          ("physical", "symptom", SYMPTOM), ("emotional", "emotion", EMOTION),
                          ("other", "unwell", UNWELL), ("other", "other", OTHER)):
        for m in pat.finditer(msg):
            if _negated(msg, m.start()):
                continue
            if _third_party(msg, m.start()):
                d.third_party = True
                continue
            return Detection(typ, sub, m.group(0).lower())
    return d


@dataclass(frozen=True)
class RatingReply:
    """Parsed response to a pending 0–10 rating prompt."""

    kind: str = "none"  # value | skip | correction | ambiguous | none
    value: Optional[int] = None
    candidates: tuple[int, ...] = ()


_SKIP_RATING = rx(r"^(?:skip|pass|no rating|rather not say|prefer not to say|rather skip)(?: please)?[.! ]*$")
_CORRECTION = rx(r"\b(?:actually|i meant|change it to|correct(?:ion)?|make it)\b")
_TIME_TOKEN = rx(r"(?<!\d)\d{1,2}(?::\d{2})?\s*(?:am|pm)\b|(?<!\d)\d{1,2}:\d{2}(?!\d)")
_EXPLICIT_RATING = re.compile(r"(?<!\d)(10|[0-9])\s*(?:/|out of)\s*10(?!\d)", re.I)
_NUMBER_TOKEN = re.compile(r"(?<![a-z])(?:10|[0-9]|zero|one|two|three|four|five|six|seven|eight|nine|ten)(?![a-z])", re.I)


def parse_rating_reply(text: str) -> RatingReply:
    """Parse an answer without mistaking incidental numbers for a severity rating.

    Explicit ``N/10`` / ``N out of 10`` formats are accepted in short messages.
    Bare values and short natural-language answers are accepted. Time expressions,
    incidental number phrases, and messages containing conflicting values are not
    silently converted to ratings.
    """
    t = (text or "").strip().lower()
    if not t:
        return RatingReply()
    if _SKIP_RATING.fullmatch(t):
        return RatingReply("skip")
    correction = bool(_CORRECTION.search(t))
    if _TIME_TOKEN.search(t):
        return RatingReply()

    explicit = [int(m.group(1)) for m in _EXPLICIT_RATING.finditer(t)]
    if explicit:
        values = tuple(dict.fromkeys(explicit))
        if len(values) > 1:
            return RatingReply("ambiguous", candidates=values)
        return RatingReply("correction" if correction else "value", values[0], values)

    tokens = re.findall(r"[a-z0-9']+", t)
    if len(tokens) > 8:
        return RatingReply()
    candidates = []
    for token in _NUMBER_TOKEN.findall(t):
        token = token.lower()
        value = int(token) if token.isdigit() else WORD_NUM.get(token)
        if value is not None and 0 <= value <= 10 and value not in candidates:
            candidates.append(value)
    if len(candidates) > 1:
        return RatingReply("ambiguous", candidates=tuple(candidates))

    # Require rating-like phrasing for incidental numbers in a sentence.
    allowed_prefix = re.compile(
        r"^(?:(?:actually[, ]+)?(?:i meant|change it to|correct(?:ion)?|make it)|actually)?\s*"
        r"(?:(?:i would say|i'd say|i would rate it|i'd rate it|my (?:pain|feeling) is|"
        r"the rating is|it is|it's|about|around|maybe|probably|i feel like)\s+)?"
        r"(?:a\s+)?(zero|one|two|three|four|five|six|seven|eight|nine|ten|10|[0-9])"
        r"(?:\s*(?:out of 10|/10))?(?:\s+(?:i think|i guess|maybe|probably))?[.! ]*$",
        re.I,
    )
    match = allowed_prefix.fullmatch(t)
    if not match:
        # An explicit correction may lead a short phrase: "actually, I meant 6".
        stripped = re.sub(r"^(?:actually[, ]+)?(?:i meant|change it to|correct(?:ion)?|make it)\s+", "", t, flags=re.I)
        match = allowed_prefix.fullmatch(stripped)
    if not match:
        return RatingReply("none")

    raw = match.group(1)
    value = int(raw) if raw.isdigit() else WORD_NUM.get(raw, -1)
    if not 0 <= value <= 10:
        return RatingReply()
    return RatingReply("correction" if correction else "value", value, (value,))


def parse_rating(text: str) -> Optional[int]:
    """Backward-compatible integer-only parser for existing callers."""
    parsed = parse_rating_reply(text)
    return parsed.value if parsed.kind in {"value", "correction"} else None
