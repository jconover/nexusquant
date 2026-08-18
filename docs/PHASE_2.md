# PHASE_2 — Risk service, executor service, in-cluster Postgres

This is the phase where policy becomes code. The risk service enforces
every guard listed in `ARCHITECTURE.md`; the executor is the one and
only place `submit_order` gets called; in-cluster Postgres finally
exists so audit writes stop silently failing.

**Do not underscope this phase.** Risk is the layer between an LLM and
real order placement. Everything after Phase 2 — MCP surface, Hermes
integration, Slack approval flow — trusts that this phase got the
guards right. Ship with the scope intact or split the phase; do not
ship with half the guards.

**Required reading before writing any code:**

1. `CLAUDE.md` — operating rules.
2. `ARCHITECTURE.md` — unchanged target system. §Hybrid autonomy
   thresholds and §Risk guards are the binding policy this phase
   implements.
3. `docs/PHASE_0.md`, `docs/PHASE_1.md`, `docs/PHASE_1_RETRO.md` —
   for pattern continuity.
4. `TODO.md` — Phase 2 section in particular.
5. `~/.claude/skills/alpaca-paper/SKILL.md` — **especially** the
   `feed=DataFeed.IEX` requirement and the pytz dependency note
   added after Phase 1 (see §Pre-phase drift corrections below).

---

## Pre-phase drift corrections

Based on the Phase 1 retro. Land these as **small, single-purpose
commits on a pre-phase branch before the main Phase 2 work** so the
phase builds on a clean base:

1. **`alpaca-paper/SKILL.md`** — add four items:
   - **Hard requirement:** every `StockBarsRequest` /
     `StockLatestBarRequest` must pass `feed=DataFeed.IEX` explicitly.
     The SDK default is SIP; free-tier paper accounts reject SIP data
     with `"subscription does not permit querying recent SIP data"`.
     Unit tests with stubbed BarSets do not catch this. List under
     "Anti-patterns to refuse."
   - **pytz is a transitive runtime dep** of `alpaca-py` but not in
     its declared deps. Every service that imports from `alpaca.data`
     must list `pytz` directly in its `pyproject.toml`.
   - **`TimeFrame` equality is fresh-instance per access.** Comparing
     `req.timeframe == TimeFrame.Day` is always False. In stubs and
     assertions, compare `str(req.timeframe)` against
     `str(TimeFrame.Day)`. Add to "Testing" section.
   - **The `# paper-check: allow` escape hatch.** Document the
     convention used to exempt the settings validator (which must
     reference the live URL in its rejection logic) from the CI grep.
     Add to the "Paper-only enforcement" subsection.
2. **`ARCHITECTURE.md`** — add two small subsections:
   - **SDK boundary discipline.** "No pandas/numpy/SDK-native types
     cross into business logic. Every service that talks to Alpaca
     converts SDK responses into typed `Bar` (or equivalent)
     dataclasses at the adapter layer. Indicator, signal, and risk
     code operates on the dataclasses. Rationale: keeps business
     logic testable with trivial fixtures, prevents pandas from
     leaking dependency weight, and isolates SDK version changes."
   - **Secret management convention.** "Helm charts expose
     `createSecret` as a values flag. In dev (`values-dev.yaml`) the
     chart creates the Secret inline from values. In cluster-prod the
     chart assumes a SealedSecret has already reconciled the Secret
     into place. Every service's chart follows this pattern."
3. **`CLAUDE.md`** — add one line under §Working with Alpaca: "The
   `# paper-check: allow` comment exempts a line from the live-URL
   grep. Use only in the settings validator; never elsewhere."

These drift corrections are **not** Phase 2 work; they're Phase 1
debt. Land them first, tagged as `phase-1: drift:` commits, before
opening a `phase-2/...` branch.

---

## Goals

1. **In-cluster Postgres.** TimescaleDB deployed to `nexusquant`
   namespace at `postgres.nexusquant.svc.cluster.local:5432`. Init SQL
   from `infra/postgres/init/` runs on first boot. Signal service's
   `signal_db_write_failures_total` drops to zero.
