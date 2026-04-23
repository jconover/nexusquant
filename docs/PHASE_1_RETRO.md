# Phase 1 retrospective

Three bullets per the definition-of-done in `docs/PHASE_1.md`.

## Surprises

- **alpaca-py hidden deps.** Installing `alpaca-py` succeeds, but
  importing anything from `alpaca.data.requests` fails without `pytz`
  on the path. `pytz` is not in alpaca-py's declared dependencies — it
  has to be added to every service that touches alpaca-py. It also
  pulls in full pandas + numpy transitively, which motivated the
  `types.Bar` dataclass wall: pandas never leaves the SDK boundary.
- **TimeFrame equality doesn't work.** `req.timeframe == TimeFrame.Day`
  is False even when the request was constructed with `TimeFrame.Day`,
  because each property access returns a fresh instance and the class
  doesn't define `__eq__` in a way that covers this. Stubs must
  compare `str(req.timeframe)` against `str(TimeFrame.Day)`. Bit me
  in `tests/unit/conftest.py` — worth a note in the alpaca-paper skill.
- **BackgroundTasks run synchronously in TestClient.** Didn't realize
  this upfront and half-designed around `asyncio.create_task`. The
  switch to `BackgroundTasks` made the DB-persistence tests clean:
  `TestClient.get(...).json()` returns *after* the background task has
  already run, so assertions on DB side-effects are deterministic.

## What I'd do differently

- **The custom `BarsCache` might be overkill.** I wrote it because
  `cachetools.TTLCache` has a single global TTL per instance and the
  phase spec asked for market-hours-aware TTLs. In hindsight, keeping
  the *short* TTL (15min daily, 60s minute) for both regimes would be
  barely worse — caches get refreshed more often outside market hours,
  but nothing is wrong — and cachetools would have been ~20 LOC
  shorter. I'd at least consider it next time before rolling my own.
- **Annotate the paper-only guard escape hatch upfront.** The
  `# paper-check: allow` convention showed up reactively after the CI
  grep false-positived on the validator that rejects the live URL.
  Documenting it in `CLAUDE.md` or `alpaca-paper/SKILL.md` from day
  one would save the next person the same back-and-forth.
- **Plan the shared-lib extraction at the same time as the first
  write.** `alpaca_clients.py`, `alpaca_logger.py`, `rate_limiter.py`
  are filed as "per-service now, shared lib in Phase 2" in `TODO.md`
  — but the module boundaries are already shaped to make promotion
  easy (no signal-specific logic, no cross-imports with service
  config beyond AlpacaSettings). Doing this consciously saved a later
  refactor.

## Updates that would help future phases

- **`alpaca-paper/SKILL.md` — add pytz gotcha.** Brief note that
  `pytz` must be in the service's declared deps even though alpaca-py
  is what needs it. Same note could flag the TimeFrame equality
  caveat for anyone stubbing Alpaca in tests.
- **`ARCHITECTURE.md` — reference the `Bar` dataclass wall pattern.**
  The rule "no pandas/numpy/SDK types in business logic, convert at
  the SDK boundary to a typed dataclass" is going to apply to every
  service that talks to Alpaca (executor, ingester). Worth
  generalizing from a Phase-1 implementation note to a project-level
  convention in ARCHITECTURE.md.
- **`ARCHITECTURE.md` — secret-management convention.** The
  `createSecret` boolean in the Helm chart (dev creates via values,
  prod leaves sealed-secrets to reconcile) works well and will
  repeat across every service's chart. Worth capturing so the next
  chart doesn't reinvent.
