# Local dev checks

The six commands below are the "is this repo healthy?" loop. They're what
CI runs on every push, and they're what you run locally before committing
so you don't wait on GitHub Actions to tell you something obvious is broken.

Run them from the repo root unless noted. They're independent — order
doesn't matter and they can run in parallel.

---

## 1. `uv run pytest -q`

**What:** Runs the test suite. The `-q` (quiet) flag hides per-test output;
you get a dot per passing test and a summary line. In this repo it covers
two things:

- Each service's `tests/test_health.py` — asserts `/healthz` returns 200.
- `tests/unit/test_schemas.py` — validates every example JSON payload in
  `schemas/examples/` against its matching JSON Schema in `schemas/`.

**Why:** Tests are the executable half of the spec. If a stub stops
returning 200 or a schema example drifts from its schema, this fails fast.
Phase 0's 45 tests are almost entirely schema validation — the real
behavioral tests show up in later phases.

**`uv run` vs plain `pytest`:** `uv run` spawns the command inside the
project's managed virtualenv (`.venv/`, created by `uv sync`). It means you
never have to remember to `source .venv/bin/activate`, and it guarantees
the pinned versions from `uv.lock` are the ones being used.

---

## 2. `uv run --with ruff ruff check .`

**What:** `ruff` is a Python linter (Rust-based, very fast). `check` scans
for bugs and style issues — unused imports, undefined names, shadowed
built-ins, bad exception handling, etc. The `.` is the path to scan.

**Why:** A linter catches a whole class of defects before they reach
runtime. It also enforces consistency so code reviews don't devolve into
style nitpicks. Config lives in `pyproject.toml` under `[tool.ruff]`.

**`--with ruff`:** ruff isn't a project dependency — it's a tool. `--with`
tells `uv run` to install it into an ephemeral environment just for this
command. Keeps the project's `.venv/` clean of dev-only tooling.

---

## 3. `uv run --with ruff ruff format --check .`

**What:** ruff also has a formatter (Black-compatible). `format` would
rewrite files; `--check` only reports whether they *would* be rewritten,
exiting non-zero if any file is mis-formatted.

**Why:** Formatting is not-negotiable in CI so the diff you see in a PR
is a real change, not a whitespace reshuffle. Locally you'd run without
`--check` to actually apply the formatting; CI uses `--check` as a gate.

**Why separate from `ruff check`:** `check` finds bugs; `format`
rearranges whitespace. Two different jobs, two commands. ruff bundles
both tools under one CLI but keeps them distinct.

---

## 4. `uv run --with mypy mypy services/*/src`

**What:** mypy is a static type checker. Python is dynamically typed at
runtime, but when you add annotations (`def foo(x: int) -> str:`) mypy
reads them and flags inconsistencies without running the code. The
argument `services/*/src` is a shell glob that expands to all seven
service source trees — we only type-check service code, not tests.

**Why:** Types catch integration bugs that tests often miss — passing the
wrong shape across a module boundary, forgetting an `Optional`, returning
`None` where a value is required. Catching this at edit-time is much
cheaper than catching it at runtime in production.

**Why `services/*/src` specifically:** PHASE_0.md says `mypy src/`. We're
honoring that directive per-service. Tests are deliberately excluded —
test code is allowed to be looser (e.g. `def test_foo():` with no return
annotation is idiomatic pytest).

---

## 5. `cd infra && docker compose config > /dev/null`

**What:** `docker compose config` parses `docker-compose.yaml`, expands
environment variables from `../.env`, resolves `depends_on`, and prints
the final merged config. Redirecting to `/dev/null` throws the output
away — we only care whether it parses without error.

**Why:** YAML is easy to get wrong (wrong indentation, a missing colon,
an undefined `${VAR}`). This is the cheapest possible "will compose even
start?" check. It does not pull images, build containers, or hit the
network. Takes <1 second.

**Why `cd infra`:** The compose file uses relative paths (`../.env`,
`../services/signal`, etc.) so it has to be invoked from the `infra/`
directory, or with `-f infra/docker-compose.yaml` and adjusted paths.
Phase 0 picked the simpler convention.

---

## 6. `gh run list --branch main --limit 3`

**What:** The GitHub CLI. Lists recent Actions runs on the `main` branch.
You're looking for `completed success` on the most recent commit.

**Why:** Local checks can pass on your machine and still fail in CI
(different Python version, missing env var, Docker build context issue,
etc.). Checking CI status is the last mile — "not just green on my laptop,
green on the server that everyone trusts."

**Alternative:** `gh run watch` follows an in-progress run live. `gh run
view <id> --log` shows the full log of a failed run. `gh pr checks` does
the same for a PR's checks.

---

## The shape of the loop

The pattern across all six is the same:

1. **Static checks** (ruff, mypy) — fastest, no code execution. Run these
   constantly while editing.
2. **Tests** (pytest) — runs your code but not the infrastructure. Run
   before every commit.
3. **Config validation** (compose config) — catches broken glue without
   spinning anything up.
4. **CI status** (gh) — confirms the server agrees with you.

If any of those fail locally, don't commit. If the first three pass
locally but CI fails, something in your environment is lying to you —
usually a missing `uv sync`, a stale `.venv/`, or a divergent Python
version. Fix the gap, don't paper over it.

---

## Related config files

- `pyproject.toml` (root) — uv workspace, ruff config, mypy config,
  pytest config. Shared across all services.
- `services/<name>/pyproject.toml` — per-service dependencies and
  package metadata. Shared tooling config is inherited from the root.
- `uv.lock` — the pinned dependency graph. Committed. Regenerated by
  `uv lock` when you add or bump a dep.
- `.github/workflows/ci.yaml` — the CI equivalent of this doc. Keep them
  in sync.