2. **Shared Alpaca library.** `nexusquant_signal.alpaca_clients`,
   `.alpaca_logger`, `.rate_limiter` promoted to `libs/alpaca_common/`
   as a uv workspace member. Signal refactored to import from it (no
   behavior change). Executor uses it from day one.
3. **Risk service with real guards.** Every guard in `ARCHITECTURE.md`
   §Risk guards implemented, tested, and enforced server-side. Typed
   `Decision` input → one of three typed outcomes (`Executed`,
   `PendingApproval`, `Rejected`) with full audit persistence.
4. **Executor service with real order placement.** The one and only
   `submit_order` call site in the codebase. Takes validated decisions
   from the risk service, places paper orders with idempotency, logs
   every fill.
5. **Sealed-secrets baseline.** Controller installed in cluster,
   `SealedSecret` manifests for Alpaca + Postgres creds committed,
   `--set-file` pattern retired.
6. **Real `/readyz` checks.** Signal, risk, executor each ping the
   services they depend on (Postgres, Alpaca for executor) and return
   503 when dependencies are unhealthy.
7. **Auth on service-to-service calls.** Mutual shared-secret header
   between risk ↔ executor; rejected calls return 401 with a
   structured reason.

## Non-goals (defer to later phases)

- MCP tool surface wrapping risk/executor — Phase 5.
- Watchlist service business logic — Phase 4 (nightly scan writes
  candidates.parquet; risk's "allowlist" check in Phase 2 reads from
  a static JSON fallback; see §Watchlist fallback).
- Live WebSocket ingestion — Phase 3.
- Hermes integration — Phase 6.
- Slack approval buttons (Block Kit, interactive webhook) — Phase 6.
  In Phase 2, a `PendingApproval` outcome writes to the DB and that's
  it; nothing notifies a human yet. Approvals auto-expire after their
  TTL and flip to `expired` on read.
- Drawdown intraday computation from live prices — Phase 3. Phase 2's
  circuit breaker reads from realized P&L in the `orders` table and
  the current `get_account` equity from Alpaca.
- Fancy observability (Grafana dashboards, alerting) — Phase 3.
  Metrics must be present; dashboards wait.

If scope creeps, add to `TODO.md` under the appropriate phase.

---

## Architecture within the phase

### In-cluster Postgres

- **Chart location:** `infra/helm/postgres/`. Use TimescaleDB's
  official Helm chart as a dependency, or a thin wrapper over a
  `StatefulSet` + `PersistentVolumeClaim` — whichever Claude Code
  proposes with fewer CRDs in the loop. No operators unless the
  upstream chart requires one.
- **Storage:** single replica, 10Gi PVC on the default storage class.
  Data loss is acceptable in this lab; do not spend time on HA.
- **Init SQL:** mount `infra/postgres/init/` via ConfigMap, run
  on first boot. Same contents that docker-compose uses.
- **Secret:** `postgres-credentials` Secret in the `nexusquant`
  namespace, populated via SealedSecret. Contains
  `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`.
- **Service DNS:** `postgres.nexusquant.svc.cluster.local:5432`.
  This is what signal's `values.yaml` already assumes.

### Shared Alpaca library

```
libs/
└── alpaca_common/
    ├── pyproject.toml           # "nexusquant-alpaca-common"
    └── src/alpaca_common/
        ├── __init__.py
        ├── settings.py          # AlpacaSettings + validators
        ├── clients.py           # trading_client(), historical_data_client()
        ├── logger.py            # structured Alpaca call logger
        ├── rate_limiter.py      # shared token bucket
        ├── types.py             # Bar dataclass + converters
        └── errors.py            # typed Alpaca exceptions
```

- Root `pyproject.toml` adds `libs/*` to `tool.uv.workspace.members`.
- Signal's `pyproject.toml` replaces per-module imports with a
  `nexusquant-alpaca-common` workspace dep; the old modules in
  `nexusquant_signal/` are deleted and their uses rewired.
- Signal's behavior does not change. The refactor commit must be
  green against the existing Phase 1 test suite with zero test
  modifications, *then* a follow-up commit can tighten any test
  that was over-coupled to the old module paths.
