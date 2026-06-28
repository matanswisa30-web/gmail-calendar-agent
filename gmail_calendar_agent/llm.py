"""LLM layer — Anthropic Claude for meeting-intent detection + detail extraction.

A single structured-output call returns both the classification (is this a meeting
invite?) and the extracted fields (date/time/participants/location). Using the API's
``output_config.format`` with a JSON schema means the model returns a validated object,
so there is no brittle string parsing on our side.

If no API key is configured, ``analyze_email`` falls back to the rule layer so the rest
of the agent still works (in a reduced, rules-only mode).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from .classifier import RuleSignal, rule_signal


@dataclass
class MeetingAnalysis:
    is_meeting_invite: bool
    confidence: float
    reasoning: str = ""
    title: str = ""
    date: str = ""          # "YYYY-MM-DD" or "" if unknown
    start_time: str = ""    # "HH:MM" (24h) or "" if unknown
    duration_minutes: int = 0
    participants: list[str] = field(default_factory=list)
    location: str = ""

    @property
    def has_concrete_time(self) -> bool:
        return bool(self.date) and bool(self.start_time)


# JSON schema for the structured output (no unsupported constraints).
_SCHEMA = {
    "type": "object",
    "properties": {
        "is_meeting_invite": {"type": "boolean"},
        "confidence": {"type": "number"},
        "reasoning": {"type": "string"},
        "title": {"type": "string"},
        "date": {"type": "string"},
        "start_time": {"type": "string"},
        "duration_minutes": {"type": "integer"},
        "participants": {"type": "array", "items": {"type": "string"}},
        "location": {"type": "string"},
    },
    "required": [
        "is_meeting_invite", "confidence", "reasoning", "title", "date",
        "start_time", "duration_minutes", "participants", "location",
    ],
    "additionalProperties": False,
}

_SYSTEM = (
    "You are an assistant that decides whether an email is a FREE-TEXT meeting "
    "invitation and, if so, extracts the meeting details. A free-text invitation "
    "is a message where a human proposes meeting in natural language (e.g. 'can we "
    "talk tomorrow at 3?'). It is NOT: newsletters, receipts, notifications, "
    "automated mail, or formal calendar (.ics) invites. Resolve relative dates "
    "(today/tomorrow/next Monday) against the provided current date and timezone. "
    "Use 24-hour HH:MM for start_time and YYYY-MM-DD for date. Leave date or "
    "start_time empty ('') if the email does not state a concrete one. participants "
    "should be email addresses when present. Be conservative: if it is not clearly "
    "a meeting request, set is_meeting_invite=false."
)


class AnthropicLLM:
    def __init__(self, api_key: str, model: str = "claude-opus-4-8",
                 effort: str = "low"):
        # Imported lazily so the package imports even without the SDK installed.
        import anthropic

        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = model
        self._effort = effort

    def analyze_email(
        self, subject: str, sender: str, body: str,
        now_iso: str, timezone: str, hint: RuleSignal | None = None,
    ) -> MeetingAnalysis:
        hint_text = ""
        if hint is not None:
            hint_text = (
                f"\n\n[Pre-filter hint: rule score={hint.score:.2f}, "
                f"keywords={hint.matched_keywords}, "
                f"time_hint={hint.has_time_hint}. Use only as a weak signal.]"
            )

        user = (
            f"Current date/time: {now_iso}\nTimezone: {timezone}\n\n"
            f"From: {sender}\nSubject: {subject}\n\n"
            f"Body:\n{body[:6000]}{hint_text}"
        )

        resp = self._client.messages.create(
            model=self._model,
            max_tokens=2048,
            thinking={"type": "adaptive"},
            output_config={
                "effort": self._effort,
                "format": {"type": "json_schema", "schema": _SCHEMA},
            },
            system=_SYSTEM,
            messages=[{"role": "user", "content": user}],
        )

        text = next((b.text for b in resp.content if b.type == "text"), "{}")
        data = json.loads(text)
        return MeetingAnalysis(
            is_meeting_invite=bool(data.get("is_meeting_invite", False)),
            confidence=float(data.get("confidence", 0.0)),
            reasoning=str(data.get("reasoning", "")),
            title=str(data.get("title", "")),
            date=str(data.get("date", "")),
            start_time=str(data.get("start_time", "")),
            duration_minutes=int(data.get("duration_minutes", 0)),
            participants=[str(p) for p in data.get("participants", [])],
            location=str(data.get("location", "")),
        )


def rules_only_analysis(subject: str, body: str) -> MeetingAnalysis:
    """Degraded analysis when no LLM is configured: classification only.

    The rule layer cannot reliably extract a date/time from free text, so the
    result will usually lack a concrete time and the agent will skip booking —
    by design. This keeps the pipeline runnable for testing without an API key.
    """
    sig = rule_signal(subject, body)
    return MeetingAnalysis(
        is_meeting_invite=sig.looks_like_invite,
        confidence=sig.score,
        reasoning=(
            "rules-only mode (no LLM configured): "
            f"keywords={sig.matched_keywords}, time_hint={sig.has_time_hint}"
        ),
        title=subject,
    )
