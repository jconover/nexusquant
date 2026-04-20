# PHASE_0 — Repo scaffold and contracts

**No business logic in this phase.** The deliverable is a repo where
`docker-compose up` starts empty services that respond to health checks,
every MCP tool has a JSON schema, the Postgres audit schema is defined,
and CI is green on an empty test suite. This is the boring phase. It is
the most important phase.

---

## Goals

1. Establish the monorepo layout exactly as described in `ARCHITECTURE.md`.
2. Define JSON schemas for every MCP tool request and response.
3. Define the Postgres/TimescaleDB schema for the audit log.
4. Create stub FastAPI services for `signal`, `risk`, `executor`,
   `watchlist`, `ingester`, `mcp`, `slack`. Each responds to `/healthz`
   and `/readyz` with 200. No other endpoints.
5. Provide a working `docker-compose.yaml` that brings up all stubs plus
   Postgres, Redis, and MinIO, locally on a dev machine.
6. GitHub Actions CI: lint (ruff), type-check (mypy), test (pytest),
   build container images. All jobs green on an empty placeholder test.
7. Root README explaining the repo and how to run locally.

## Non-goals (do not implement in this phase)

- Any Alpaca integration.
- Any real indicator computation.
- Any risk guard logic.
- Any MCP tool logic (stub the server; define the schemas; don't wire tools).
- Helm charts, OKD deployment manifests. Those are Phase 1+.
- Authentication on service-to-service calls. Phase 2.
- Any mention of Hermes. Phase 6.

If work that would belong to a later phase is identified, add it to
`TODO.md` under the appropriate phase heading. Do not write code for it.

---

## Acceptance criteria

A reviewer can:

1. Clone the repo.
2. Run `docker-compose up -d`.
3. Run `curl http://localhost:8001/healthz` through port 8007 and receive
   `{"status": "ok"}` from each stub service.
4. Run `docker-compose exec postgres psql -U nexusquant -c "\dt"` and see
   the audit tables.
5. Open `schemas/` and find a `.json` schema file for every MCP tool
   listed in ARCHITECTURE.md, each with `request` and `response` schemas
   that validate against example payloads in `schemas/examples/`.
6. Push a branch and see GitHub Actions run lint, type-check, test, and
   build steps to green.

---

## Deliverables checklist

### Repo structure

Create exactly the layout in `ARCHITECTURE.md` §Repo layout. Every service
directory contains at minimum:

```
services/<name>/
├── Dockerfile
├── pyproject.toml
├── README.md           # one-paragraph: what this service does
├── src/<name>/
│   ├── __init__.py
│   ├── main.py         # FastAPI app with /healthz, /readyz
│   └── config.py       # pydantic-settings, reads from env
└── tests/
    └── test_health.py  # asserts /healthz returns 200
```

### JSON schemas

In `schemas/`, one file per MCP tool:

- `get_market_status.json`
- `get_watchlist.json`
- `get_signal.json`
- `get_sentiment.json`
- `get_portfolio.json`
- `get_risk_budget.json`
- `place_paper_order.json`

Each schema file contains a `request` and a `response` JSON Schema
(draft 2020-12). For `place_paper_order.response`, the schema is a
`oneOf` of the three outcome shapes (`executed`, `pending_approval`,
`rejected`).

Provide `schemas/examples/<tool>.request.json` and
`schemas/examples/<tool>.response.json` for each. Include a test in
`tests/unit/test_schemas.py` that validates every example against its
schema.

### Postgres/TimescaleDB schema

In `infra/postgres/init/`, SQL migrations creating:

- `signals` (hypertable on `ts`): symbol, ts, indicator_json, rule_result
- `decisions`: proposal_id, ts, symbol, side, qty, notional, mode
  (auto/proposal), agent_reasoning_text
- `orders`: order_id, proposal_id (nullable), ts_submitted, ts_filled,
  symbol, side, qty, fill_price, status, idempotency_key (unique)
- `risk_events`: ts, kind (rejection/approval/circuit_breaker), reason,
  context_json
- `proposals`: proposal_id, ts_created, ts_decided, outcome
  (approved/rejected/expired), payload_json

No triggers, no views, no stored procedures. Just tables and indices.

### docker-compose.yaml

Services:

- 7 Python stubs (ports 8001–8007)
- `postgres` (timescaledb/timescaledb:latest-pg16), volume-mounted init SQL
- `redis` (redis:7-alpine)
- `minio` (minio/minio, console on 9001)

No bind mounts into service code (use image builds). Health checks on
postgres and redis. Stubs depend on postgres and redis being healthy.

### CI

`.github/workflows/ci.yaml` with a matrix job per service:

- `ruff check`
- `ruff format --check`
- `mypy src/`
- `pytest tests/`
- `docker build` (no push in this phase)

Plus a top-level job that validates every JSON schema example.

### Root README

Sections:

1. What NexusQuant is (link to ARCHITECTURE.md)
2. Local dev quickstart (`docker-compose up`, health-check commands)
3. Repo layout
4. Current phase (0) and link to docs/PHASE_0.md
5. A bold note: **NO REAL MONEY. PAPER TRADING ONLY.**

---

## Constraints for Claude Code

- Python 3.12. FastAPI. pydantic v2. pydantic-settings for config.
- No ORMs yet; raw SQL via `psycopg[binary]` is fine. SQLAlchemy can be
  added in a later phase if needed.
- Use `uv` for dependency management where reasonable, or plain pip with
  `pyproject.toml`. Consistent across all services.
- All services read config from environment variables only. No config
  files checked into the repo.
- No secrets anywhere in the repo, including in `docker-compose.yaml`.
  Use `.env.example` with placeholder values and a gitignored `.env`.
- Commit in logical units: scaffolding, schemas, audit DB, stubs, compose,
  CI. Not one monster commit.
- When in doubt about scope, check this document. If it's not here, it's
  not in this phase — put it in `TODO.md`.

## Definition of done

- `docker-compose up` brings everything green.
- All 7 health endpoints return 200.
- All schemas validate their examples.
- CI is green on `main`.
- README is accurate.
- `TODO.md` captures anything deferred.

When all of the above hold, open `docs/PHASE_1.md` and begin.
