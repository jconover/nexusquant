# NexusQuant — Architecture

A hybrid human/LLM agent paper-trading platform built across a self-managed OKD
cluster and a GPU workstation. The trading is the domain; the real deliverable
is the guardrail platform that lets an LLM agent take bounded action on a
deterministic service layer with full audit.

**Status:** design document. No code yet. Each implementation phase has its
own `PHASE_N.md`.

---

## Goals

- Demonstrate an end-to-end agentic system where an LLM (Hermes) makes
  buy/sell/hold decisions against Alpaca paper trading with hard server-side
  guardrails.
- Cleanly separate **universe selection** (deterministic batch),
  **signal generation** (deterministic real-time), **risk enforcement**
  (deterministic), and **decision/ranking** (the LLM).
- Produce a portfolio artifact that showcases platform engineering,
  observability, and agent safety — not trading alpha.

## Non-goals

- Real money. Paper only. The code path for live trading does not exist in
  this repo and will not be added.
- Sub-minute decision latency. This is not HFT. Decisions operate on
  minute-bar cadence at fastest.
- Options, futures, crypto. US equities only, IEX-quoted.
- Freestyle ticker selection by the LLM. Hermes only sees and acts on the
  pre-computed watchlist.
- The LLM constructing order payloads from scratch. Order placement is a
  deterministic Python function invoked via a typed MCP tool.

---

## Physical topology

```
┌────────────────────────┐      ┌────────────────────────────────────┐
│ orion (workstation)    │      │ OKD cluster (3x SER5 Max)          │
│ Ryzen 9 9950X          │      │ api VIP 192.168.68.100             │
│ 128GB RAM              │      │ ingress VIP 192.168.68.101         │
│ RTX 3090 24GB          │      │ nexuslab.nexuslab.local            │
├────────────────────────┤      ├────────────────────────────────────┤
│ Nightly universe scan  │─────▶│ MinIO: candidates.parquet          │
│ Ollama enrichment API  │◀─────│ Signal service calls for sentiment │
│ Jupyter (research)     │      │ WebSocket ingester                 │
│ Backtester (batch)     │      │ Signal service (rolling indicators)│
└────────────────────────┘      │ Risk service                       │
                                │ Order executor (Alpaca paper)      │
                                │ MCP server (tool surface)          │
                                │ Postgres/TimescaleDB (audit)       │
                                │ Prometheus + Grafana               │
                                │ Slack approver (Block Kit buttons) │
                                └────────────────────────────────────┘
                                                 ▲
                                                 │ MCP
                                                 │
                                      ┌──────────┴──────────┐
                                      │ Hermes Agent        │
                                      │ (small PC, cron)    │
                                      └─────────────────────┘
```

## Workload split rationale

- **orion** is used where *iteration volume* or *model size* matters:
  backtesting, feature engineering, universe scoring across thousands of
  symbols, local LLM inference for sentiment/summarization. Batch,
  on-demand. Not required for live trading to continue.
- **OKD** is used where *uptime and uniformity* matter: the live signal
  pipeline, risk enforcement, order execution, audit, observability.
  Everything always-on.
- **Hermes** is the narrator and orchestrator. It reasons over structured
  candidate state and decides what to act on. It does not generate
  signals, hold secrets, or construct order payloads.

---

## Data flow

```
Alpaca REST (EOD bars, full universe)
        │
        ▼
[orion] Nightly universe scan ──► candidates.parquet ──► MinIO
        │                                                  │
        │                                                  ▼
        │                                  [OKD] Watchlist service (loads at open)
        │                                                  │
        ▼                                                  ▼
Alpaca WebSocket ◀───────── subscribes to watchlist symbols
        │
        ▼
[OKD] Ingester ──► Redis Streams ──► Signal service (rolling indicators)
                                              │
                                              ▼
                                       MCP tool surface
                                              │
                                              ▼
                                      [Hermes] reasons, decides
                                              │
                                              ▼
                                      place_paper_order(...)
                                              │
                                              ▼
                                       Risk service (validates)
                                              │
                              ┌───────────────┼───────────────┐
                              ▼               ▼               ▼
                         executed      pending_approval    rejected
                              │               │               │
                              ▼               ▼               ▼
                         Alpaca paper   Slack button    Structured reason
                              │               │
                              ▼               ▼
                         Postgres audit  (approved → executed; expires 5m)
```

---

## MCP tool surface

The only interface Hermes has to the platform. Every tool has a strict JSON
schema (see `/schemas` once built).

