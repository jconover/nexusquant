# TODO

Work identified during a phase but deferred to a later phase. Phase-0 rule:
if it isn't in `docs/PHASE_0.md`, it goes here under the phase that owns it.

## Phase 1

- Add foreign keys from `decisions.proposal_id` and `orders.proposal_id` to
  `proposals.proposal_id` once service write paths are wired.
- Drift correction: `docs/PHASE_1.md` originally referenced
  `services/signal/src/signal/*.py` paths. Phase 0 established
  `nexusquant_signal` as the package name (bare `signal` shadows the stdlib
  module and breaks uvicorn SIGTERM handling + pytest). Paths in PHASE_1.md
  were corrected in-place to match. No code impact.

## Phase 2

- Authentication on service-to-service calls.
- Real `/readyz` checks: Postgres and Redis pings for the services that
  depend on them (signal, risk, executor, watchlist, ingester). Phase 0
  stubs return `{"status": "ok"}` unconditionally.
- Promote `nexusquant_signal.alpaca_clients`, `.alpaca_logger`, and
  `.rate_limiter` to a shared library when the executor service needs
  them. Phase 1 lands them per-service to avoid premature abstraction.
- Deploy in-cluster Postgres (TimescaleDB) in the `nexusquant` namespace
  at `postgres.nexusquant.svc.cluster.local:5432`, with init SQL from
  `infra/postgres/init/` applied on first boot. Phase 1 signal service
  assumes this host but runs standalone because fire-and-forget writes
  tolerate the connection failure; `signal_db_write_failures_total`
  climbs until this lands. Executor is the first service that actually
  needs audit writes to succeed, so this blocks Phase 2.
- Migrate Alpaca + Postgres credentials to sealed-secrets end to end.
  The Helm chart already supports this via `createSecret=false`; what's
  missing is (a) installing the sealed-secrets controller, (b) writing
  `SealedSecret` manifests for the `signal-alpaca` / `signal-postgres`
  Secrets the chart expects, and (c) doing the same for the risk +
  executor secrets as those services land. The one-off `--set-file`
  pattern used in Phase 1 doesn't scale once there are three services
  each with their own credentials.

## Phase 3

## Phase 4

- Evaluate polars for the universe scanner (batch EOD-bar feature
  engineering across thousands of symbols on orion). Phase 1 uses pure
  Python inside the signal service because the data volume is trivial
  (100 daily bars x 4 symbols); universe scanning is a different regime.

## Phase 5

## Phase 6

- Hermes agent integration (LLM decisions via MCP).

## Phase 7

---

## Repo boundary

Backtesting is **not** in this repo. It lives in europa-quant
(github.com/jconover/europa-quant), which answers whether a strategy
survives realistic costs and out-of-sample testing. This repo answers
whether an agent can be given bounded authority safely. See
`docs/decisions/0001-backtesting-in-europa-quant.md` for the boundary and
the reasoning.

If a future phase needs in-repo backtesting — validating an equities
signal on Alpaca bars, say — that reverses ADR 0001 and needs a new ADR,
not a quiet re-addition.

---

## Maintenance / cross-cutting

Not tied to a specific phase; environment hygiene that can land any time.

- ~~Bump GitHub Actions off Node 20.~~ **Done 2026-08-18.** All actions
  moved to their current major, each defaulting to Node 24:
  `checkout@v5`, `setup-uv@v10.0.1` (full pin — major-only tags are no
  longer published), `setup-helm@v5`, `login-action@v4`,
  `setup-buildx-action@v4`, `metadata-action@v6`, `build-push-action@v7`.
