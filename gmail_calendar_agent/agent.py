"""Agent orchestration — the six-step workflow from the assignment.

1. Scan recent emails        4. Check calendar availability
2. Detect a free-text invite 5. If free  -> create a calendar event
3. Extract the details       6. If busy  -> reply "cannot hold the meeting"
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from .calendar_client import CalendarClient
from .classifier import rule_signal
from .config import CONFIDENCE_THRESHOLD, Settings
from .gmail_client import Email, GmailClient
from .llm import AnthropicLLM, MeetingAnalysis, rules_only_analysis


@dataclass
class RunSummary:
    scanned: int = 0
    events_created: int = 0
    declines_sent: int = 0
    skipped: int = 0
    notes: list[str] = field(default_factory=list)

    def line(self) -> str:
        return (
            f"Done. {self.events_created} event(s) created, "
            f"{self.declines_sent} decline(s) sent, {self.skipped} skipped "
            f"(of {self.scanned} scanned)."
        )


@dataclass
class AgentOptions:
    dry_run: bool = False
    no_reply: bool = False
    reprocess: bool = False
    verbose: bool = False
    max_emails: int = 25


class Agent:
    def __init__(
        self,
        gmail: GmailClient,
        calendar: CalendarClient,
        settings: Settings,
        llm: AnthropicLLM | None = None,
        options: AgentOptions | None = None,
    ):
        self.gmail = gmail
        self.calendar = calendar
        self.settings = settings
        self.llm = llm
        self.opt = options or AgentOptions()

    # --- public API --------------------------------------------------------

    def run(self) -> RunSummary:
        summary = RunSummary()
        tz = ZoneInfo(self.settings.timezone)

        label_id = self.gmail.ensure_label()
        processed_filter = None if self.opt.reprocess else label_id

        print(
            f"Scanning inbox (newer_than:{self.settings.lookback}, "
            f"{'including processed' if self.opt.reprocess else 'excluding already-processed'}) ..."
        )
        ids = self.gmail.list_recent(
            lookback=self.settings.lookback,
            processed_label_id=processed_filter,
            max_results=self.opt.max_emails,
        )
        print(f"Found {len(ids)} candidate message(s).\n")

        for i, msg_id in enumerate(ids, start=1):
            email = self.gmail.get_message(msg_id)
            summary.scanned += 1
            self._handle_email(i, len(ids), email, tz, label_id, summary)

        print()
        print(summary.line())
        for note in summary.notes:
            print(f"  - {note}")
        return summary

    # --- per-email pipeline ------------------------------------------------

    def _handle_email(
        self, idx: int, total: int, email: Email, tz: ZoneInfo,
        label_id: str, summary: RunSummary,
    ) -> None:
        print(f'[{idx}/{total}] "{email.subject}"  from {email.sender_email}')

        analysis = self._analyze(email)
        if self.opt.verbose:
            print(f"      reasoning: {analysis.reasoning}")

        # Step 2: is this a meeting invitation we should act on?
        if not analysis.is_meeting_invite or analysis.confidence < CONFIDENCE_THRESHOLD:
            print(
                f"      -> not a meeting invitation "
                f"(confidence {analysis.confidence:.2f}) -> skipped"
            )
            summary.skipped += 1
            self._mark(email, label_id)
            return

        # Step 3 boundary case: a concrete date AND time are mandatory.
        if not analysis.has_concrete_time:
            print(
                "      -> meeting intent but no concrete date/time -> skipped "
                "(design decision: date+time are mandatory)"
            )
            summary.skipped += 1
            summary.notes.append(
                f'"{email.subject}": invite without a concrete time — not booked.'
            )
            self._mark(email, label_id)
            return

        start, end = self._to_datetimes(analysis, tz)
        if start is None:
            print("      -> could not parse the proposed time -> skipped")
            summary.skipped += 1
            self._mark(email, label_id)
            return

        when = f"{analysis.date} {analysis.start_time} ({analysis.duration_minutes or self.settings.default_duration_minutes} min)"
        loc = f', location: "{analysis.location}"' if analysis.location else ""
        print(
            f"      -> meeting invite (confidence {analysis.confidence:.2f})\n"
            f"      -> {when}{loc}, with: {email.sender_email}"
        )

        # Step 4: availability.
        free = self.calendar.is_free(start, end)

        if free:
            self._book(email, analysis, start, end, summary)
        else:
            self._decline(email, when, summary)

        self._mark(email, label_id)

    # --- steps 5 & 6 -------------------------------------------------------

    def _book(
        self, email: Email, analysis: MeetingAnalysis,
        start: datetime, end: datetime, summary: RunSummary,
    ) -> None:
        attendees = list(dict.fromkeys(analysis.participants + [email.sender_email]))
        title = analysis.title or f"Meeting with {email.sender_email}"
        description = (
            "Created automatically by the Gmail & Calendar Agent from the email:\n"
            f'"{email.subject}" (from {email.sender_email}).'
        )
        if self.opt.dry_run:
            print("      -> slot is FREE -> [dry-run] would create event")
            summary.events_created += 1
            return

        event_id, link = self.calendar.create_event(
            summary=title, start=start, end=end,
            description=description, location=analysis.location,
            attendees=attendees,
        )
        print(f"      -> slot is FREE -> event created: {link or event_id}")
        summary.events_created += 1

    def _decline(self, email: Email, when: str, summary: RunSummary) -> None:
        body = (
            f"Hi,\n\nThanks for the meeting request. Unfortunately the proposed "
            f"time ({when}) is not available on my calendar, so the meeting cannot "
            f"be held as suggested. Could we find another time?\n\n"
            f"(This reply was sent automatically by my scheduling agent.)"
        )
        if self.opt.dry_run or self.opt.no_reply:
            reason = "dry-run" if self.opt.dry_run else "--no-reply"
            print(f"      -> slot is BUSY -> [{reason}] would send a decline reply")
            summary.declines_sent += 1
            return

        self.gmail.send_reply(email, body)
        print("      -> slot is BUSY -> decline reply sent")
        summary.declines_sent += 1

    # --- helpers -----------------------------------------------------------

    def _analyze(self, email: Email) -> MeetingAnalysis:
        if self.llm is not None:
            now_iso = datetime.now(ZoneInfo(self.settings.timezone)).isoformat()
            return self.llm.analyze_email(
                subject=email.subject, sender=email.sender, body=email.body,
                now_iso=now_iso, timezone=self.settings.timezone,
                hint=rule_signal(email.subject, email.body),
            )
        return rules_only_analysis(email.subject, email.body)

    def _to_datetimes(
        self, analysis: MeetingAnalysis, tz: ZoneInfo,
    ) -> tuple[datetime | None, datetime | None]:
        try:
            start = datetime.strptime(
                f"{analysis.date} {analysis.start_time}", "%Y-%m-%d %H:%M"
            ).replace(tzinfo=tz)
        except ValueError:
            return None, None
        minutes = analysis.duration_minutes or self.settings.default_duration_minutes
        return start, start + timedelta(minutes=minutes)

    def _mark(self, email: Email, label_id: str) -> None:
        if not self.opt.dry_run:
            self.gmail.mark_processed(email.id, label_id)