- Executor depends on the common library from its first commit.

### Risk service

Service port 8002. Python package `nexusquant_risk`.

**Endpoints:**

| Method | Path                    | Purpose                                   |
|--------|-------------------------|-------------------------------------------|
| POST   | `/evaluate`             | Input: Decision. Output: one of three outcomes. |
| GET    | `/risk-budget`          | Current budget state (orders/notional remaining, drawdown, circuit-breaker state). |
| GET    | `/proposals/{id}`       | Single proposal state (for future approval flow). |
| POST   | `/proposals/{id}/decide`| Approve/reject a pending proposal. Server-auth'd; no human UI yet. |
| GET    | `/healthz`, `/readyz`   | Standard. `/readyz` pings Postgres. |
| GET    | `/metrics`              | Prometheus. |

**Input type (`Decision`):**

```python
@dataclass(frozen=True)
class Decision:
    symbol: str
    side: Literal["BUY", "SELL"]
    qty: int                      # positive integer
    reference_price: float        # for notional computation; risk may
                                  # reject if stale vs. Alpaca last-trade
    reason: str                   # free-text from upstream
    client_decision_id: str       # idempotency; same id ⇒ same outcome
```

**Outcome types:**

```python
@dataclass(frozen=True)
class Executed:
    status: Literal["executed"] = "executed"
    order_id: str
    fill: dict              # structured Alpaca fill snapshot

@dataclass(frozen=True)
class PendingApproval:
    status: Literal["pending_approval"] = "pending_approval"
    proposal_id: str
    expires_at: datetime
    reason: str             # why it went to approval (notional band)

@dataclass(frozen=True)
class Rejected:
    status: Literal["rejected"] = "rejected"
    reason: str             # machine-readable enum below
    context: dict           # structured details
```

**Rejection reason enum** (stable strings; anything else is a bug):

```
symbol_not_on_watchlist
symbol_not_held_for_sell          # from the shorting TODO
notional_exceeds_hard_ceiling     # > $10,000
hourly_auto_limit_reached
daily_auto_limit_reached
daily_auto_notional_reached
max_open_positions_reached
drawdown_circuit_breaker_active
per_symbol_cooldown_active
outside_market_hours
split_order_evasion_detected
stale_reference_price
malformed_request
duplicate_client_decision_id
```

**Guard evaluation order** (short-circuit; first rejection wins):

1. Schema validation (malformed → 422 with `malformed_request`)
2. Idempotency check (same `client_decision_id` → return prior outcome)
3. Allowlist (not in watchlist → reject)
4. Hard ceiling (notional > $10k → reject)
5. Market hours (outside 09:30–16:00 ET → reject)
6. Shorting guard (SELL on unheld symbol → reject)
7. Stale price (|reference_price − Alpaca last trade| / last > 1% → reject)
8. Per-symbol cooldown (same symbol auto-order within 30 min → reject)
9. Split-order evasion (same symbol+side within 10 min whose
   cumulative notional exceeds $2,500 → demote to proposal)
10. Budget checks (hourly / daily / daily-notional / open positions →
    reject)
11. Drawdown circuit breaker (−3% intraday → reject for BUYs; allow
    SELLs that reduce exposure)
12. Band routing:
    - notional < $2,500 → call executor, return `Executed` or
      `Rejected` based on fill outcome
    - $2,500–$10,000 → persist `Proposal`, return `PendingApproval`
    - the hard ceiling case is already handled at step 4

Every guard is a pure function taking `(Decision, RiskState) →
GuardResult`. Testable in isolation. The sequencer composes them.

### Executor service

Service port 8003. Python package `nexusquant_executor`.

**Endpoints:**

| Method | Path                    | Purpose                                   |
|--------|-------------------------|-------------------------------------------|
| POST   | `/orders`               | Server-auth'd. Body: validated order. Called *only* by risk after all guards pass. |
| GET    | `/orders/{client_id}`   | Look up prior order by client_order_id. Idempotency helper for risk. |
| GET    | `/positions`            | Proxy `get_all_positions` from Alpaca with caching (30s TTL). |
| GET    | `/account`              | Proxy `get_account` from Alpaca with caching (30s TTL). |
| GET    | `/healthz`, `/readyz`   | `/readyz` pings Postgres and Alpaca. |
| GET    | `/metrics`              | Prometheus. |

