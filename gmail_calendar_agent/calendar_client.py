"""Thin wrapper over the Google Calendar API: free/busy check + event creation."""

from __future__ import annotations

from datetime import datetime


class CalendarClient:
    def __init__(self, service, timezone: str = "Asia/Jerusalem"):
        self._svc = service
        self.timezone = timezone

    def is_free(self, start: datetime, end: datetime) -> bool:
        """Return True if the primary calendar has no busy block in [start, end)."""
        body = {
            "timeMin": start.isoformat(),
            "timeMax": end.isoformat(),
            "timeZone": self.timezone,
            "items": [{"id": "primary"}],
        }
        resp = self._svc.freebusy().query(body=body).execute()
        busy = resp["calendars"]["primary"].get("busy", [])
        return len(busy) == 0

    def create_event(
        self,
        summary: str,
        start: datetime,
        end: datetime,
        description: str = "",
        location: str = "",
        attendees: list[str] | None = None,
    ) -> tuple[str, str]:
        """Create an event and return (event_id, html_link)."""
        event: dict = {
            "summary": summary or "Meeting",
            "description": description,
            "start": {"dateTime": start.isoformat(), "timeZone": self.timezone},
            "end": {"dateTime": end.isoformat(), "timeZone": self.timezone},
        }
        if location:
            event["location"] = location
        if attendees:
            event["attendees"] = [{"email": a} for a in attendees if a]

        created = (
            self._svc.events()
            .insert(calendarId="primary", body=event)
            .execute()
        )
        return created["id"], created.get("htmlLink", "")
