# PHASE_1 — Signal service, offline mode

Phase 0 gave us a scaffold. Phase 1 puts real business logic in exactly
one service: `signal`. Every other service stays a stub until its own
phase. By the end of Phase 1:

- `GET /signal/{symbol}` returns indicators + a rules-based buy/sell/hold
  decision, computed from historical Alpaca REST bars.
- Results are persisted to the `signals` hypertable.
- A `/metrics` endpoint exposes Prometheus counters.
- The service builds to a container image pushed to GHCR and deploys to
  OKD via a Helm chart behind a ClusterIP (no ingress yet).
- CI remains green, including a new unit-test suite that mocks Alpaca
  entirely.

**Required reading before writing any code in this phase:**

1. `ARCHITECTURE.md` — unchanged.
2. `docs/PHASE_0.md` — for continuity of conventions.
3. `~/.claude/skills/alpaca-paper/SKILL.md` — **governs every line of
   Alpaca code**. Read this before you `pip install alpaca-py`. Its
   guardrails are binding: paper-only enforcement, idempotency keys,
   symbol allowlists, rate limits, structured logging, WebSocket
   reconnection. The WebSocket rules don't bite this phase (Phase 3 is
   live data), but the paper-only + rate-limit + logging rules do.
4. `schemas/get_signal.json` — the response shape is already a contract.
   Phase 1 makes it real; it does not change it. If the schema is
   insufficient, propose a schema change in a separate commit first.

---

## Goals

1. Build a production-shaped signal service. "Offline mode" means it
   sources data from Alpaca REST (historical bars), not from live
   WebSockets. Everything else — response shape, persistence, metrics,
   deployment — is real.
2. Prove out the Alpaca skill in practice: settings validation, client
   factory, structured logging, rate-limit handling, credential hygiene.
3. Ship the first Helm chart and first GHCR image. Deploy to the OKD
   cluster behind a ClusterIP. The service is reachable from inside the
   cluster at `signal.nexusquant.svc.cluster.local:8001`.

## Non-goals (defer to later phases)

- Live WebSocket ingestion — Phase 3.
- Risk service, order executor business logic — Phase 2.
- MCP wrapping of signal — Phase 5.
- Hermes integration — Phase 6.
- Ingress / external exposure of the signal service.
- Grafana dashboards (expose metrics; wire dashboards in Phase 3 once
  multiple services emit).
