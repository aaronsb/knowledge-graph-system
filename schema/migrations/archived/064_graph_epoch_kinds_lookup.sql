-- Migration 064: Replace graph_epochs.kind CHECK constraint with a lookup table.
--
-- ADR-203 §Decision §1 introduced graph_epochs.kind with a hard-coded
-- CHECK constraint (`kind IN ('ingestion','reasoning','annealing','edit')`).
-- The constraint was also duplicated, in spirit, by the formatter's
-- `KINDS_WITH_WALLCLOCK` set in cli/src/mcp/formatters/epoch.ts — both
-- need to stay in sync as the system grows new event kinds.
--
-- This migration:
--   1. Adds kg_api.graph_epoch_kinds — one row per kind with a
--      `semantic_wallclock` flag (the discriminator from ADR-203 §Decision
--      that says "is occurred_at semantically primary for this kind?").
--   2. Seeds the four kinds from ADR-203.
--   3. Drops the closed-set CHECK on graph_epochs.kind.
--   4. Adds a foreign key from graph_epochs.kind into the lookup table so
--      invalid kinds are still rejected, but new kinds are added by
--      INSERT rather than by ALTER CONSTRAINT migration.
--
-- The semantic_wallclock flag becomes the single source of truth, exposed
-- via the lifetime / epochs API responses so the TS formatter stops
-- duplicating the set.

CREATE TABLE IF NOT EXISTS kg_api.graph_epoch_kinds (
    kind                TEXT PRIMARY KEY,
    semantic_wallclock  BOOLEAN NOT NULL,
    description         TEXT
);

COMMENT ON TABLE kg_api.graph_epoch_kinds IS
    'ADR-203: Discriminator for graph_epochs.kind. semantic_wallclock distinguishes events whose occurred_at is semantically primary (ingestion, edit) from those where it is forensic-only (reasoning, annealing).';

COMMENT ON COLUMN kg_api.graph_epoch_kinds.semantic_wallclock IS
    'When TRUE, occurred_at is the meaningful timestamp for downstream consumers. When FALSE, occurred_at is recorded for audit/forensics but should not drive time-based queries on the resulting graph state.';

INSERT INTO kg_api.graph_epoch_kinds (kind, semantic_wallclock, description) VALUES
    ('ingestion',  TRUE,  'External corpus arrived via the ingestion pipeline.'),
    ('edit',       TRUE,  'Explicit manual mutation by an operator.'),
    ('reasoning',  FALSE, 'Agent-driven reasoning session mutated the graph internally.'),
    ('annealing',  FALSE, 'Ontology annealing pass mutated the graph internally.')
ON CONFLICT (kind) DO NOTHING;

-- Drop the closed-set CHECK constraint added by migration 063.
-- The constraint name was assigned by Postgres; find it dynamically.
DO $$
DECLARE
    v_constraint_name TEXT;
BEGIN
    SELECT conname INTO v_constraint_name
    FROM pg_constraint
    WHERE conrelid = 'kg_api.graph_epochs'::regclass
      AND contype = 'c'
      AND pg_get_constraintdef(oid) LIKE '%kind = ANY%';

    IF v_constraint_name IS NOT NULL THEN
        EXECUTE format(
            'ALTER TABLE kg_api.graph_epochs DROP CONSTRAINT %I',
            v_constraint_name
        );
    END IF;
END $$;

-- Replace with a foreign key.
ALTER TABLE kg_api.graph_epochs
    ADD CONSTRAINT graph_epochs_kind_fkey
    FOREIGN KEY (kind)
    REFERENCES kg_api.graph_epoch_kinds (kind)
    ON UPDATE CASCADE
    ON DELETE RESTRICT;

INSERT INTO public.schema_migrations (version, name)
VALUES (64, 'graph_epoch_kinds_lookup')
ON CONFLICT (version) DO NOTHING;
