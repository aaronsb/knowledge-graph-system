-- Migration 063: Graph epoch event log (ADR-203)
--
-- Introduces a monotonic event sequence for graph mutations, distinct from
-- the count-checksum `graph_change_counter` (ADR-079). Each row represents
-- one logical mutation event (default granularity: one per ingestion job).
-- Instance nodes will gain `created_at_event_id` referencing this table,
-- enabling honest re-evidence-stream queries per concept.
--
-- Semantics:
--   event_id     - logical-time axis (monotonic, unique)
--   occurred_at  - wall-clock axis (always present, semantically meaningful
--                  only for kinds where it is — see `kind`)
--   kind         - discriminator for whether wall-clock has meaning
--                  ('ingestion'/'edit' = yes; 'reasoning'/'annealing' = forensic only)
--   actor        - user id, agent session id, system component
--   counter_after- snapshot of graph_change_counter post-event (cross-ref to ADR-079)

CREATE TABLE IF NOT EXISTS kg_api.graph_epochs (
    event_id      BIGSERIAL PRIMARY KEY,
    occurred_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    kind          TEXT NOT NULL CHECK (kind IN ('ingestion', 'reasoning', 'annealing', 'edit')),
    actor         TEXT,
    counter_after BIGINT,
    metadata      JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_graph_epochs_occurred_at
    ON kg_api.graph_epochs(occurred_at);

CREATE INDEX IF NOT EXISTS idx_graph_epochs_kind
    ON kg_api.graph_epochs(kind, occurred_at);

COMMENT ON TABLE kg_api.graph_epochs IS
    'ADR-203: Monotonic event log of graph mutations. Distinct from graph_change_counter (ADR-079) which is a composite cache-invalidation checksum.';

COMMENT ON COLUMN kg_api.graph_epochs.event_id IS
    'Monotonic logical-time id. Foreign-keyed by Instance.created_at_event_id.';

COMMENT ON COLUMN kg_api.graph_epochs.kind IS
    'ingestion | reasoning | annealing | edit. Determines whether occurred_at is semantically meaningful for the rows attributable to this event.';

-- Helper: record a new epoch event and return its event_id.
-- Called at the *start* of an ingestion job (or other mutation) so the
-- returned event_id can tag every node created during that unit of work.
CREATE OR REPLACE FUNCTION kg_api.record_graph_epoch(
    p_kind     TEXT,
    p_actor    TEXT DEFAULT NULL,
    p_metadata JSONB DEFAULT '{}'::jsonb
) RETURNS BIGINT AS $$
DECLARE
    v_event_id BIGINT;
    v_counter  BIGINT;
BEGIN
    SELECT counter INTO v_counter
    FROM public.graph_metrics
    WHERE metric_name = 'graph_change_counter';

    INSERT INTO kg_api.graph_epochs (kind, actor, counter_after, metadata)
    VALUES (p_kind, p_actor, v_counter, p_metadata)
    RETURNING event_id INTO v_event_id;

    RETURN v_event_id;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION kg_api.record_graph_epoch IS
    'ADR-203: Record a new graph-mutation event and return its event_id. Call at the start of an ingestion job (or other mutation transaction) so the returned id can tag nodes created during the unit of work.';

INSERT INTO public.schema_migrations (version, name)
VALUES (63, 'graph_epoch_events')
ON CONFLICT (version) DO NOTHING;
