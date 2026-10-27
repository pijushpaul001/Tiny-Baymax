"""Settings from environment variables (and an optional .env file). No dependencies."""
import os
from dataclasses import dataclass, field
from pathlib import Path


def load_dotenv(path=".env"):
    p = Path(path)
    if not p.exists():
        return
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def parse_tokens(raw: str) -> dict:
    """'pijush=abc123,friend=xyz' -> {'abc123': 'pijush', 'xyz': 'friend'}"""
    out = {}
    for pair in (raw or "").split(","):
        if "=" in pair:
            user, token = pair.split("=", 1)
            if user.strip() and token.strip():
                out[token.strip()] = user.strip()
    return out


@dataclass
class Settings:
    data_dir: Path = Path("data")
    llm: str = "gemini"                      # "gemini" | "fake"
    gemini_api_key: str = ""
    model: str = "gemini-3.5-flash-lite"
    fallback_model: str = ""
    tokens: dict = field(default_factory=dict)   # token -> user id
    allow_no_auth: bool = False
    host: str = "127.0.0.1"
    port: int = 8080
    max_history: int = 24
    max_per_day: int = 200
    emergency_hint: str = "your local emergency number"
    allowed_origins: tuple[str, ...] = ()
    trusted_proxy: bool = False
    backup_keep: int = 7
    user_controls: bool = False

    @property
    def db_path(self) -> str:
        return str(Path(self.data_dir) / "baymax.db")

    @classmethod
    def from_env(cls):
        load_dotenv()
        e = os.environ.get
        return cls(
            data_dir=Path(e("BAYMAX_DATA_DIR", "data")),
            llm=e("BAYMAX_LLM", "gemini").lower(),
            gemini_api_key=e("GEMINI_API_KEY", ""),
            model=e("BAYMAX_MODEL", "gemini-3.5-flash-lite"),
            fallback_model=e("BAYMAX_FALLBACK_MODEL", ""),
            tokens=parse_tokens(e("BAYMAX_TOKENS", "")),
            allow_no_auth=e("BAYMAX_ALLOW_NO_AUTH", "") == "1",
            host=e("BAYMAX_HOST", "127.0.0.1"),
            port=int(e("BAYMAX_PORT", "8080")),
            max_history=int(e("BAYMAX_MAX_HISTORY", "24")),
            max_per_day=int(e("BAYMAX_MAX_PER_DAY", "200")),
            emergency_hint=e("BAYMAX_EMERGENCY_HINT", "your local emergency number"),
            allowed_origins=tuple(x.strip() for x in e("BAYMAX_ALLOWED_ORIGINS", "").split(",") if x.strip()),
            trusted_proxy=e("BAYMAX_TRUSTED_PROXY", "") == "1",
            backup_keep=max(1, int(e("BAYMAX_BACKUP_KEEP", "7"))),
            user_controls=e("BAYMAX_USER_CONTROLS", "0") == "1",
        )
