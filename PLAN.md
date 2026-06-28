# PLAN — Gmail & Calendar Agent

Implementation plan for the product described in [`PRD.md`](PRD.md). This is the "how":
architecture, module responsibilities, milestones, and the testing approach.

---

## 1. Architecture overview

```
                 +-------------------+
                 |     main.py       |  CLI: flags, wiring, summary
                 +---------+---------+
                           |
                           v
                 +-------------------+
                 |  agent.py         |  Orchestrates the 6-step workflow
                 +--+-----+-----+----+
                    |     |     |
        +-----------+     |     +------------------+
        v                 v                        v
+---------------+  +---------------+        +----------------+
| gmail_client  |  | classifier    |        | calendar_client|
| (read/reply/  |  | (rule signal) |        | (free/busy +   |
|  labels)      |  +-------+-------+        |  create event) |
+-------+-------+          |                +----------------+
        |                  v
        |          +---------------+
        |          |    llm.py     |  Claude: intent + extraction
        |          +---------------+
        v
+---------------+
|   auth.py     |  OAuth: credentials.json -> token.json
+---------------+
        ^
        |
+---------------+
|  config.py    |  Settings from env / .env
+---------------+
```

Data flows top-down: `agent` pulls candidate emails from `gmail_client`, runs each
through `classifier` (rules) + `llm` (intent & extraction), checks the slot via
`calendar_client`, and then books or declines.

## 2. Module responsibilities

| Module | Responsibility | Key functions |
|--------|----------------|---------------|
| `config.py` | Load settings from environment / `.env`; hold constants (scopes, file paths, defaults); persist `USER_EMAIL` back to `.env`. | `Settings.load()`, `save_user_email()` |
| `auth.py` | Google OAuth: load/refresh token, run the installed-app flow (with `login_hint`) on first use, build API services, verify the signed-in account. | `get_credentials()`, `build_services()`, `_verify_account()` |
| `gmail_client.py` | List recent messages, fetch + parse a message (subject/from/body), send a reply in-thread, ensure/apply a label. | `list_recent`, `get_message`, `send_reply`, `ensure_label`, `mark_processed` |
| `calendar_client.py` | Free/busy check for a slot; create an event; resolve timezone. | `is_free`, `create_event` |
| `classifier.py` | Rule-based pre-filter: score an email for meeting intent; offline, no network. | `rule_signal` |
| `llm.py` | Anthropic Claude wrapper: one structured-output call returning intent + extracted fields. Degrades to rules-only if no key. | `analyze_email` |
| `agent.py` | Glue: implement the 6 steps, decide book vs decline vs skip, produce a run summary. | `run` |
| `main.py` | CLI parsing, prompt once for `USER_EMAIL` (saved to `.env`), build dependencies, call `agent.run`, print summary. | `main` |

The repository also ships a Claude **Skill** (`gmail-meeting-scheduler/SKILL.md`) that
documents when and how to invoke this agent.

## 3. Data model

A single dataclass carries the analysis of one email (`llm.MeetingAnalysis`):

```python
is_meeting_invite: bool
confidence: float            # 0..1
reasoning: str
title: str
date: str                    # "YYYY-MM-DD" or "" if unknown
start_time: str              # "HH:MM" (24h) or "" if unknown
duration_minutes: int        # defaults applied downstream
participants: list[str]
location: str
```

`agent.py` converts `date`+`start_time`+`duration_minutes` into timezone-aware
`datetime` objects for the calendar layer.

## 4. External interfaces

- **Google OAuth** — installed-app flow (`InstalledAppFlow.run_local_server`) with
  `login_hint=USER_EMAIL` to pre-select the account. Scopes: `gmail.modify`, `calendar`.
  Files: `credentials.json` (Client), `token.json` (Token).
- **Gmail API v1** — `users().messages().list/get`, `...drafts()/messages().send`,
  `...labels()`, `users().getProfile` (account verification).
- **Calendar API v3** — `freebusy().query`, `events().insert`.
- **Anthropic Messages API** — `claude-opus-4-8`, structured outputs via
  `output_config.format` (JSON schema), adaptive thinking.

## 5. Milestones

1. **M1 — Skeleton & config.** `pyproject.toml`, `.gitignore`, `.env.example`, package
   scaffolding, `config.py`. *(done)*
2. **M2 — Auth.** `auth.py` based on the assignment's reference flow; build Gmail +
   Calendar services; first-run consent → `token.json`. *(done)*
3. **M3 — Gmail read.** List recent messages (`newer_than:2d`), parse subject/from/body
   (handle multipart + base64url). *(done)*
4. **M4 — Detection + extraction.** `classifier.py` rule signal; `llm.py` structured
   analysis; combine. *(done)*
5. **M5 — Calendar.** `calendar_client.py` free/busy + event creation. *(done)*
6. **M6 — Reply + idempotency.** Send decline reply in-thread; processed label. *(done)*
7. **M7 — Orchestration + CLI.** `agent.py`, `main.py`, flags, dry-run, summary. *(done)*
8. **M8 — Tests + docs.** Offline classifier tests; README/PRD/PLAN/TODO. *(done)*

## 6. Testing strategy

- **Offline unit tests** (`tests/test_classifier.py`): feed sample emails (invitations
  and non-invitations) through the rule layer and assert the signal direction. No
  network or credentials required — runnable in CI.
- **Manual end-to-end** (per assignment Appendix A): send yourself a couple of test
  emails (one for a free slot, one for a busy slot), run `--dry-run`, then a real run,
  and confirm an event is created / a decline is sent.
- **LLM behaviour**: validated indirectly — the structured-output schema guarantees a
  well-formed object; the agent applies a confidence threshold before acting.

## 7. Configuration & defaults

| Setting | Env var | Default |
|---------|---------|---------|
| Anthropic key | `ANTHROPIC_API_KEY` | — (required for LLM mode) |
| Model | `ANTHROPIC_MODEL` | `claude-opus-4-8` |
| Effort | `ANTHROPIC_EFFORT` | `low` |
| Look-back | `LOOKBACK` | `2d` |
| Default duration | `DEFAULT_DURATION_MINUTES` | `60` |
| Timezone | `TIMEZONE` | `Asia/Jerusalem` |
| Client file | `CREDENTIALS_FILE` | `credentials.json` |
| Token file | `TOKEN_FILE` | `token.json` |
| User account | `USER_EMAIL` | — (prompted on first run, saved to `.env`) |

## 8. Operational notes

- Token auto-refreshes; delete `token.json` to force re-consent (e.g. after changing
  scopes).
- The processed label (`AI-Agent-Processed`) is created on first run.
- Confidence threshold for acting is `0.6` (constant in `agent.py`); tune as needed.
