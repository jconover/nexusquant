# risk

Risk service. Validates every proposed order against deterministic server-side
guardrails (symbol allowlist, hourly/daily budgets, per-symbol cooldowns,
drawdown circuit breaker) and routes the request to auto-execute, proposal
mode, or outright rejection. **Phase 0: stub with `/healthz` and `/readyz`
only.**
