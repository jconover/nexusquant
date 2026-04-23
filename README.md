# NexusQuant

A hybrid-autonomy paper-trading research platform. A deterministic server enforces
risk guards and executes orders; an LLM agent proposes trades through a narrow MCP
tool surface. See [`ARCHITECTURE.md`](ARCHITECTURE.md) for the full design.

> **NO REAL MONEY. PAPER TRADING ONLY.**

---

## Current phase

**Phase 1 — signal service, offline mode.** The signal service computes SMA/RSI/
VWAP/volume indicators from Alpaca REST bars, applies a deterministic buy/sell/hold
rule, persists to Postgres, and exposes Prometheus metrics. Every other service
remains a stub. Details: [`docs/PHASE_1.md`](docs/PHASE_1.md). Retrospective:
[`docs/PHASE_1_RETRO.md`](docs/PHASE_1_RETRO.md).

Phase 0 (repo scaffold and contracts) is complete: [`docs/PHASE_0.md`](docs/PHASE_0.md).

---

## Local dev quickstart

Prereqs: Docker with Compose v2. Alpaca paper keys from
[alpaca.markets](https://alpaca.markets) (free).

```sh
# 1. Populate .env from the example.
cp .env.example .env
# then edit .env -- replace ALPACA_API_KEY_ID and ALPACA_API_SECRET_KEY
# with real paper keys if you want /signal/{symbol} to return real data.
# The service starts fine with the placeholder keys; only Alpaca API calls
# will fail with an auth error.

# 2. Bring up the stack (from infra/ so compose paths resolve).
cd infra
docker compose up -d

# 3. Health-check all seven services.
for p in 8001 8002 8003 8004 8005 8006 8007; do
  curl -s "http://localhost:$p/healthz"; echo
done

# 4. Hit the Phase 1 endpoint (with real keys).
curl -s http://localhost:8001/signal/AAPL | jq

# 5. Scrape Prometheus metrics.
curl -s http://localhost:8001/metrics | grep -E '^(signals_computed|cache_|alpaca_)'

# 6. Confirm the signal persisted.
docker compose exec postgres psql -U nexusquant \
  -c "SELECT symbol, ts, rule_result FROM signals ORDER BY ts DESC LIMIT 5;"

# 7. Tear down (drop -v to keep the volumes).
docker compose down -v
```

**Port map** (host → container):
`signal 8001`, `risk 8002`, `executor 8003`, `watchlist 8004`, `ingester 8005`,
`mcp 8006`, `slack 8007`, `postgres 5433→5432`, `redis 6380→6379`, `minio 9000`
(console `9001`). Host-side Postgres/Redis are shifted off canonical so the
stack coexists with other local Docker projects.

---

## Running the tests

```sh
uv sync --all-packages
uv run pytest -q                        # ~120 unit tests, no network
uv run --with ruff ruff check .
uv run --with ruff ruff format --check .
uv run --with mypy mypy services/*/src
```

Live Alpaca integration tests are gated behind `RUN_ALPACA_INTEGRATION=1` and
excluded from the default pytest run.

See [`docs/dev-checks.md`](docs/dev-checks.md) for what each command does.

---

## Deploying the signal service to OKD

```sh
# First time only: create the namespace (chart does not).
oc create namespace nexusquant

# Install / upgrade with the dev overrides (ServiceMonitor enabled).
helm upgrade --install signal infra/helm/signal \
  -n nexusquant \
  -f infra/helm/signal/values-dev.yaml \
  --set image.tag=sha-<short-sha> \
  --set alpaca.createSecret=true \
  --set alpaca.apiKeyId=<paste> \
  --set alpaca.apiSecretKey=<paste> \
  --set postgres.createSecret=true \
  --set postgres.password=<paste>

# From a debug pod in the same namespace:
curl http://signal.nexusquant.svc.cluster.local:8001/signal/AAPL
```

In production, leave `alpaca.createSecret=false` / `postgres.createSecret=false`
and let sealed-secrets reconcile the two Secrets (`signal-alpaca` and
`signal-postgres`) out of band.

---

## Repo layout (current state)

```
nexusquant/
├── ARCHITECTURE.md              # system design
├── CLAUDE.md                    # session-level operating instructions
├── TODO.md                      # work deferred out of the current phase
├── docs/
│   ├── PHASE_0.md               # complete
│   ├── PHASE_1.md               # active
│   ├── PHASE_1_RETRO.md         # post-phase retrospective
│   ├── dev-checks.md            # what each CI command does and why
│   └── decisions/               # ADRs
├── schemas/                     # MCP tool JSON schemas + examples
├── services/
│   ├── signal/                  # Phase 1 live (8001): indicators + rule
│   ├── risk/                    # stub (8002)
│   ├── executor/                # stub (8003)
│   ├── watchlist/               # stub (8004)
│   ├── ingester/                # stub (8005)
│   ├── mcp/                     # stub (8006)
│   └── slack/                   # stub (8007)
├── infra/
│   ├── docker-compose.yaml      # local dev stack
│   ├── postgres/init/           # audit-schema init SQL (lex-ordered)
│   └── helm/
│       └── signal/              # Phase 1 chart (ClusterIP, no ingress)
├── tests/unit/                  # cross-service tests (schema validator)
├── .github/workflows/ci.yaml    # lint, typecheck, test, docker build,
│                                # helm lint, paper-only guard, GHCR push
├── pyproject.toml               # uv workspace root, shared tooling config
└── uv.lock
```

Later phases add `batch/`, `sidecars/`, and the remaining service internals
per [`ARCHITECTURE.md` §Repo layout](ARCHITECTURE.md#repo-layout-monorepo).

---

## Non-goals, restated

No live trading. No real-money API keys. No mention of Hermes outside its own
phase. If you're unsure whether something belongs, check the active phase doc
and put it in [`TODO.md`](TODO.md) if it's out of scope.
