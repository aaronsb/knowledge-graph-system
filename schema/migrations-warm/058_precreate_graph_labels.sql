-- Migration 058: Pre-create all vertex and edge labels (prevents AGE race condition)
--
-- Apache AGE auto-creates labels on first CREATE/MERGE, but this is a DDL operation
-- (CREATE TABLE) that is not concurrent-safe. On a fresh install, parallel ingestion
-- threads can race to create the same label, causing:
--   "relation 'Source' already exists"
--
-- Fix: explicitly create all known vertex and edge labels at schema init time
-- via ag_catalog.create_vlabel()/create_elabel() (AGE's label API — cypher has
-- no CREATE VLABEL statement). Uses DO blocks to check ag_catalog.ag_label
-- before creating, since the functions error on existing labels.
--
-- Note: Uses EXCEPTION handlers so label creation failures (e.g., AGE not fully
-- initialized on cold start) are logged as warnings rather than aborting the migration.
--
-- History: the original version of this file EXECUTEd
-- `cypher(..., $$ CREATE VLABEL ... $$)` — the inner $$ terminated the outer
-- DO $$ quoting, so the file never parsed and version 58 was never recorded
-- anywhere. Rewritten 2026-07-01; safe to modify in place because it never
-- successfully applied.

LOAD 'age';
SET search_path = ag_catalog, "$user", public;

-- ============================================================
-- Vertex labels
-- ============================================================

DO $$
DECLARE
    labels text[] := ARRAY['Concept', 'Source', 'Instance', 'Ontology', 'DocumentMeta', 'VocabType', 'VocabCategory'];
    lbl text;
BEGIN
    FOREACH lbl IN ARRAY labels LOOP
        IF NOT EXISTS (
            SELECT 1 FROM ag_catalog.ag_label l
            JOIN ag_catalog.ag_graph g ON l.graph = g.graphid
            WHERE g.name = 'knowledge_graph' AND l.name = lbl AND l.kind = 'v'
        ) THEN
            BEGIN
                -- create_vlabel takes cstring args; text needs an explicit cast
                PERFORM ag_catalog.create_vlabel('knowledge_graph', lbl::cstring);
                RAISE NOTICE 'Created vertex label: %', lbl;
            EXCEPTION WHEN OTHERS THEN
                RAISE NOTICE 'Could not create vertex label % (will be created on first use): %', lbl, SQLERRM;
            END;
        END IF;
    END LOOP;
END $$;

-- ============================================================
-- Static edge labels (infrastructure edges)
-- ============================================================

DO $$
DECLARE
    labels text[] := ARRAY[
        'APPEARS', 'EVIDENCED_BY', 'FROM_SOURCE', 'SCOPED_BY',
        'HAS_SOURCE', 'IN_CATEGORY', 'ANCHORED_BY',
        'OVERLAPS', 'SPECIALIZES', 'GENERALIZES'
    ];
    lbl text;
BEGIN
    FOREACH lbl IN ARRAY labels LOOP
        IF NOT EXISTS (
            SELECT 1 FROM ag_catalog.ag_label l
            JOIN ag_catalog.ag_graph g ON l.graph = g.graphid
            WHERE g.name = 'knowledge_graph' AND l.name = lbl AND l.kind = 'e'
        ) THEN
            BEGIN
                PERFORM ag_catalog.create_elabel('knowledge_graph', lbl::cstring);
                RAISE NOTICE 'Created edge label: %', lbl;
            EXCEPTION WHEN OTHERS THEN
                RAISE NOTICE 'Could not create edge label % (will be created on first use): %', lbl, SQLERRM;
            END;
        END IF;
    END LOOP;
END $$;

-- ============================================================
-- Vocabulary edge labels (30 canonical relationship types)
-- These are dynamically created during ingestion, but pre-creating
-- them eliminates the concurrent DDL race on first use.
-- ============================================================

DO $$
DECLARE
    labels text[] := ARRAY[
        -- logical_truth
        'IMPLIES', 'CONTRADICTS', 'PRESUPPOSES', 'EQUIVALENT_TO',
        -- causal
        'CAUSES', 'ENABLES', 'PREVENTS', 'INFLUENCES', 'RESULTS_FROM',
        -- structural
        'PART_OF', 'CONTAINS', 'COMPOSED_OF', 'SUBSET_OF', 'INSTANCE_OF',
        -- evidential
        'SUPPORTS', 'REFUTES', 'EXEMPLIFIES', 'MEASURED_BY',
        -- similarity
        'SIMILAR_TO', 'ANALOGOUS_TO', 'CONTRASTS_WITH', 'OPPOSITE_OF',
        -- temporal
        'PRECEDES', 'CONCURRENT_WITH', 'EVOLVES_INTO',
        -- functional
        'USED_FOR', 'REQUIRES', 'PRODUCES', 'REGULATES',
        -- meta
        'DEFINED_AS', 'CATEGORIZED_AS'
    ];
    lbl text;
BEGIN
    FOREACH lbl IN ARRAY labels LOOP
        IF NOT EXISTS (
            SELECT 1 FROM ag_catalog.ag_label l
            JOIN ag_catalog.ag_graph g ON l.graph = g.graphid
            WHERE g.name = 'knowledge_graph' AND l.name = lbl AND l.kind = 'e'
        ) THEN
            BEGIN
                PERFORM ag_catalog.create_elabel('knowledge_graph', lbl::cstring);
                RAISE NOTICE 'Created edge label: %', lbl;
            EXCEPTION WHEN OTHERS THEN
                RAISE NOTICE 'Could not create edge label % (will be created on first use): %', lbl, SQLERRM;
            END;
        END IF;
    END LOOP;
END $$;

-- Record migration
INSERT INTO public.schema_migrations (version, name)
VALUES (58, 'precreate_graph_labels')
ON CONFLICT (version) DO NOTHING;
