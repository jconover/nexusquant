# watchlist

Watchlist service. Loads today's `candidates.parquet` (produced nightly on
orion) at market open and exposes `get_watchlist` on the MCP tool surface.
**Phase 0: stub with `/healthz` and `/readyz` only.**
