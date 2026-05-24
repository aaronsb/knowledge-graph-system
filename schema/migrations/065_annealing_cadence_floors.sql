-- Migration 065: Raise annealing cadence floors (#402 Defect C)
--
-- The shipping defaults emit annealing cycles too aggressively relative to
-- typical operator activity. Cycles evaluate brand-new or near-empty
-- ontologies before they have accumulated enough signal to judge — which
-- both wastes LLM evaluations and widens the race window with the
-- ingestion queue (the very race that #402 Defect A blocks).
--
-- Two new per-ontology floors gate cycle eligibility:
--
-- 1. min_ontology_age_epochs = 3
--    An ontology must exist for at least three epoch ticks (a tick fires
--    after each ingestion job's epoch increment) before annealing can
--    judge it. Three is the smallest floor that survives a single batch:
--    an ontology created mid-batch is still maturing while remaining jobs
--    in the batch land, and the worker should not act on it until the
--    batch is settled.
--
-- 2. min_ontology_concept_count = 5
--    An ontology must hold at least five concepts before annealing can
--    judge it. Below five, scores like protection and coherence are
--    dominated by per-concept noise rather than ontology-level structure.
--    Five is small enough to catch real-but-sparse ontologies while
--    excluding stubs and partial-ingest snapshots.
--
-- These are *new* keys — no existing operator can have tuned them. INSERT
-- ... ON CONFLICT DO NOTHING leaves operator-tuned values alone (the
-- pattern already used by 047's seed block); the existing-key floors
-- (epoch_interval, demotion_threshold, promotion_min_degree, max_proposals)
-- are intentionally not changed here so this migration does not silently
-- overwrite operators who have already tuned them.

INSERT INTO kg_api.annealing_options (key, value, description) VALUES
    ('min_ontology_age_epochs',
     '3',
     'Ontology must exist for at least this many epochs before annealing '
     'evaluates it. Prevents acting on ontologies still settling from '
     'recent ingestion (#402 Defect C).'),
    ('min_ontology_concept_count',
     '5',
     'Ontology must hold at least this many concepts before annealing '
     'evaluates it. Below this floor, scores are dominated by per-concept '
     'noise rather than ontology structure (#402 Defect C).')
ON CONFLICT (key) DO NOTHING;

-- ============================================================================
-- Verification
-- ============================================================================

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT FROM kg_api.annealing_options WHERE key = 'min_ontology_age_epochs'
    ) THEN
        RAISE EXCEPTION 'Migration failed: min_ontology_age_epochs not seeded';
    END IF;

    IF NOT EXISTS (
        SELECT FROM kg_api.annealing_options WHERE key = 'min_ontology_concept_count'
    ) THEN
        RAISE EXCEPTION 'Migration failed: min_ontology_concept_count not seeded';
    END IF;

    RAISE NOTICE 'Migration 065: annealing cadence floors installed';
END $$;

-- ============================================================================
-- Record Migration
-- ============================================================================

INSERT INTO public.schema_migrations (version, name)
VALUES (65, 'annealing_cadence_floors')
ON CONFLICT (version) DO NOTHING;
