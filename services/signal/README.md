# signal

Signal service. Consumes price ticks from Redis Streams and maintains rolling
technical indicators per watchlist symbol; exposes `get_signal` on the MCP
tool surface. **Phase 0: stub with `/healthz` and `/readyz` only.**
