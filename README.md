# Inbox-to-Actions: AI Email-to-CRM Automation with Human Review

## Problem

Inbound business email is where deals start and where they get lost: leads, signed
agreements and status updates all land in the same inbox and someone has to re-type
them into the CRM. That manual step is slow, error-prone, and silently drops the
messages nobody got to. This project turns that inbox into validated, auditable CRM
records automatically — and routes anything uncertain to a human instead of guessing.

## What it does

- Ingests `.eml` / `.txt` emails from a drop folder (30-second timer or `POST /ingest/run`) and extracts text from attached PDF agreements with pypdf
- Classifies every email (lead / document / status_update / other) and extracts a typed, schema-validated record via a Gemini → Groq free-tier fallback chain
- Runs deterministic guardrails (email/phone format, date order, amount bounds, contact conflicts, confidence threshold) before anything touches the CRM
- Writes contacts, deals and activities idempotently — reprocessing an email or double-clicking Approve can never write twice
- Puts every uncertain item in a human review queue with editable fields and Approve / Reject
- Records one audit row per pipeline stage, visible per email in the UI
- [▶ Watch the 25-second demo video](docs/inbox-to-actions-demo.mp4) · try it yourself: (live demo coming soon)

**Inbox** — 12 sample emails triaged with category, confidence and outcome:

![Inbox panel with 12 triaged emails](docs/screenshots/01-inbox-panel-12-emails.png)

**Guardrail in action** — an agreement whose closing date precedes its acceptance
date is stopped with reason `date_order` instead of being written:

![Bad-dates document flagged for review](docs/screenshots/02-bad-dates-document-review-reason.png)

**Human review queue** — editable extracted fields with Approve / Reject:

![Review queue with three pending items](docs/screenshots/03-review-queue-3-pending.png)

**Audit trail** — one row per stage (ingest → classify → extract → validate → act),
with prompt version and the provider that answered:

![Email detail with full audit trail](docs/screenshots/11-email-detail-audit-trail.png)

**CRM deals** — upserted by reference with amounts and key dates:

![CRM deals tab](docs/screenshots/09-crm-deals-references-amounts.png)

## Architecture

```mermaid
flowchart LR
  UI["static UI\nInbox / Review / CRM"] --> API["FastAPI\n(aiforge_core.create_app)"]
  API --> W["worker pipeline\ningest -> classify -> extract\n-> validate -> act"]
  W --> R["aiforge_core Router\nversioned prompts, JSON schema"]
  R --> G["Gemini 2.5 Flash\n(primary, free tier)"]
  R --> Q["Groq llama-3.3-70b\n(fallback, free tier)"]
  W --> DB[("PostgreSQL\nemails, attachments, extractions,\nreview_queue, contacts, deals,\nactivities + audit_log, processed_keys")]
  API --> DB
```

Every model call goes through `Router.generate_json` with a Pydantic schema — invalid
output raises `ValidationFailed` and lands in the review queue, never in the CRM.

## Guardrails

Plain deterministic checks in `app/validate.py`, no model involved:

- Email addresses must look like email addresses; phone numbers must have 7–15 digits
- Agreement dates must parse and be in order: acceptance ≤ earnest money ≤ due diligence ≤ closing (`date_order` reason)
- Amounts must be positive and below 100,000,000
- A known contact name arriving with a different email address is flagged as a conflict, not silently overwritten
- Classifier confidence below 0.8 always goes to a human
- Broken or non-conforming model JSON goes to review with reason `validation`; nothing partial is ever written
- Every CRM write is wrapped in `idempotency.once(key(message_id, action))`; every stage writes an `audit_log` row

## Limits

Deliberately out of scope, to keep the demo honest and small:

- No live mailbox integration (IMAP/Gmail API) — emails arrive as files in a drop folder
- No OCR: scanned/image-only PDFs extract as empty text and end up in review
- Single-tenant, no auth — it is a portfolio demo behind a rate limit, not a SaaS
- The CRM is three tables, not Salesforce; the point is the pipeline, not the CRM
- Only Gemini and Groq free tiers are wired; no other providers or frameworks

## Run

```bash
git clone https://github.com/AbuBaker91-hub/inbox-to-actions
cd inbox-to-actions
cp .env.example .env        # add GEMINI_API_KEY, or use mock mode below
make setup                  # venv + deps + dockerised postgres + migrations
make demo                   # app at http://localhost:8000
curl -X POST localhost:8000/ingest/run   # -> {"processed": 12}
```

**Zero-key offline demo:** set `LLM_PROVIDER_ORDER=mock` in `.env` and the Router is
built with a MockProvider preloaded from `tests/canned.py`, so the 12 sample emails
process end-to-end with no API keys and no network.

New files dropped into `inbox/` are picked up by the 30-second background timer
(`INGEST_INTERVAL_S`). Or run everything in Docker: `docker compose up --build`
(first boot runs migrations and seeds the samples idempotently).

### Deploy

1. Neon: create a free project, enable the `vector` extension, copy `DATABASE_URL`.
2. Render: new Web Service from this repo, Docker runtime, add the env vars, health check `/health`.
3. First boot runs migrations and seeds samples automatically (idempotent).
4. Confirm `https://<app>.onrender.com/health` returns `{"ok": true}`.
5. Rate limit stays on. Free Gemini quota is enough for demo traffic.

**Or serverless on Vercel** (keyless demo): `vercel.json` + `api/index.py` are
included. Set env vars `DATABASE_URL` (Neon pooled URL) and
`LLM_PROVIDER_ORDER=mock`; cold starts apply migrations idempotently and the
background timer is disabled (the UI's "Run ingest" button still works). Seed
the demo database once from any machine:

```bash
DATABASE_URL=<neon-url> LLM_PROVIDER_ORDER=mock python -m app.bootstrap
```

## Tests

```bash
make test   # no keys, no network; needs the test postgres (docker) reachable
```

| Test | Proves |
|---|---|
| `test_idempotency` | the same email processed twice yields exactly one contact, one deal, one activity |
| `test_extract_invalid` | broken model JSON goes to review (`validation`), CRM untouched |
| `test_dates` | closing before acceptance goes to review (`date_order`), no deal written |
| `test_confidence` | confidence 0.6 → review, 0.9 → written |
| `test_fallback` | provider 1 timeout → provider 2 answers, audit row names the provider used |
| `test_review_approve` | approve writes the edited payload once; a second approve returns 200 and writes nothing |

All tests use `MockProvider` and a fresh throwaway database per test
(`TEST_DATABASE_URL`, default `postgresql://postgres:postgres@localhost:5433/postgres`).

## Keywords

AI email automation, email to CRM, PDF data extraction, document AI, structured
outputs, human in the loop, idempotent processing, audit trail, CRM integration,
FastAPI, PostgreSQL, Gemini API.