| Tool                    | Purpose                                              |
|-------------------------|------------------------------------------------------|
| `get_market_status`     | Is the market open? pre/post/closed?                 |
| `get_watchlist`         | Today's candidates with the features that ranked them|
| `get_signal`            | Indicators + rules output for a watchlist symbol     |
| `get_sentiment`         | Optional; calls Ollama on orion for news sentiment   |
| `get_portfolio`         | Current positions, cash, P&L                         |
| `get_risk_budget`       | Remaining hourly/daily order budget, drawdown state  |
| `place_paper_order`     | Validates via risk service; returns 1 of 3 outcomes  |

`place_paper_order` response shape:

```json
{ "status": "executed",         "order_id": "...", "fill": { ... } }
{ "status": "pending_approval", "proposal_id": "...", "expires_at": "..." }
{ "status": "rejected",         "reason": "daily_auto_order_limit_reached" }
```

Hermes does not choose which outcome it gets. The risk service decides,
based on size and current budget state.

---

## Hybrid autonomy thresholds

| Notional per order | Mode                                       |
|--------------------|--------------------------------------------|
| < $2,500           | Auto-execute, post-hoc Slack notification  |
| $2,500 – $10,000   | Proposal mode, Slack approve/reject, 5m TTL|
| > $10,000          | Rejected outright                          |

Tuning starts conservative and loosens only after observed behavior warrants.

## Risk guards (server-side, not agent-trusted)

- Symbol allowlist (from today's watchlist only)
- Max auto-orders per hour: 3
- Max auto-orders per day: 10
- Max total auto notional per day: $15,000
- Max open positions: 8
- Daily drawdown circuit breaker: -3% disables auto mode
- Per-symbol cooldown: no repeat auto-order within 30 min on same symbol
- Market hours gate: reject outside 09:30–16:00 ET
- Idempotency key required on every order
- Split-order evasion detection: same symbol + side within N minutes whose
  cumulative notional exceeds auto threshold requires approval
- `risk_check: PASS` required before executor accepts the order

---

## Audit and observability

Every `data → signal → decision → order → fill` event lands in
Postgres/TimescaleDB with:

- Structured fields (timestamps, prices, sizes, guard results)
- The Hermes reasoning text that accompanied the decision
- The proposal/approval trail if applicable
- The fill details from Alpaca

Prometheus metrics (non-exhaustive):

- `signals_computed_total{symbol}`
- `orders_submitted_total{status}`
- `risk_rejections_total{reason}`
- `proposal_approval_latency_seconds`
- `daily_drawdown_pct`
- `auto_budget_remaining_notional`
- `watchlist_size`

Grafana dashboards: live trading view, risk budget view, agent reasoning
review.

---

## Repo layout (monorepo)

```
nexusquant/
├── ARCHITECTURE.md              # this file
├── TODO.md                      # anything deferred out of current phase
├── docs/
│   ├── PHASE_0.md .. PHASE_7.md
│   └── decisions/               # ADRs
├── schemas/                     # MCP tool JSON schemas + order shapes
├── services/
│   ├── signal/                  # FastAPI, rolling indicators
│   ├── risk/                    # Deterministic guards
│   ├── executor/                # Alpaca paper wrapper
│   ├── watchlist/               # Loads daily candidates.parquet
│   ├── ingester/                # Alpaca WebSocket → Redis Streams
│   ├── mcp/                     # MCP server wrapping the above
│   └── slack/                   # Block Kit proposal approver
├── batch/
│   ├── universe_scan/           # Runs on orion (nightly)
│   └── backtester/              # Runs on orion (on-demand)
├── sidecars/
│   └── ollama_enrichment/       # Runs on orion, called by signal svc
├── infra/
│   ├── docker-compose.yaml      # Local dev
│   ├── helm/                    # OKD deployment
│   └── terraform/               # If any cloud bits later
├── .github/workflows/           # CI: lint, test, build, push
└── tests/
    ├── unit/
    └── integration/
```

---

## Non-goals, restated (important)

If any of the following appear in a PR, reject:

- Live trading code paths, real-money API keys, or any reference to
  `paper=False`.
- Tools that let the agent query arbitrary tickers outside the watchlist.
- LLM-generated order payloads (JSON constructed by the LLM and passed
  verbatim to Alpaca). Orders are always constructed by deterministic code
  from typed arguments the LLM supplies.
- Storage of secrets in agent memory, prompt context, or config files.
  Secrets live in Kubernetes Secrets, injected at runtime.
- Strategies touted as "alpha." This is a platform demo. Strategies are
  illustrative.