**Hard rules:**

- Exactly one `submit_order` call site, in
  `executor/src/nexusquant_executor/alpaca_ops.py::submit_validated_order`.
  No other module imports that function except the `/orders`
  handler. A CI grep enforces "only one file contains the string
  `.submit_order(`".
- Every order carries a deterministic `client_order_id` derived from
  the risk service's `client_decision_id`. The `orders` table's
  UNIQUE constraint on `idempotency_key` is the final backstop.
- Every outbound Alpaca call goes through the shared rate limiter
  (target 150 req/min).
- Every Alpaca call and response is logged via the shared structured
  logger.
- Executor trusts the risk service: once a request arrives at
  `/orders`, guards are not re-checked. Trust is enforced by the
  shared-secret header; the executor is not exposed outside the
  cluster.

### Watchlist fallback

Phase 4 introduces the dynamic nightly scan. Phase 2 needs an
allowlist now. Solution:

- New file `infra/watchlist/phase_2_allowlist.json`:
  ```json
  {
    "as_of": "phase_2_static",
    "symbols": ["AAPL", "MSFT", "NVDA", "SPY"]
  }
  ```
- Mounted into the risk service via ConfigMap.
- Risk's allowlist check reads this file, logs the `as_of` value in
  every decision. When Phase 4 lands, the same interface flips to
  reading the daily parquet.
- The watchlist service stub stays a stub in Phase 2. Do not wire it
  into the risk service. The JSON file is deliberately crude — it's
  a bridge, not infrastructure.

### Auth

Shared-secret header, one secret per service pair:

- `NEXUSQUANT_SHARED_SECRET_RISK_EXECUTOR` — mounted into both risk
  and executor via a SealedSecret-backed Secret. Value is a random
  32-byte base64 string. Generated once, rotated out-of-band.
- Middleware on executor's `/orders` endpoint rejects requests
  missing or mismatching the `X-Nexusquant-Shared-Secret` header with
  401 `{"reason": "auth_failed"}`.
- Risk's executor client adds the header automatically.
- Other endpoints (healthz/readyz/metrics) are unauthenticated.
- TLS is out of scope for this phase — in-cluster only, service-to-
  service. Mesh / mTLS gets its own later ADR.

---

## Persistence

