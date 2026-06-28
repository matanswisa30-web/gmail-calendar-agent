# PRD — Gmail & Calendar Agent

**Product:** An AI agent that turns free-text meeting requests in Gmail into Google
Calendar events (or a polite decline).
**Course:** L08 — Bonus Assignment (Dr. Yoram Segal, 2026).
**Status:** v1.0.

---

## 1. Problem & motivation

People constantly receive meeting requests written in plain language — *"can we meet
Thursday at 3?"*, *"let's grab 30 minutes tomorrow morning"* — rather than as formal
calendar invites. Acting on each one means reading the mail, parsing the intent,
checking the calendar, and replying or booking. This is repetitive and easy to drop.

Classic Gmail filters cannot solve it: they match on sender or fixed keywords and miss
the *intent* expressed in natural language. The goal of this product is an agent that
understands intent and automates the whole loop.

## 2. Goal

Given a Gmail inbox, automatically:

1. Find recent emails that are **free-text meeting invitations**.
2. Understand **when / who / where**.
3. **Book** the meeting if the calendar is free, or **decline** by reply if it is busy.

### Non-goals (v1)

- Handling formal `Calendar Invite` / `.ics` attachments (those already create events).
- Multi-account or non-Google mail (Outlook, corporate, bank accounts). The OAuth method
  used here is for Google applications only.
- A long back-and-forth negotiation of times (single-shot decision per email).
- A graphical UI (this is a CLI agent).

## 3. Users

- The mailbox owner (a single Gmail account, ideally a dedicated one for the assignment).

## 4. User stories

- *As a mailbox owner,* when someone emails me a casual meeting request and I'm free,
  I want the agent to put it on my calendar so I don't forget.
- *As a mailbox owner,* when I'm busy at the requested time, I want the agent to reply
  that the meeting can't be held, so the sender knows.
- *As a mailbox owner,* I want the agent to ignore non-meeting emails (newsletters,
  invoices, threads) so it doesn't create junk events.
- *As a developer,* I want a dry-run mode so I can verify behaviour before it acts.

## 5. Functional requirements (the workflow)

The agent must perform these steps, mirroring the assignment specification:

| # | Step | Requirement |
|---|------|-------------|
| 1 | **Scan emails** | Read inbox messages from the **last 2 days only** (configurable), via a Gmail search query. |
| 2 | **Detect invitation** | Decide whether the email is a *free-text* meeting invitation (not a formal calendar invite). |
| 3 | **Extract details** | Produce date, start time, duration, participants and location using an LLM. |
| 4 | **Check availability** | Query Google Calendar free/busy for the proposed slot. |
| 5 | **If free → book** | Create a Google Calendar event for the slot. |
| 6 | **If busy → decline** | Send a reply email stating the meeting cannot be held. |

Supporting requirements:

- **Idempotency:** never act on the same message twice (label processed messages and
  exclude them on later runs).
- **Auth:** authenticate to Google with OAuth using a downloaded **Client**
  (`credentials.json`) and a generated **Token** (`token.json`); scopes
  `gmail.modify` + `calendar`.
- **Safety:** a `--dry-run` mode that analyses but performs no side effects.

## 6. Design decisions

These are the explicit "design choices" the assignment asks us to reason about.

### 6.1 Hybrid detection: rules **and** LLM (not rules alone)

Rigid keyword/sender rules recognise a free-text invitation correctly only ~40% of the
time, because intent lives in natural language. We therefore combine:

- **Rule layer (`classifier.py`)** — a fast, free pre-filter that scores an email on
  meeting keywords ("meet", "call", "available", times/dates, question marks, etc.) and
  surfaces a signal. It cheaply skips obvious non-invites and provides a hint.
- **LLM layer (`llm.py`)** — Claude makes the final intent decision *and* extracts the
  structured details in one structured-output call. This is where natural-language
  understanding happens.

The rule signal is passed to the LLM as a hint and is also used as a degraded fallback
when no API key is configured.

### 6.2 Distinguishing invite vs. non-invite

The system must not turn every email into an event. Both layers explicitly classify the
message first; only emails judged to be invitations (above a confidence threshold)
proceed to extraction and booking. Replies, receipts, newsletters and notifications are
skipped.

### 6.3 Boundary case — missing time

If an email expresses intent but lacks a concrete **date or start time**, we cannot
responsibly book it. **Decision:** date and start time are *mandatory* fields. When
either is missing, the agent does **not** create an event; in non-dry-run mode it may
optionally reply asking for a concrete time (configurable; default: skip and log). This
is a deliberate design choice to avoid wrong bookings.

### 6.4 Default duration

Casual invitations rarely state a duration. **Decision:** default to **60 minutes**
(configurable via `DEFAULT_DURATION_MINUTES`).

### 6.5 LLM choice

We use **Anthropic Claude (`claude-opus-4-8`)** via the official `anthropic` SDK, with
adaptive thinking and structured outputs (a JSON schema) so the model returns a
validated object — no brittle string parsing. The model and reasoning effort are
configurable via environment variables.

## 7. Success metrics / acceptance criteria

- Given a sample of mixed emails, the agent books exactly the free-text invitations that
  fall on free slots, declines those on busy slots, and skips non-invites.
- No event is ever created twice for the same email.
- Secrets (`credentials.json`, `token.json`, `.env`) are never committed.
- `--dry-run` produces the same analysis with zero side effects.

## 8. Risks & mitigations

| Risk | Mitigation |
|------|------------|
| LLM mis-classifies an email | Confidence threshold + rule signal; `--dry-run` for review. |
| Google changes console UI / setup drifts | Setup documented in README + Appendix A; token auto-refresh. |
| Accidental spam from auto-replies | `--no-reply` flag; replies only on confident busy-slot invites. |
| Leaked credentials | `.gitignore` covers all secret files; least-privilege scopes. |
| Wrong booking from vague time | Date+time mandatory (see §6.3). |

## 9. Out-of-scope future work

- Suggesting alternative free slots when busy.
- Threaded negotiation over multiple emails.
- Web/desktop UI and continuous (daemon) operation.
