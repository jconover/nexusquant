-- decisions: one row per place_paper_order call, recording the agent's
-- intent before risk routes it. proposal_id is set only when the decision
-- was routed into proposal mode; auto decisions leave it NULL.

CREATE TABLE IF NOT EXISTS decisions (
    decision_id           uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    proposal_id           uuid        NULL,
    ts                    timestamptz NOT NULL DEFAULT now(),
    symbol                text        NOT NULL,
    side                  text        NOT NULL CHECK (side IN ('buy', 'sell')),
    qty                   numeric     NOT NULL CHECK (qty > 0),
    notional              numeric     NOT NULL CHECK (notional >= 0),
    mode                  text        NOT NULL CHECK (mode IN ('auto', 'proposal')),
    agent_reasoning_text  text        NULL
);

CREATE INDEX IF NOT EXISTS decisions_ts_idx     ON decisions (ts DESC);
CREATE INDEX IF NOT EXISTS decisions_symbol_idx ON decisions (symbol);
CREATE UNIQUE INDEX IF NOT EXISTS decisions_proposal_id_idx
    ON decisions (proposal_id)
    WHERE proposal_id IS NOT NULL;
