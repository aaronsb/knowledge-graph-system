-- Migration 066: Ontology tombstones (#402 Defect B2)
--
-- A queued ingestion is operator intent: if annealing dissolves the target
-- between queue and execution, recreating the ontology and ingesting under
-- it is what the operator wanted. But there is one case where recreation
-- is wrong — when an operator deliberately removed the ontology and does
-- not want any later job to silently bring it back.
--
-- Tombstones make that distinction with a positive signal. An operator-
-- initiated delete writes a row here; annealing's dissolve_ontology()
-- path does NOT. The ingestion worker consults the table when its target
-- is missing:
--
--   missing + tombstoned   → fail with the "deliberately removed" string
--   missing + no tombstone → recreate and proceed (operator intent wins
--                            over background reorganization)
--
-- The tombstone is keyed by name (the same handle operators and ingest
-- jobs use). An operator who later wants to re-use the name removes the
-- tombstone explicitly — that is itself a positive signal.

CREATE TABLE IF NOT EXISTS kg_api.ontology_tombstones (
    name        VARCHAR(200) PRIMARY KEY,
    removed_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    removed_by  VARCHAR(100),
    reason      TEXT
);

COMMENT ON TABLE kg_api.ontology_tombstones IS
    'Positive operator-intent signal that an ontology was deliberately '
    'removed and must not be silently recreated by a subsequent ingest '
    '(#402 Defect B2). Operator-initiated delete writes a row; annealing '
    'dissolution does not.';

-- ============================================================================
-- Verification
-- ============================================================================

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT FROM information_schema.tables
        WHERE table_schema = 'kg_api'
          AND table_name   = 'ontology_tombstones'
    ) THEN
        RAISE EXCEPTION 'Migration failed: kg_api.ontology_tombstones not created';
    END IF;

    RAISE NOTICE 'Migration 066: ontology tombstones installed';
END $$;

-- ============================================================================
-- Record Migration
-- ============================================================================

INSERT INTO public.schema_migrations (version, name)
VALUES (66, 'ontology_tombstones')
ON CONFLICT (version) DO NOTHING;
