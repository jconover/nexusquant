# TODO

Work identified during a phase but deferred to a later phase. Phase-0 rule:
if it isn't in `docs/PHASE_0.md`, it goes here under the phase that owns it.

## Phase 1

- Add foreign keys from `decisions.proposal_id` and `orders.proposal_id` to
  `proposals.proposal_id` once service write paths are wired.

## Phase 2

- Authentication on service-to-service calls.
- Real `/readyz` checks: Postgres and Redis pings for the services that
  depend on them (signal, risk, executor, watchlist, ingester). Phase 0
  stubs return `{"status": "ok"}` unconditionally.

## Phase 3

## Phase 4

## Phase 5

## Phase 6

- Hermes agent integration (LLM decisions via MCP).

## Phase 7
