"""Rule-based pre-filter for meeting intent.

This is the *rules* half of the hybrid detection described in the PRD. On its own,
keyword rules recognise free-text invitations only ~40% of the time, so this layer is
used as a cheap signal/hint and as a degraded fallback when the LLM is unavailable —
never as the sole decision-maker when the LLM is configured.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Words/phrases that suggest someone wants to meet.
_MEETING_KEYWORDS = [
    "meet", "meeting", "catch up", "catch-up", "sync", "call", "zoom",
    "google meet", "hop on", "get together", "coffee", "lunch", "appointment",
    "schedule", "available", "availability", "free time", "are you free",
    "let's talk", "discuss in person", "book a", "set up a time", "slot",
    "פגישה", "להיפגש", "ניפגש", "פנוי", "זמין", "שיחה", "להתקשר",  # Hebrew
]

# Patterns that suggest a concrete time/day is being proposed.
_TIME_PATTERNS = [
    r"\b\d{1,2}:\d{2}\b",                      # 14:30
    r"\b\d{1,2}\s?(am|pm)\b",                  # 3pm
    r"\b(mon|tue|wed|thu|fri|sat|sun)[a-z]*\b",  # weekday
    r"\b(today|tomorrow|tonight|next week|this week)\b",
    r"\b(morning|afternoon|evening|noon)\b",
    r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{1,2}\b",
    r"\b(מחר|היום|מחרתיים|בשעה|ביום)\b",        # Hebrew time words
]

# Signals that an email is probably NOT a free-text invite.
_NEGATIVE_KEYWORDS = [
    "unsubscribe", "invoice", "receipt", "order #", "newsletter",
    "no-reply", "noreply", "verification code", "password reset",
    "out of office", "automatic reply",
]


@dataclass
class RuleSignal:
    score: float          # 0..1, rough likelihood of being a meeting invite
    matched_keywords: list[str]
    has_time_hint: bool

    @property
    def looks_like_invite(self) -> bool:
        return self.score >= 0.5


def rule_signal(subject: str, body: str) -> RuleSignal:
    """Score an email for meeting intent using keywords and time hints."""
    text = f"{subject}\n{body}".lower()

    matched = [kw for kw in _MEETING_KEYWORDS if kw in text]
    has_time = any(re.search(p, text) for p in _TIME_PATTERNS)
    has_question = "?" in text
    negatives = [kw for kw in _NEGATIVE_KEYWORDS if kw in text]

    score = 0.0
    score += min(len(matched), 3) * 0.2   # up to +0.6 from keywords
    if has_time:
        score += 0.3
    if has_question:
        score += 0.1
    if negatives:
        score -= 0.4

    score = max(0.0, min(1.0, score))
    return RuleSignal(
        score=score, matched_keywords=matched, has_time_hint=has_time
    )
