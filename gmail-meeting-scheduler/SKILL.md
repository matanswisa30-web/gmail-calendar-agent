---
name: gmail-meeting-scheduler
description: >-
  Reads recent Gmail messages, recognises free-text meeting invitations (not
  formal Calendar/.ics invites), extracts the date, time, duration, participants
  and location with an LLM, checks Google Calendar availability, and then either
  books the meeting or replies that it cannot be held. Use when the user wants to
  triage their inbox for meeting requests and auto-schedule them, e.g. "scan my
  email and book any meetings", "did anyone ask to meet this week?", or "check my
  inbox and decline what I can't make".
---

# Gmail Meeting Scheduler

A Skill that turns free-text meeting requests sitting in a Gmail inbox into
Google Calendar events — or polite declines when the slot is busy. It pairs a
fast rule-based pre-filter with an LLM that makes the final intent decision and
extracts the structured details.

## When to use this Skill

Use it whenever the goal is to **act on meeting invitations that arrived as plain
email text** rather than as a formal `Calendar Invite` / `.ics` attachment.
Typical triggers:

- "Scan my inbox and schedule any meetings people asked for."
- "Did anyone request a meeting in the last couple of days?"
- "Book the ones I'm free for and decline the rest."

Do **not** use it for formal calendar invitations (those are handled natively by
Google Calendar) or for non-Google mailboxes (Outlook, etc.) — the OAuth flow in
this project supports Google accounts only.

## The workflow (6 steps)

1. **Scan emails** — read inbox messages from the last *2 days only* (configurable).
2. **Detect a meeting invitation** — identify a *free-text* invite using a hybrid
   of keyword rules + an LLM (rules alone catch only ~40% of natural-language intent).
3. **Extract the details** — date, time, duration, participants and location, via the LLM.
4. **Check calendar availability** — query Google Calendar free/busy for that slot.
5. **If free** — create a matching event on Google Calendar.
6. **If busy** — send a reply email: *"the meeting cannot be held."*

Each processed message is tagged with the Gmail label `AI-Agent-Processed` so the
same email is never acted on twice.

## How to run

Prerequisites (see the project [`README.md`](../README.md) for the full setup):

- Python 3.10+ and [`uv`](https://docs.astral.sh/uv/).
- Google OAuth `credentials.json` in the project root (Gmail API + Calendar API
  enabled, the account added as a Test user). A `token.json` is created on first run.
- An `ANTHROPIC_API_KEY` set in `.env`.

```bash
uv sync                      # install dependencies

uv run main.py --dry-run     # analyse only — never creates events or sends mail
uv run main.py               # real run
```

Useful flags: `--dry-run`, `--lookback 2d`, `--max-emails 20`, `--no-reply`,
`--reprocess`, `--verbose`.

**Always run `--dry-run` first** to review the agent's decisions before letting it
write to the calendar or send replies.

## How it is built (project map)

The Skill is backed by the `gmail_calendar_agent` Python package:

| Module | Responsibility |
|--------|----------------|
| `config.py` | settings loaded from env / `.env` |
| `auth.py` | Google OAuth (`credentials.json` → `token.json`) |
| `gmail_client.py` | read messages, send replies, manage labels |
| `calendar_client.py` | free/busy check + event creation |
| `classifier.py` | rule-based pre-filter (keywords / heuristics) |
| `llm.py` | Anthropic Claude: intent decision + detail extraction |
| `agent.py` | orchestrates the 6-step workflow |

## Safety notes

- `credentials.json`, `token.json` and `.env` hold mailbox/calendar access and an
  API key — they are git-ignored and must never be committed.
- The OAuth token is scoped (`gmail.modify`, `calendar`); the agent never sees the
  Google password.
- Prefer `--dry-run` until you trust the output on your own inbox.
