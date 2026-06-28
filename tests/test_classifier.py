"""Offline tests for the rule-based pre-filter.

These need no network, credentials, or API key — they validate that the rule layer
points in the right direction for clear invitations vs. clear non-invitations.

Run with:  uv run python -m pytest    (or)    uv run python tests/test_classifier.py
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gmail_calendar_agent.classifier import rule_signal  # noqa: E402


INVITES = [
    ("Coffee chat?", "Hey, are you free to meet tomorrow at 14:00 for a coffee?"),
    ("Quick sync", "Can we hop on a call Monday afternoon to discuss the project?"),
    ("פגישה", "אפשר להיפגש מחר בשעה 10:00? אני פנוי בבוקר."),
]

NON_INVITES = [
    ("Your invoice #4471", "Please find attached invoice. To unsubscribe click here."),
    ("Welcome to our newsletter", "Here are this week's top articles. no-reply@news.com"),
    ("Verification code", "Your verification code is 558213. Do not share it."),
]


def test_invites_score_high():
    for subject, body in INVITES:
        sig = rule_signal(subject, body)
        assert sig.looks_like_invite, f"expected invite: {subject!r} (score {sig.score})"


def test_non_invites_score_low():
    for subject, body in NON_INVITES:
        sig = rule_signal(subject, body)
        assert not sig.looks_like_invite, (
            f"expected non-invite: {subject!r} (score {sig.score})"
        )


def test_time_hint_detected():
    sig = rule_signal("Meet", "Let's meet tomorrow at 3pm")
    assert sig.has_time_hint


if __name__ == "__main__":
    # Allow running directly without pytest.
    failures = 0
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"PASS  {name}")
            except AssertionError as exc:
                failures += 1
                print(f"FAIL  {name}: {exc}")
    print(f"\n{'All tests passed.' if not failures else f'{failures} failure(s).'}")
    raise SystemExit(1 if failures else 0)
