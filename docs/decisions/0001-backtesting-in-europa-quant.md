# 0001 — Backtesting lives in europa-quant, not in this repo

**Status:** Accepted
**Date:** 2026-08-18

## Context

`ARCHITECTURE.md` has listed a `batch/backtester/` component since the design
was written — in the physical topology diagram, in the workload split
rationale, and in the repo layout. It has never had a phase doc, a `TODO.md`
entry, or a line of code. It is the only component in the architecture with no
owner and no schedule.

Separately, a dedicated research repository now exists at
`~/Projects/europa-quant` (github.com/jconover/europa-quant). Its M1 milestone
is complete and verified against real market data: a partitioned Parquet lake
over CME futures bars, a broker-parameterised cost model, a hand-written
backtest engine with an explicit no-look-ahead rule, and a random-entry null
test proving the cost model is genuinely wired in.

The two efforts have near-zero technical overlap. europa-quant uses polars,
DuckDB and Parquet over CME futures; nexusquant uses FastAPI, psycopg and
Postgres over US equities on Alpaca paper. They share Python 3.12 and `uv`.

Keeping a backtester in this repo would also violate this repo's own stated
non-goals. `ARCHITECTURE.md` excludes futures explicitly, and states the
deliverable is "platform engineering, observability, and agent safety — not
trading alpha." A backtester exists to evaluate alpha.

## Decision

**Backtesting is out of scope for nexusquant. It lives in europa-quant.**

The `batch/backtester/` component is removed from `ARCHITECTURE.md` rather
than left as an unowned placeholder. References to it are replaced with a
pointer to europa-quant.

`batch/universe_scan/` is unaffected. Nightly universe scanning produces the
watchlist this platform's risk service enforces against, and remains in scope
for Phase 4.

## Boundary between the two repositories

They compose sequentially rather than overlapping:

| | europa-quant | nexusquant |
|---|---|---|
| Question | Does this strategy survive costs and out-of-sample testing? | Can an agent be given bounded authority safely? |
| Instrument | CME futures (ES bars, MES contract) | US equities, IEX-quoted |
| Deliverable | Research validity | Guardrail platform |

A strategy validated in europa-quant could eventually inform a nexusquant
signal — that is europa-quant's own "paper trade the survivor for a quarter"
step. That hand-off is not designed and is not in scope for any current phase.
It would need its own ADR.

**No code is shared.** No submodule, no vendored package, no cross-repo
imports. The relationship is conceptual.

## Consequences

- `ARCHITECTURE.md` loses its `batch/backtester/` references. `batch/` remains
  for `universe_scan/`.
- The repo's stated scope becomes internally consistent: nothing in
  `ARCHITECTURE.md` now implies work that contradicts its own non-goals.
- Anyone looking for backtesting is directed to europa-quant rather than
  finding an empty promise.
- If a future phase genuinely needs in-repo backtesting — for example to
  validate an equities signal on Alpaca bars — that reverses this decision and
  requires a new ADR, not a quiet re-addition.