- Auth on service-to-service calls (already in `TODO.md` under Phase 2).
- FK constraints on audit tables (already in `TODO.md` under Phase 1 for
  the `decisions`/`orders` → `proposals` edges; **do not** add those in
  this phase, they don't apply to the signals table).
- Touching any other service's code. Stubs stay stubs.

If scope creeps, add to `TODO.md` under the appropriate phase.

---

## Symbol universe for this phase

Hardcode a small list in `services/signal/src/nexusquant_signal/universe.py`:

```python
PHASE_1_SYMBOLS: frozenset[str] = frozenset({"AAPL", "MSFT", "NVDA", "SPY"})
```

Any request for a symbol outside this set returns `404` with a structured
body `{"error": "symbol_not_in_phase_1_universe", "symbol": "..."}`.
Later phases replace this with the dynamic watchlist; the 404 is a
reminder that symbol allowlisting is the rule, not the exception.

---

## Indicators and rule

Compute against the trailing window of daily bars pulled from Alpaca
REST (`StockBarsRequest`, `TimeFrame.Day`, 100 trading days
lookback — enough for SMA(50) + buffer):

- `sma_20` — 20-day simple moving average of close
- `sma_50` — 50-day simple moving average of close
- `rsi_14` — 14-period RSI on close (use Wilder's smoothing)
- `vwap` — session VWAP from the most recent day's minute bars
  (separate `TimeFrame.Minute` request for today only)
- `avg_volume_20` — 20-day average of daily volume
- `last_close` — most recent daily close
- `last_volume` — most recent daily volume

Rule combination produces a `signal` enum:

```
BUY  if last_close > sma_20 > sma_50 AND rsi_14 < 70 AND last_volume > avg_volume_20
SELL if last_close < sma_20 < sma_50 AND rsi_14 > 30
HOLD otherwise
```

The response also includes `rules_passed: int` (how many of the component
conditions for the chosen signal were true) — **not** a `confidence`
field. Rules-based strategies don't produce probabilities; don't pretend
they do. This matches what we discussed in Phase 0 design.

**Do not invent additional indicators or rules.** If another indicator
seems obviously useful, put it in `TODO.md` under Phase 3 (when live data
makes more indicators meaningful) and move on.

---

## Response shape

Must validate against `schemas/get_signal.json` (already defined in
Phase 0). Example:

```json
{
  "symbol": "AAPL",
  "as_of": "2026-04-22T20:00:00Z",
  "indicators": {
    "sma_20": 210.14,
    "sma_50": 205.88,
    "rsi_14": 58.2,
    "vwap": 211.02,
    "avg_volume_20": 54200000,
    "last_close": 212.45,
    "last_volume": 61300000
  },
  "signal": "BUY",
  "rules_passed": 3,
  "data_source": "alpaca_rest",
  "cache_hit": false
}
```

If the schema in `schemas/get_signal.json` doesn't already have these
fields, treat that as a Phase 0 deficiency — amend the schema (and its
example in `schemas/examples/`) as the first commit of Phase 1.

---

## Persistence

Every successful signal computation writes one row to `signals` (the
Phase 0 hypertable). Use the existing columns from
`infra/postgres/init/` — do not add columns this phase unless they're
strictly necessary to satisfy the schema above, and if they are, add a
new numerically-suffixed init file that lands **after** the Phase 0 ones.

Writes happen in a separate task (fire-and-forget via `asyncio.create_task`
or a small background queue); a DB outage must not fail the signal
response. Log the write failure and increment a counter; serve the
computed signal anyway.

---

## Caching

Alpaca's free tier rate-limits apply. Add an in-memory TTL cache keyed
on `(symbol, timeframe, start_date, end_date)`:

- Daily bars: TTL 15 minutes during market hours, 6 hours outside.
- Minute bars (for VWAP): TTL 60 seconds during market hours, 1 hour
  outside.

`cachetools.TTLCache` is fine. No Redis yet — Phase 3 introduces shared
caching. Emit a `cache_hit_total{kind="daily|minute"}` counter.

The cache is process-local. With `replicas=1` (which is what we deploy
in this phase), that's acceptable. Note in the Helm chart a comment that
scaling replicas requires moving the cache to Redis first.

---

## Observability

### Structured logging

Per the Alpaca skill: JSON lines to stdout, one line per outbound Alpaca
request and its response, with `ts`, `service=signal`, `direction`,
`endpoint`, `method`, `status_code`, `latency_ms`, `request_id`,
`symbol`. Redact key/secret headers. Use the shared logger pattern from
the skill; if it doesn't exist yet as a shared lib, create
`services/signal/src/nexusquant_signal/alpaca_logger.py` and note in `TODO.md`
under Phase 2 that it should be promoted to a shared library when the
executor and ingester need it.

### Prometheus metrics

Add `prometheus-client` to the signal service. Expose `/metrics` (text
exposition format, default path, no auth). Counters and gauges:

- `signals_computed_total{symbol, signal}` — counter
- `signal_computation_latency_seconds` — histogram
- `alpaca_request_total{endpoint, status_code}` — counter
- `alpaca_request_latency_seconds{endpoint}` — histogram
- `cache_hit_total{kind}` / `cache_miss_total{kind}` — counters
- `signal_db_write_failures_total` — counter
- `rate_limit_hit_total` — counter (fires on Alpaca `429`)

No Grafana dashboards this phase. Metrics should be *present and
correct*; dashboards come in Phase 3 when multiple services emit and
the kube-prometheus-stack is assumed installed.

---

## Deployment

### Helm chart

New directory: `infra/helm/signal/`. Minimal viable chart:

```
infra/helm/signal/
├── Chart.yaml
├── values.yaml
├── values-dev.yaml           # overrides for the homelab cluster
└── templates/
    ├── deployment.yaml       # replicas=1, readiness/liveness on /readyz, /healthz
    ├── service.yaml          # ClusterIP, port 8001
    ├── secret.yaml           # Alpaca creds; populated via sealed-secrets
    ├── configmap.yaml        # non-secret settings (data feed, symbol list, etc.)
    └── servicemonitor.yaml   # if Prometheus Operator CRDs are available;
                              # gated behind a values flag
```

Values include:
- `image.repository` (GHCR path)
- `image.tag` (image tag, defaults to `Chart.appVersion`)
- `alpaca.baseUrl` (`https://paper-api.alpaca.markets` — enforced by the
  skill's settings validator; configmap just for visibility)
- `alpaca.dataFeed` (`iex`)
- `postgres.host` / `postgres.port` / `postgres.database` (from the
  cluster-local postgres; creds via secret)

Deploy namespace: `nexusquant` (create if absent via a one-line
`kubectl create namespace` note in the README — not via Helm).

### Registry and image

Container builds go to `ghcr.io/jconover/nexusquant-signal`. Tags:
- `:sha-<short-sha>` on every push to `main`
- `:v0.1.0` on a git tag matching `signal-v*`

No Phase-0 images existed yet; this is the first real image.

### CI additions

Extend `.github/workflows/ci.yaml`:
- New job `build-signal`: builds the signal service image and pushes to
  GHCR on `push` to `main`. Uses `GITHUB_TOKEN` with `packages: write`.
  Skip on PRs (build only, no push).
- New job `helm-lint`: runs `helm lint infra/helm/signal/` and
  `helm template ... | kubectl --dry-run=client apply -f -`. No cluster
  credentials needed.
- Existing lint/typecheck/test jobs continue to cover the signal service
  as a uv workspace member.

**Do not** add a deploy-to-cluster CI job. Deployment is manual this
phase (`helm upgrade --install ...`); automation comes in a later phase
once there are >1 services to deploy.

---

## Testing

### Unit tests (no network)

Location: `services/signal/tests/unit/`.

- `test_indicators.py` — feed known bars, assert indicator values to 4
  decimals. Cover: trivial cases, edge cases (all same price → RSI=50,
  zero volume, insufficient history → 422 or typed error).
- `test_rules.py` — exhaustive boolean table over the rule inputs.
- `test_signal_endpoint.py` — FastAPI test client. Alpaca is mocked via
  `respx` or `pytest-httpx` (already in dev deps). Assert response
  matches `schemas/get_signal.json`.
- `test_cache.py` — second call with same args returns `cache_hit=true`
  and makes zero Alpaca calls.
- `test_settings_validation.py` — confirm the `must_be_paper` /
  `must_be_paper_url` validators from the skill crash startup when
  misconfigured. Use `monkeypatch` on env vars.
- `test_404_outside_universe.py` — `GET /signal/TSLA` returns 404 with
  the expected body.
- `test_metrics.py` — `/metrics` exposes every counter named above.

### Integration tests (real paper keys, gated)

Location: `services/signal/tests/integration/`. Skipped unless
`RUN_ALPACA_INTEGRATION=1`.

- `test_alpaca_roundtrip.py` — one test: hit paper Alpaca for AAPL
  daily bars, get a real response, compute indicators, assert the signal
  value is one of `{"BUY","SELL","HOLD"}` and the indicators are sane
  (not NaN, positive prices, etc.). Uses `FAKEPACA` for any stream
  assertions if applicable.

Integration tests are excluded from the default CI `pytest` run. They
may be wired to a separate CI workflow later, but not in this phase.

### What not to test

- Alpaca's own correctness.
- Grafana dashboards (not created).
- Any other service.

---

## Acceptance criteria

A reviewer can:

1. `cd infra && docker compose up -d` — signal service comes up on 8001
   and health-checks green (unchanged from Phase 0, but now with real
   business logic wired).
2. `curl http://localhost:8001/signal/AAPL` — receives a JSON response
   validating against `schemas/get_signal.json`, with a real computed
   signal. Requires a local `.env` with paper keys.
3. `curl http://localhost:8001/signal/TSLA` — receives `404` with the
   structured "not in universe" body.
4. `curl http://localhost:8001/metrics` — receives Prometheus text
   exposition with every counter listed above.
5. `docker compose exec postgres psql -U nexusquant -c "SELECT symbol,
   signal FROM signals ORDER BY ts DESC LIMIT 5;"` — shows rows from
   the curl calls above.
6. `pytest services/signal` — green.
7. `pytest services/signal` with `RUN_ALPACA_INTEGRATION=1` (with real
   paper keys) — green.
8. `helm lint infra/helm/signal/` — clean.
9. Push to main → CI green, new image appears at
   `ghcr.io/jconover/nexusquant-signal:sha-<short>`.
10. `helm upgrade --install signal infra/helm/signal/ -n nexusquant -f
    infra/helm/signal/values-dev.yaml` deploys to the OKD cluster. Pod
    goes ready. From a debug pod in-cluster:
    `curl http://signal.nexusquant.svc.cluster.local:8001/signal/AAPL`
    returns a valid signal.

---

## Constraints for Claude Code

- **Read the alpaca-paper SKILL.md before writing any Alpaca code.** The
  skill's rules override any plausible-looking shortcut.
- No `paper=False` anywhere. Not even in a commented-out line. CI should
  already grep for this — if it doesn't, add the check as part of
  Phase 1.
- Service code uses the shared settings pattern from the skill. If a
  factory for Alpaca clients doesn't yet exist at the repo level, it's
  fine to land it inside `services/signal/src/nexusquant_signal/alpaca_clients.py`
  for now and note in `TODO.md` that it gets promoted to a shared
  library in Phase 2 when the executor needs it too.
- Postgres connection: use `psycopg[binary]` + `psycopg_pool` async pool.
  No SQLAlchemy. One module, `services/signal/src/nexusquant_signal/db.py`, handles
  pool setup and the single INSERT. Read from env: `POSTGRES_HOST`,
  `POSTGRES_PORT`, `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`.
- Commit in logical units:
  1. Schema fixes (if `get_signal.json` needs amending)
  2. Indicators + rules (pure functions, unit-tested in isolation)
  3. Alpaca integration (the client, settings, logging)
  4. Endpoint wiring + cache
  5. DB persistence
  6. Metrics
  7. Dockerfile + Helm chart
  8. CI extensions
  9. README updates
- Before writing code, propose the commit plan and wait for approval
  (same rule as Phase 0).

## Definition of done

- All 10 acceptance criteria pass.
- Every Alpaca skill rule that applies to REST + settings + logging is
  demonstrably enforced (not just stated).
- `docs/PHASE_1_RETRO.md` exists with three bullets: surprises, what
  you'd do differently, anything in `ARCHITECTURE.md` or the skill that
  needs updating based on real-world use.

When all of the above hold, open `docs/PHASE_2.md` and begin.
