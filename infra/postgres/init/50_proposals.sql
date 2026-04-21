-- proposals: proposal-mode order approval lifecycle. ts_decided and outcome
-- stay NULL until a human (or the TTL) resolves the proposal.

CREATE TABLE IF NOT EXISTS proposals (
    proposal_id   uuid        PRIMARY KEY,
    ts_created    timestamptz NOT NULL DEFAULT now(),
    ts_decided    timestamptz NULL,
    outcome       text        NULL
                              CHECK (outcome IS NULL
                                     OR outcome IN ('approved', 'rejected', 'expired')),
    payload_json  jsonb       NOT NULL
);

CREATE INDEX IF NOT EXISTS proposals_ts_created_idx ON proposals (ts_created DESC);
CREATE INDEX IF NOT EXISTS proposals_outcome_idx    ON proposals (outcome)
    WHERE outcome IS NOT NULL;
