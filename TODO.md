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
