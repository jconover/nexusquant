-- Extensions required by the audit schema.
-- timescaledb: hypertable support for the signals table.
-- pgcrypto:    gen_random_uuid() for surrogate primary keys.

CREATE EXTENSION IF NOT EXISTS timescaledb;
CREATE EXTENSION IF NOT EXISTS pgcrypto;
