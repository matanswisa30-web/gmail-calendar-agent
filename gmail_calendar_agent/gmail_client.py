"""Thin wrapper over the Gmail API: read messages, send replies, manage labels."""

from __future__ import annotations

import base64
from dataclasses import dataclass, field
from email.message import EmailMessage

from .config import PROCESSED_LABEL


@dataclass
class Email:
    """A parsed Gmail message, reduced to what the agent needs."""

    id: str
    thread_id: str
    subject: str
    sender: str  # raw "From" header, e.g. 'Alice <alice@example.com>'
    to: str
    date: str
    body: str
    message_id_header: str = ""  # RFC822 Message-ID, for threading replies
    label_ids: list[str] = field(default_factory=list)

    @property
    def sender_email(self) -> str:
        """Bare email address parsed from the From header."""
        raw = self.sender
        if "<" in raw and ">" in raw:
            return raw[raw.index("<") + 1 : raw.index(">")].strip()
        return raw.strip()


class GmailClient:
    def __init__(self, service):
        self._svc = service

    # --- Reading -----------------------------------------------------------

    def list_recent(
        self, lookback: str = "2d", processed_label_id: str | None = None,
        max_results: int = 25,
    ) -> list[str]:
        """Return message IDs from the inbox within the look-back window.

        Already-processed messages (carrying the processed label) are excluded
        unless ``processed_label_id`` is None.
        """
        query = f"in:inbox newer_than:{lookback}"
        if processed_label_id:
            # Exclude messages we've already handled.
            query += f" -label:{PROCESSED_LABEL}"

        resp = (
            self._svc.users()
            .messages()
            .list(userId="me", q=query, maxResults=max_results)
            .execute()
        )
        return [m["id"] for m in resp.get("messages", [])]

    def get_message(self, message_id: str) -> Email:
        """Fetch and parse a single message."""
        msg = (
            self._svc.users()
            .messages()
            .get(userId="me", id=message_id, format="full")
            .execute()
        )
        payload = msg.get("payload", {})
        headers = {
            h["name"].lower(): h["value"] for h in payload.get("headers", [])
        }
        body = _extract_body(payload)
        return Email(
            id=msg["id"],
            thread_id=msg.get("threadId", ""),
            subject=headers.get("subject", "(no subject)"),
            sender=headers.get("from", ""),
            to=headers.get("to", ""),
            date=headers.get("date", ""),
            body=body,
            message_id_header=headers.get("message-id", ""),
            label_ids=msg.get("labelIds", []),
        )

    # --- Replying ----------------------------------------------------------

    def send_reply(self, original: Email, body_text: str) -> str:
        """Send a plain-text reply to ``original`` within the same thread."""
        msg = EmailMessage()
        msg["To"] = original.sender_email
        subject = original.subject
        if not subject.lower().startswith("re:"):
            subject = f"Re: {subject}"
        msg["Subject"] = subject
        if original.message_id_header:
            msg["In-Reply-To"] = original.message_id_header
            msg["References"] = original.message_id_header
        msg.set_content(body_text)

        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        sent = (
            self._svc.users()
            .messages()
            .send(
                userId="me",
                body={"raw": raw, "threadId": original.thread_id},
            )
            .execute()
        )
        return sent["id"]

    # --- Labels (idempotency) ---------------------------------------------

    def ensure_label(self, name: str = PROCESSED_LABEL) -> str:
        """Return the id of the label, creating it if necessary."""
        labels = (
            self._svc.users().labels().list(userId="me").execute().get("labels", [])
        )
        for lbl in labels:
            if lbl["name"] == name:
                return lbl["id"]
        created = (
            self._svc.users()
            .labels()
            .create(
                userId="me",
                body={
                    "name": name,
                    "labelListVisibility": "labelShow",
                    "messageListVisibility": "show",
                },
            )
            .execute()
        )
        return created["id"]

    def mark_processed(self, message_id: str, label_id: str) -> None:
        """Apply the processed label so the agent won't handle this twice."""
        self._svc.users().messages().modify(
            userId="me",
            id=message_id,
            body={"addLabelIds": [label_id]},
        ).execute()


def _extract_body(payload: dict) -> str:
    """Walk a Gmail payload tree and return the best plain-text body."""
    # Prefer text/plain; fall back to the first decodable part.
    plain = _find_part(payload, "text/plain")
    if plain:
        return plain
    html = _find_part(payload, "text/html")
    if html:
        return _strip_html(html)
    # Single-part message.
    data = payload.get("body", {}).get("data")
    return _decode(data) if data else ""


def _find_part(payload: dict, mime_type: str) -> str:
    if payload.get("mimeType") == mime_type:
        data = payload.get("body", {}).get("data")
        if data:
            return _decode(data)
    for part in payload.get("parts", []) or []:
        found = _find_part(part, mime_type)
        if found:
            return found
    return ""


def _decode(data: str) -> str:
    return base64.urlsafe_b64decode(data.encode("utf-8")).decode(
        "utf-8", errors="replace"
    )


def _strip_html(html: str) -> str:
    """Very small HTML-to-text fallback (no external dependency)."""
    import re

    text = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", html)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()
