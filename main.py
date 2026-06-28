"""CLI entry point for the Gmail & Calendar Agent.

Usage:
    uv run main.py [--dry-run] [--lookback 2d] [--max-emails 20]
                   [--no-reply] [--reprocess] [--verbose]
"""

from __future__ import annotations

import argparse
import sys

from gmail_calendar_agent.agent import Agent, AgentOptions
from gmail_calendar_agent.auth import build_services
from gmail_calendar_agent.calendar_client import CalendarClient
from gmail_calendar_agent.config import Settings
from gmail_calendar_agent.gmail_client import GmailClient
from gmail_calendar_agent.llm import AnthropicLLM


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="gmail-calendar-agent",
        description="Scan Gmail for free-text meeting invitations and book them "
        "on Google Calendar when the slot is free.",
    )
    p.add_argument("--dry-run", action="store_true",
                   help="Analyse only; never create events or send replies.")
    p.add_argument("--lookback", default=None,
                   help="Inbox look-back window in Gmail syntax (default from env, e.g. 2d).")
    p.add_argument("--max-emails", type=int, default=25,
                   help="Maximum number of messages to inspect this run.")
    p.add_argument("--no-reply", action="store_true",
                   help="Do not send decline replies on busy slots.")
    p.add_argument("--reprocess", action="store_true",
                   help="Ignore the processed-label filter and re-scan everything.")
    p.add_argument("--verbose", action="store_true",
                   help="Print per-email reasoning.")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    settings = Settings.load()
    if args.lookback:
        settings.lookback = args.lookback

    # Authenticate and build Google services (runs OAuth on first use).
    try:
        gmail_service, calendar_service = build_services(settings)
    except FileNotFoundError as exc:
        print(f"Authentication error: {exc}", file=sys.stderr)
        return 2

    gmail = GmailClient(gmail_service)
    calendar = CalendarClient(calendar_service, timezone=settings.timezone)

    # The LLM is optional: without a key the agent runs in reduced rules-only mode.
    llm: AnthropicLLM | None = None
    if settings.llm_enabled:
        llm = AnthropicLLM(
            api_key=settings.anthropic_api_key,
            model=settings.anthropic_model,
            effort=settings.anthropic_effort,
        )
    else:
        print(
            "WARNING: ANTHROPIC_API_KEY not set — running in rules-only mode. "
            "Detection is weaker and emails without an explicit time won't be booked.\n"
        )

    options = AgentOptions(
        dry_run=args.dry_run,
        no_reply=args.no_reply,
        reprocess=args.reprocess,
        verbose=args.verbose,
        max_emails=args.max_emails,
    )

    agent = Agent(gmail, calendar, settings, llm=llm, options=options)
    agent.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
