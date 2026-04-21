# ingester

Ingester service. Subscribes to the Alpaca WebSocket for the current watchlist
symbols and publishes normalized tick events onto Redis Streams for the signal
service to consume. **Phase 0: stub with `/healthz` and `/readyz` only.**
