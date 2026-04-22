# NexusQuant

A hybrid-autonomy paper-trading research platform. A deterministic server enforces
risk guards and executes orders; an LLM agent proposes trades through a narrow MCP
tool surface. See [`ARCHITECTURE.md`](ARCHITECTURE.md) for the full design.

> **NO REAL MONEY. PAPER TRADING ONLY.**

---

## Current phase

**Phase 0 — repo scaffold and contracts.** No business logic. The deliverable is
a repo where `docker compose up` starts empty services that answer health checks,
every MCP tool has a JSON schema, the Postgres audit schema is defined, and CI is
green. Details: [`docs/PHASE_0.md`](docs/PHASE_0.md).

---

## Local dev quickstart

Prereqs: Docker with Compose v2.

```sh
# 1. Populate .env from the example (gitignored; placeholders only).
cp .env.example .env

# 2. Bring up the stack. Commands must run from infra/ because the
#    compose file uses ../.env and ../services/ relative paths.
cd infra
docker compose up -d

# 3. Health-check all seven stub services (expect {"status":"ok"} x7).
for p in 8001 8002 8003 8004 8005 8006 8007; do
  curl -s "http://localhost:$p/healthz"; echo
done

# 4. Confirm the audit tables were created on first Postgres boot.
docker compose exec postgres psql -U nexusquant -c "\dt"

# 5. Tear down (drop -v if you want the volumes preserved).
docker compose down -v
```

Service port map: signal 8001, risk 8002, executor 8003, watchlist 8004,
ingester 8005, mcp 8006, slack 8007. Postgres host-side 5433 (canonical
5432 inside the container), Redis host-side 6380 (canonical 6379 inside),
MinIO 9000 (console 9001). Host-side ports are moved off canonical so the
stack coexists with other local docker projects that already bind 5432
and 6379.

---

## Repo layout (current state)

```
nexusquant/
├── ARCHITECTURE.md              # system design
├── TODO.md                      # work deferred out of the current phase
├── docs/
│   └── PHASE_0.md               # active phase spec
├── schemas/                     # MCP tool JSON schemas + examples
├── services/
│   ├── signal/                  # FastAPI stub (8001)
│   ├── risk/                    # FastAPI stub (8002)
│   ├── executor/                # FastAPI stub (8003)
│   ├── watchlist/               # FastAPI stub (8004)
│   ├── ingester/                # FastAPI stub (8005)
│   ├── mcp/                     # FastAPI stub (8006)
│   └── slack/                   # FastAPI stub (8007)
├── infra/
│   ├── docker-compose.yaml      # local dev stack
│   └── postgres/init/           # audit-schema init SQL (lex-ordered)
├── tests/unit/                  # schema-example validator
├── .github/workflows/ci.yaml    # lint, type-check, test, docker build
├── pyproject.toml               # uv workspace root, shared tooling config
└── uv.lock
```

Services currently expose only `/healthz` and `/readyz`. See
[`ARCHITECTURE.md` §Repo layout](ARCHITECTURE.md#repo-layout-monorepo) for the
full target layout (batch jobs, sidecars, Helm, Terraform — later phases).

---

## Non-goals, restated

No live trading. No real-money API keys. No mention of Hermes outside its own
phase. If you're unsure whether something belongs, check `docs/PHASE_0.md` and
put it in `TODO.md` if it's out of scope.
