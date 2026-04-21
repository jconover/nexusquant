-- risk_events: structured log of guard verdicts. 'rejection' and 'approval'
-- cover the per-order path; 'circuit_breaker' covers portfolio-level halts
-- (e.g. daily drawdown tripped).

CREATE TABLE IF NOT EXISTS risk_events (
    risk_event_id  uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    ts             timestamptz NOT NULL DEFAULT now(),
    kind           text        NOT NULL
                               CHECK (kind IN ('rejection', 'approval', 'circuit_breaker')),
    reason         text        NOT NULL,
    context_json   jsonb       NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS risk_events_ts_idx   ON risk_events (ts DESC);
CREATE INDEX IF NOT EXISTS risk_events_kind_idx ON risk_events (kind);
