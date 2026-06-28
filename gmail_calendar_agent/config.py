"""Configuration loaded from the environment (and an optional .env file).

Keeping all knobs in one place makes the rest of the code easy to read and test.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

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

    # The Gmail account the user granted API access to. Used as the OAuth
    # ``login_hint`` (pre-selects the right account) and verified after sign-in.
    user_email: str = ""

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
            user_email=_get("USER_EMAIL", ""),
        )

    @property
    def llm_enabled(self) -> bool:
        """Whether the LLM layer can run (requires an API key)."""
        return bool(self.anthropic_api_key)


def save_user_email(email: str, env_file: str = ".env") -> None:
    """Persist ``USER_EMAIL`` to the .env file so the user isn't asked again.

    Updates an existing (uncommented) ``USER_EMAIL=`` line if present, otherwise
    appends one. Creates the file if it does not exist.
    """
    path = Path(env_file)
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    new_line = f"USER_EMAIL={email}"
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("USER_EMAIL=") and not stripped.startswith("#"):
            lines[i] = new_line
            break
    else:
        lines.append(new_line)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
