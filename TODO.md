# TODO — Gmail & Calendar Agent

Task checklist. `[x]` done · `[ ]` open. See [`PLAN.md`](PLAN.md) for milestone context.

## Setup & scaffolding
- [x] `pyproject.toml` with `uv` + dependencies (google-api-python-client, google-auth-oauthlib, google-auth-httplib2, anthropic, python-dotenv)
- [x] `.gitignore` covering `credentials.json`, `token.json`, `.env`, venv, caches
- [x] `.env.example` template
- [x] Package scaffolding (`gmail_calendar_agent/`)
- [x] `config.py` — settings from env / `.env`

## Authentication (Client + Token)
- [x] `auth.py` — `get_credentials()` (load/refresh/first-run flow → `token.json`)
- [x] `build_services()` — Gmail v1 + Calendar v3 service objects
- [x] Scopes: `gmail.modify`, `calendar`

## Step 1 — Scan emails
- [x] `gmail_client.list_recent()` with `newer_than` query
- [x] Exclude already-processed messages (label filter)
- [x] `get_message()` parsing subject / from / body (multipart + base64url)

## Step 2 — Detect invitation
- [x] `classifier.rule_signal()` — keyword/heuristic score (offline)
- [x] LLM intent decision in `llm.analyze_email()`
- [x] Combine rule signal + LLM; confidence threshold in `agent.py`

## Step 3 — Extract details
- [x] LLM structured output: date, time, duration, participants, location
- [x] Relative-date resolution (pass "today" + timezone to the model)
- [x] Boundary case: missing date/time → do not book (design decision)

## Step 4 — Check availability
- [x] `calendar_client.is_free()` via free/busy query
- [x] Timezone handling (`zoneinfo`)

## Step 5 — Book (if free)
- [x] `calendar_client.create_event()` with attendees + location
- [x] Return event id + link

## Step 6 — Decline (if busy)
- [x] `gmail_client.send_reply()` in-thread ("cannot hold the meeting")
- [x] `--no-reply` flag to suppress

## Idempotency & safety
- [x] `ensure_label()` + `mark_processed()` (`AI-Agent-Processed`)
- [x] `--dry-run` mode (analyse only, no side effects)
- [x] `--reprocess` to ignore processed filter

## Orchestration & CLI
- [x] `agent.run()` — the 6-step loop + per-email decisions
- [x] `main.py` — argparse flags, wiring, run summary
- [x] `--verbose` reasoning output

## Tests & docs
- [x] `tests/test_classifier.py` — offline rule-layer tests
- [x] `README.md`, `PRD.md`, `PLAN.md`, `TODO.md`

## Nice-to-have (future)
- [ ] Suggest alternative free slots when busy
- [ ] Multi-turn time negotiation
- [ ] Continuous/daemon mode or scheduled runs
- [ ] Richer end-to-end test fixtures with recorded API responses
