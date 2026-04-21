-- orders: every order submitted to the broker and its fill trail.
-- idempotency_key is unique so the executor can de-dupe retries.
-- status values are not pinned in Phase 0; services will define the set.

CREATE TABLE IF NOT EXISTS orders (
    order_id         text        PRIMARY KEY,
    proposal_id      uuid        NULL,
    ts_submitted     timestamptz NOT NULL,
    ts_filled        timestamptz NULL,
    symbol           text        NOT NULL,
    side             text        NOT NULL CHECK (side IN ('buy', 'sell')),
    qty              numeric     NOT NULL CHECK (qty > 0),
    fill_price       numeric     NULL CHECK (fill_price IS NULL OR fill_price > 0),
    status           text        NOT NULL,
    idempotency_key  text        NOT NULL UNIQUE
);

CREATE INDEX IF NOT EXISTS orders_ts_submitted_idx ON orders (ts_submitted DESC);
CREATE INDEX IF NOT EXISTS orders_symbol_idx       ON orders (symbol);
CREATE INDEX IF NOT EXISTS orders_status_idx       ON orders (status);
CREATE INDEX IF NOT EXISTS orders_proposal_id_idx  ON orders (proposal_id)
    WHERE proposal_id IS NOT NULL;
