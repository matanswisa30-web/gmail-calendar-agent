"""Configuration loaded from the environment (and an optional .env file).

Keeping all knobs in one place makes the rest of the code easy to read and test.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

try:
    # python-dotenv is optional at import time; load .env if present.
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # pragma: no cover - dotenv is a declared dependency
    pass


# OAuth scopes required by the assignment (read/modify mail + manage calendar).
SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/calendar",
]

# Gmail label used to mark messages the agent has already handled.
PROCESSED_LABEL = "AI-Agent-Processed"

# Confidence below which the agent will not act on an email as an invitation.
CONFIDENCE_THRESHOLD = 0.6


def _get(name: str, default: str) -> str:
    value = os.environ.get(name)
    return value if value not in (None, "") else default


@dataclass
class Settings:
    """All runtime settings, resolved from environment variables."""

    anthropic_api_key: str = ""
    anthropic_model: str = "claude-opus-4-8"
    anthropic_effort: str = "low"

    lookback: str = "2d"
    default_duration_minutes: int = 60
    timezone: str = "Asia/Jerusalem"

    credentials_file: str = "credentials.json"
    token_file: str = "token.json"

    scopes: list[str] = field(default_factory=lambda: list(SCOPES))

    @classmethod
    def load(cls) -> "Settings":
        return cls(
            anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
            anthropic_model=_get("ANTHROPIC_MODEL", "claude-opus-4-8"),
            anthropic_effort=_get("ANTHROPIC_EFFORT", "low"),
            lookback=_get("LOOKBACK", "2d"),
            default_duration_minutes=int(_get("DEFAULT_DURATION_MINUTES", "60")),
            timezone=_get("TIMEZONE", "Asia/Jerusalem"),
            credentials_file=_get("CREDENTIALS_FILE", "credentials.json"),
            token_file=_get("TOKEN_FILE", "token.json"),
        )

    @property
    def llm_enabled(self) -> bool:
        """Whether the LLM layer can run (requires an API key)."""
        return bool(self.anthropic_api_key)