**New tables** (add under `infra/postgres/init/` with numeric prefix
sorting *after* Phase 0's init files). **Do not modify existing init
files.**

```sql
CREATE TABLE risk_state (
    ts timestamptz NOT NULL DEFAULT now(),
    kind text NOT NULL,           -- 'drawdown', 'open_positions', etc.
    value_numeric numeric,
    value_text text,
    PRIMARY KEY (ts, kind)
);

CREATE INDEX idx_risk_state_kind_ts ON risk_state(kind, ts DESC);
```

`proposals`, `orders`, `decisions`, `risk_events` already exist from
Phase 0. Phase 2 fills them. The FK from `decisions.proposal_id` and
`orders.proposal_id` → `proposals.proposal_id` (noted in
`TODO.md#Phase 1`) lands in this phase since the write paths are now
wired.

**Write path:**

1. Decision arrives at risk `/evaluate`
2. Risk inserts into `decisions` (mode = 'auto' or 'proposal')
3. Each guard that fires logs to `risk_events`
4. If executed: executor inserts into `orders` (on successful Alpaca
   ack), updates on fill
5. If pending: risk inserts into `proposals`
6. Risk-state snapshots (current open positions, drawdown, budgets)
   write to `risk_state` on every evaluate — cheap, enables
   historical debugging

All writes are transactional per-decision. Unlike Phase 1's
fire-and-forget, **risk writes are synchronous** — if Postgres is
down, risk returns 503 and the caller retries. The audit log is the
product; losing rows is not acceptable.

Executor order writes are also synchronous but wrap the Alpaca call:
insert with status `submitting` → Alpaca call → update to `submitted`
or `failed`. This way a crash between DB and Alpaca is detectable
(rows in `submitting` state > 30s) rather than lost.

---

## Observability

Per-service metrics:

**Risk:**

- `risk_evaluations_total{outcome}` (executed, pending, rejected)
- `risk_rejections_total{reason}`
- `risk_evaluation_latency_seconds`
- `risk_guard_failures_total{guard, reason}` — per-guard diagnostic
- `risk_budget_remaining_auto_orders_hourly` (gauge)
- `risk_budget_remaining_auto_orders_daily` (gauge)
- `risk_budget_remaining_notional_daily` (gauge)
- `risk_open_positions` (gauge)
- `risk_circuit_breaker_active` (gauge, 0/1)
- `risk_proposals_pending` (gauge)

**Executor:**

- `executor_orders_submitted_total{status}` (ack, rejected, failed)
- `executor_fills_total{side}`
- `executor_order_latency_seconds`
- `alpaca_request_total{endpoint, status_code}`
- `alpaca_request_latency_seconds{endpoint}`
- `rate_limit_hit_total`

Structured logging continues on every Alpaca call. Every risk
decision emits one JSON line with `decision_id`, `symbol`, `side`,
`qty`, `notional`, `outcome`, `rejection_reason` (null on success),
`guards_passed`, and `guards_evaluated`.

Grafana dashboards stay out of scope. Emit metrics; wire dashboards
in Phase 3.

---

## Testing

**Unit tests (no network, no DB, no Alpaca):**

- Every guard tested in isolation with a `RiskState` fixture.
- Guard sequencer tested for correct short-circuit order (first
  rejection wins).
- Idempotency: same `client_decision_id` returns same outcome
  byte-for-byte.
- Rejection reason table: exhaustive — every enum value has a test
  that produces it.
- Executor `submit_validated_order` tested with `respx`-stubbed
  Alpaca; covers ack, rate-limit 429 with backoff, idempotency
  conflict, Alpaca rejection with structured error mapping.
- Hard requirement: a test that asserts **exactly one file** in the
  entire repo contains `.submit_order(`. Uses `Path.rglob` + string
  scan. This is the single most important test in Phase 2.

**Integration tests (gated behind env var, not in default CI):**

- Risk + executor + Postgres all running locally via compose.
- Issue 100 synthetic decisions covering a matrix of (allowlisted /
  not) × (auto / proposal / rejected notional) × (market hours /
  outside) × (cooldown active / not). Assert every expected outcome.
- Real Alpaca paper: one decision that lands an order, assert
  `orders` row, assert Alpaca position reflects the trade.
- Circuit breaker: simulate a drawdown > 3% via a fake `risk_state`
  insert, confirm subsequent BUY rejected and SELL allowed.

**What not to test:**

- Signal service (Phase 1, already done).
- MCP behavior (Phase 5).
- Alpaca's own correctness.

---

## Deployment

Three new Helm charts:

- `infra/helm/postgres/` — TimescaleDB, single replica, PVC, init SQL.
- `infra/helm/risk/` — FastAPI, port 8002, same pattern as signal.
- `infra/helm/executor/` — FastAPI, port 8003, same pattern as signal.

Signal's chart gets a minor update: replace `--set-file` Secret
pattern with SealedSecret-backed Secret; `createSecret=false` in
prod values.

Deployment order (manual):

1. Install sealed-secrets controller (one-time cluster bootstrap).
2. Create SealedSecrets for all creds. Check in.
3. `helm upgrade --install postgres ./infra/helm/postgres -n nexusquant`.
4. Verify init SQL ran (`\dt` returns expected tables).
5. Re-deploy signal with SealedSecret-backed Secret and the new
   Postgres target.
6. Verify signal's `signal_db_write_failures_total` stops climbing.
7. Deploy risk and executor.
8. Run the gated integration suite against the cluster.

**CI additions:**

- `build-risk`, `build-executor`: containerize and push to GHCR.
- `helm-lint` extended to cover all three new charts.
- A grep test in CI: exactly one `.py` file matches `\.submit_order\(`.
  This is a top-level workflow step, not a pytest; it runs regardless
  of test pass/fail.

---

## Acceptance criteria

A reviewer can:

1. `cd infra && docker compose up -d` — signal, risk, executor,
   Postgres, Redis all green.
2. `curl -X POST http://localhost:8002/evaluate \
   -H 'Content-Type: application/json' \
   -d '{"symbol":"AAPL","side":"BUY","qty":5, \
        "reference_price":200.0,"reason":"test", \
        "client_decision_id":"test-001"}'` —
   returns a structured outcome (executed / pending / rejected)
   validating against `schemas/place_paper_order.json`.
3. Same call twice — second call returns *byte-identical* outcome
   (idempotency).
4. A decision with notional $7,500 — returns `PendingApproval`,
   writes to `proposals`. `SELECT * FROM proposals` shows the row.
5. A decision for a symbol not in `phase_2_allowlist.json` — returns
   `Rejected` with `symbol_not_on_watchlist`.
6. A SELL decision for a symbol not held — returns `Rejected` with
   `symbol_not_held_for_sell`.
7. A decision outside market hours — returns `Rejected` with
   `outside_market_hours`.
8. `SELECT count(*) FROM risk_events` — grows with each rejection.
9. `pytest services/risk services/executor libs/alpaca_common` —
   green.
10. The one-`submit_order` CI check passes.
11. `curl http://localhost:8003/orders -H 'X-Nexusquant-Shared-Secret:
    wrong'` — 401.
12. In the cluster:
    - `oc get pods -n nexusquant` shows postgres, signal, risk,
      executor, all Ready.
    - Signal's `signal_db_write_failures_total` on `/metrics` reads
      the same value for 10 minutes straight (not climbing).
    - Risk's `/readyz` returns 503 when Postgres is scaled to 0;
      returns 200 when scaled back up.
13. A real paper order via the gated integration test: decision in,
    Alpaca paper account shows the position, `orders` table has
    matching row with `status='submitted'` and a non-null fill.
14. `docs/PHASE_2_RETRO.md` exists.

---

## Constraints for Claude Code

- Read all of §Required reading before writing any code.
- Land the three drift correction commits (SKILL.md, ARCHITECTURE.md,
  CLAUDE.md) as a small separate branch merged first. Do not bundle
  them with Phase 2 work.
- **Ship the phase in this order**; each is its own PR:
  1. Drift corrections (docs only).
  2. In-cluster Postgres chart + SealedSecret.
  3. `libs/alpaca_common/` + signal refactor (zero behavior change).
  4. Risk service: guards as pure functions + sequencer + unit tests.
  5. Risk service: endpoints, DB writes, idempotency.
  6. Executor service: `submit_validated_order` + unit tests.
  7. Executor service: endpoints, auth middleware.
  8. Risk → executor integration: the happy path.
  9. Risk → proposal path: DB persistence, auto-expiry.
  10. Helm charts for risk + executor.
  11. CI additions (build-risk, build-executor, one-submit_order check).
  12. Cluster deployment + gated integration test run.
- After commit 3 (shared library refactor), signal's test suite must
  be green *with no test changes*. If tests break, the refactor is
  wrong.
- After commit 4 (guards as pure functions), every guard must have
  unit-test coverage *before* moving to commit 5. Do not wire
  anything until guards are individually proven.
- Propose the full commit plan and wait for approval before any
  code. If mid-phase the plan needs revision, stop and propose the
  revision.
- If a reasonable shortcut is found, put it in `TODO.md` and do not
  take it. Phase 2 prioritizes correctness over cleverness.

## Definition of done

- All 14 acceptance criteria pass.
- Every guard in `ARCHITECTURE.md` §Risk guards has a corresponding
  unit test and a corresponding rejection reason enum value.
- Exactly one `.py` file in the repo contains `.submit_order(`.
- The shared Alpaca library is in place; signal uses it.
- `docs/PHASE_2_RETRO.md` captures surprises, changes-in-hindsight,
  and any updates needed to `ARCHITECTURE.md`, `CLAUDE.md`, or the
  alpaca-paper skill.

When all of the above hold, open `docs/PHASE_3.md` and begin.
