-- signals: rolling indicator output and rule verdict per symbol.
-- Hypertable partitioned on ts. TimescaleDB requires the partitioning
-- column to participate in any unique/primary key, so the PK is (symbol, ts).

CREATE TABLE IF NOT EXISTS signals (
    symbol          text        NOT NULL,
    ts              timestamptz NOT NULL,
    indicator_json  jsonb       NOT NULL,
    rule_result     text        NOT NULL
                                CHECK (rule_result IN ('buy', 'sell', 'hold')),
    PRIMARY KEY (symbol, ts)
);

SELECT create_hypertable(
    'signals',
    'ts',
    if_not_exists => TRUE,
    migrate_data  => TRUE
);

CREATE INDEX IF NOT EXISTS signals_ts_idx ON signals (ts DESC);
