# SimplyCashIN backend

    python -m venv .venv && . .venv/Scripts/activate   # Windows
    pip install -e ".[dev]"
    docker compose up -d
    createdb / auto: tests create scin_test schema
    cp .env.example .env   # set ANTHROPIC_API_KEY
    uvicorn app.api.app:app --reload

Run tests: `USE_STUB_LLM=1 python -m pytest`

## Scheduling vs dispatch (M3 decision)

Responsibilities are split so the same job never runs in two places:

- **APScheduler DETECTS** — `DailyOverdueTrigger` (in the API process, opt-in via
  `ENABLE_SCHEDULER=1`) finds overdue invoices once a day and pushes them into
  the Redis urgency sorted-set. It never sends anything.
- **Celery DISPATCHES** — the worker drains that queue (`scin.drain_queue` →
  one `scin.dispatch_cycle` per buyer, highest urgency first), runs the agent
  cycle, and sends via the channel factory. There is no Celery beat schedule.

The hand-off is a single `drain_queue.delay(owner_id)` at the end of a trigger
run, gated by `ENABLE_CELERY_DISPATCH=1`. Defaults (both flags `0`) keep the
API serverless-safe and let the demo drive each step manually via
`POST /schedule/trigger` and the worker.

Run the worker (needs Redis):

    celery -A app.dispatch.celery_app:celery worker --pool=solo -l info

Transient send failures retry inside the task (max 3, exponential backoff);
exhaustion records an escalation — nothing is silently dropped.

## Channels (M3)

`app/channels/factory.py` picks the transport from env; **with no credentials
set, every send goes through `SimulatedChannel`** — tests and the demo need no
external accounts.

- Twilio WhatsApp/SMS: `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`,
  `TWILIO_WHATSAPP_FROM`, `TWILIO_SMS_FROM`, and `TWILIO_TO_MAP`
  (JSON `{"buyer_id": "+91..."}` — a dev bridge until buyer contact columns land).
- Email: `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`,
  `EMAIL_TO_MAP`.
- Inbound replies: `POST /webhooks/twilio?buyer_id=<id>` appends a buyer turn.
  Signature validation is stubbed behind `TWILIO_VALIDATE_SIGNATURE=1`.

## Realtime HITL (M5)

`WS /ws/escalations` pushes new escalations live (owner-scoped; JWT rides
`?token=` when auth is enabled) and accepts
`{"action": "approve|edit|override", "escalation_id": "...", "text": "..."}`
— the same resolve logic as `POST /escalations/{id}/resolve`; approve/edit
dispatches and records memory. The React app resolves over the socket when
connected and falls back to REST.

## Demo script (end-to-end)

    # 0. stack + data
    docker compose up -d
    USE_STUB_LLM=1 .venv/Scripts/python scripts/seed_dev.py
    # 1. API (terminal A) and frontend (terminal B)
    .venv/Scripts/python -m uvicorn app.api.app:app --port 8123
    cd ../frontend && npm install && VITE_API_BASE=http://localhost:8123 npm run dev
    # 2. decision loop: rajan ACTs (plain reminder), anand ESCALATEs (policy breach)
    curl -X POST http://localhost:8123/buyers/rajan/run-cycle
    curl -X POST http://localhost:8123/buyers/anand/run-cycle
    # 3. approve anand's escalation in the UI (Escalation screen) — resolution
    #    travels over WS /ws/escalations; watch the ack + fan-out live
    # 4. ingest more invoices, detect overdue, drain via Celery
    curl -F "file=@tests/fixtures/invoices.csv" http://localhost:8123/ingest/csv
    curl -X POST http://localhost:8123/schedule/trigger
    celery -A app.dispatch.celery_app:celery worker --pool=solo -l info   # terminal C
    .venv/Scripts/python -c "from app.dispatch.tasks import drain_queue; print(drain_queue.delay('ramesh').id)"
    # 5. inbound buyer reply lands in the thread
    curl -X POST "http://localhost:8123/webhooks/twilio?buyer_id=anand" -d "Body=Will pay Friday"

## AI Finance Controller / reconciliation (M6)

A second, independent decision loop — no Postgres, Redis, or channels
needed, just the `LLM` seam:

    USE_STUB_LLM=1 python scripts/run_reconciliation.py            # rules-only, offline
    ANTHROPIC_API_KEY=... USE_STUB_LLM=0 python scripts/run_reconciliation.py  # live adjudication
    python scripts/run_reconciliation.py --seed 7 --n 60 --out reports/run7.json

`ReconciliationEngine` (deterministic, tiered) does as much as rules safely
can; `ReconciliationAgent` (LLM-backed) adjudicates only the bank records
with more than one plausible ledger candidate, and declines rather than
guesses when it isn't confident. `ReconciliationController` wires the two
together and produces a `ReconciliationReport` that accounts for every
input record — matched, or a typed exception
(`no_candidate` / `ambiguous_candidates` / `agent_rejected` /
`agent_uncertain`). The synthetic batch
(`app/data/synthetic_reconciliation.py`) is seeded, so a given `--seed`
always reproduces the same records and the same match rate.

Tests: `pytest tests/test_reconciliation_engine.py tests/test_reconciliation_agent.py
tests/test_reconciliation_e2e.py` — engine tiers in isolation, the agent's
accept/reject/low-confidence/error paths via `StubLLM`, and an end-to-end
run over the full batch asserting the report is reproducible and exhaustive
(every unmatched record shows up as an exception, never silently dropped).

## Auth & multi-tenancy (M4)

`SUPABASE_JWT_SECRET` set → every request must carry a Supabase-issued HS256
JWT (`Authorization: Bearer <token>`); the `sub` claim is the owner id and all
data, queue, and vector access is scoped to it (Postgres RLS policies +
repo-level filters). Unset → dev fallback: everything resolves to owner
`ramesh`, so M1–M3 flows and tests run unchanged.
