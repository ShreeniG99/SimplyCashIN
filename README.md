# SimplyCashIN

[![CI](https://github.com/ShreeniG99/SimplyCashIN/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/ShreeniG99/SimplyCashIN/actions/workflows/ci.yml)

**Agentic receivables collection for Indian MSMEs.** An AI agent that chases overdue invoices over WhatsApp/SMS/email, negotiates payment plans inside owner-defined guardrails, and hands control to a human the moment judgment is required — live, over a WebSocket.

> 🎬 **2-minute demo video:** _coming soon — link will be added here_

India's ~63 million small businesses collect receivables the manual way: the owner personally calls and messages buyers, every week. SimplyCashIN gives the owner an agent that does the chasing — and knows what it must never do without a human.

---

## How it works

Every overdue invoice runs through one auditable decision loop:

```mermaid
flowchart LR
    A[Context\nbuyer history + memory] --> B[Cash calendar\nurgency score]
    B --> C[Conversation agent\nClaude drafts the message]
    C --> D{needs\nnegotiation?}
    D -- yes --> E[Negotiation agent\nClaude proposes terms]
    D -- no --> F
    E --> F[Policy engine\npure Python, deterministic]
    F -- ACT --> G[Channel dispatch\nWhatsApp / SMS / Email]
    F -- ESCALATE --> H[Human-in-the-loop\nlive over WebSocket]
    H -- approve / edit / override --> G
    G --> I[Memory\npgvector embeddings]
    I --> A
```

**Design decisions that matter:**

- **The ACT-vs-ESCALATE branch is never an LLM call.** The policy engine is pure, deterministic Python evaluating owner guardrails (max extension days, min upfront %, relationship tier) — every decision is auditable and reproducible.
- **The LLM sits behind a seam.** `AnthropicClient` (Claude) in production, a deterministic `StubLLM` everywhere else — the entire test suite runs offline, and SDK errors map to typed `LLMError`s that escalate instead of failing silently.
- **Detection and dispatch never overlap.** APScheduler *detects* overdue invoices daily and ranks them into a Redis urgency queue; a Celery worker *drains* the queue and dispatches, highest urgency first, with bounded retries. Exhausted retries escalate — nothing is silently dropped.
- **Escalations are realtime.** `WS /ws/escalations` pushes new escalations to the owner's screen instantly; approve/edit/override travels back over the same socket, and the agent **remembers the owner's edits** for next time.
- **Multi-tenant by construction.** With `SUPABASE_JWT_SECRET` set, every request is owner-scoped via JWT → Postgres row-level security + repository filters. Unset, a dev fallback keeps local runs friction-free.
- **Money is integer paise** end-to-end; `₹` formatting (Indian digit grouping) happens only at the API edge.

## What's built

| Milestone | Scope | Status |
|---|---|---|
| M1 | End-to-end decision loop: Context → Conversation → Negotiation → Orchestrator → dispatch → Memory, behind FastAPI + Postgres/pgvector | ✅ |
| M2 | CSV/WhatsApp invoice ingestion, Redis urgency queue, memory vectorization | ✅ |
| M3 | APScheduler detection + Celery dispatch, Twilio WhatsApp/SMS + SMTP email channels, inbound reply webhook | ✅ |
| M4 | Supabase JWT auth, multi-tenancy with Postgres RLS | ✅ |
| M5 | Realtime HITL WebSocket gateway, wired to the React escalation screen | ✅ |
| M6 | AI Finance Controller: multi-source reconciliation agent (bank ↔ ledger), measured match rate + honest exceptions | ✅ |

**Stack:** Python 3.12 · FastAPI · SQLAlchemy 2 (async) + asyncpg · Alembic · Postgres + pgvector · Redis · Celery · APScheduler · Anthropic SDK · Pydantic v2 · pytest — React 18 · Vite · Framer Motion on the front.

```
backend/
  app/agents/        Context, Conversation, Negotiation, Orchestrator
  app/services/      cash calendar (urgency), policy engine, memory
  app/llm/           LLM seam: AnthropicClient / StubLLM
  app/channels/      Twilio, SMTP, simulated — env-driven factory
  app/dispatch/      Celery worker (queue drain → agent cycle → send)
  app/api/           FastAPI routes, WS gateway, JWT deps
  tests/             91 tests; stub LLM, db-marked, integration-marked
frontend/            React dashboard, conversation, escalation screens
```

## Quickstart (Windows / PowerShell)

Prereqs: **Python 3.12+**, **Node 18+**, **Docker Desktop** running.

```powershell
git clone https://github.com/ShreeniG99/SimplyCashIN.git
cd SimplyCashIN\backend

# 1. Infrastructure (Postgres+pgvector, Redis)
docker compose up -d

# 2. Python env + deps
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"

# 3. Config — stub LLM needs no API key; set ANTHROPIC_API_KEY + USE_STUB_LLM=0 for real Claude
Copy-Item .env.example .env
# demo mode: run with the deterministic stub
$env:USE_STUB_LLM = "1"

# 4. Schema + demo data (Ramesh Iyer's auto-parts business, 5 buyers)
python -m alembic upgrade head
python scripts\seed_dev.py

# 5. API
python -m uvicorn app.api.app:app --port 8001
```

Second terminal — frontend:

```powershell
cd SimplyCashIN\frontend
npm install
npm run dev    # http://localhost:5173 (talks to the API on :8001)
```

Drive the decision loop:

```powershell
# rajan: ordinary overdue invoice → agent ACTs (drafts + sends a reminder)
Invoke-RestMethod -Method Post http://localhost:8001/buyers/rajan/run-cycle

# anand: proposed terms breach owner policy → agent ESCALATEs
Invoke-RestMethod -Method Post http://localhost:8001/buyers/anand/run-cycle
# → approve/edit it live on the Escalations screen (WebSocket, no refresh)

# ingest a whole invoice book, detect overdue, queue by urgency
curl.exe -F "file=@tests\fixtures\invoices.csv" http://localhost:8001/ingest/csv
Invoke-RestMethod -Method Post http://localhost:8001/schedule/trigger

# a buyer replies — lands in the conversation thread
curl.exe -X POST "http://localhost:8001/webhooks/twilio?buyer_id=anand" -d "Body=Will pay Friday"
```

Tests:

```powershell
cd backend
$env:USE_STUB_LLM = "1"
python -m pytest          # db tests auto-skip if Postgres is down
```

Operational detail — the scheduler/Celery split, channel credentials, auth setup, and the full demo script — lives in [backend/README.md](backend/README.md).

## AI Finance Controller (M6): reconciliation agent

A second, self-contained decision loop built on the same LLM seam and
"deterministic-first, LLM-only-where-it-must-reason" philosophy as the
collections agent above — closing a different finance-ops loop: matching a
bank statement against the internal ledger, at throughput, with a measured
accuracy and an honest list of what it couldn't resolve.

```mermaid
flowchart LR
    A[Synthetic batch\nbank + ledger] --> B[ReconciliationEngine\npure Python, tiered rules]
    B -- unique match --> F[MatchedPair]
    B -- >1 candidate --> C[ReconciliationAgent\nClaude adjudicates]
    C -- confident --> F
    C -- declines / unsure --> E[Exception\ntyped reason, never dropped]
    B -- zero candidates --> E
    F --> G[ReconciliationReport\nmatch rate + throughput + exceptions]
    E --> G
```

- **Rules first, LLM only for genuine ambiguity.** `ReconciliationEngine`
  (`backend/app/services/reconciliation.py`) runs four tiers — exact
  reference, exact amount+date, amount+date window, then fuzzy
  (amount tolerance + date window + counterparty-or-description match) —
  and only ever claims a match when exactly one candidate qualifies at a
  tier. A bank record with more than one plausible ledger candidate is
  never guessed at; it's handed to `ReconciliationAgent`
  (`backend/app/agents/reconciliation.py`), which sits behind the same
  `LLM` seam as the rest of the app (`StubLLM` offline, `AnthropicClient`
  in prod) and is instructed to return "no match" rather than force one.
- **Every unresolved record is a typed exception, never a silent drop.**
  `ReconciliationController` accounts for every input record: matched, or
  an exception with one of `no_candidate`, `ambiguous_candidates`,
  `agent_rejected`, `agent_uncertain` — `test_reconciliation_e2e.py`
  asserts the report is exhaustive.
- **Measured, not cherry-picked.** `scripts/run_reconciliation.py` runs a
  seeded 40-transaction synthetic batch (`app/data/synthetic_reconciliation.py`,
  ~80 combined bank+ledger records covering clean matches, settlement lag,
  rounding drift, orphans on both sides, and genuinely ambiguous
  duplicate-invoice pairs) and prints throughput, match rate on both sides,
  and the full exception list — deterministic given `--seed`, so the numbers
  reproduce:

  ```powershell
  cd backend
  $env:USE_STUB_LLM = "1"       # or set ANTHROPIC_API_KEY and USE_STUB_LLM=0 for live adjudication
  python scripts\run_reconciliation.py
  ```

  A representative offline run (`--seed 42`, rules only — `StubLLM`
  declining every ambiguous case so nothing is guessed): **81 combined
  records (37 bank + 44 ledger), 78.4% of bank records / 65.9% of ledger
  records matched, tens of thousands of records/sec** on the deterministic
  tiers, with every remaining record listed as a typed exception. Pointing
  it at a real `ANTHROPIC_API_KEY` resolves a further slice of the
  ambiguous cases and raises the match rate — see
  `tests/test_reconciliation_e2e.py::test_agent_adjudication_resolves_some_ambiguous_cases_and_raises_match_rate`.
