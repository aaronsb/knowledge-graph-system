-- Migration 058: Pre-create all vertex and edge labels (prevents AGE race condition)
--
-- Apache AGE auto-creates labels on first CREATE/MERGE, but this is a DDL operation
-- (CREATE TABLE) that is not concurrent-safe. On a fresh install, parallel ingestion
-- threads can race to create the same label, causing:
--   "relation 'Source' already exists"
--
-- Fix: explicitly create all known vertex and edge labels at schema init time.
-- Uses DO blocks to check ag_catalog.ag_label before creating (AGE has no
-- CREATE VLABEL IF NOT EXISTS syntax).

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
            EXECUTE format(
                'SELECT * FROM cypher(''knowledge_graph'', $$ CREATE VLABEL %I $$) as (a agtype)',
                lbl
            );
            RAISE NOTICE 'Created vertex label: %', lbl;
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
            EXECUTE format(
                'SELECT * FROM cypher(''knowledge_graph'', $$ CREATE ELABEL %I $$) as (a agtype)',
                lbl
            );
            RAISE NOTICE 'Created edge label: %', lbl;
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
            EXECUTE format(
                'SELECT * FROM cypher(''knowledge_graph'', $$ CREATE ELABEL %I $$) as (a agtype)',
                lbl
            );
            RAISE NOTICE 'Created edge label: %', lbl;
        END IF;
    END LOOP;
END $$;

-- Record migration
INSERT INTO public.schema_migrations (version, name)
VALUES (58, 'precreate_graph_labels')
ON CONFLICT (version) DO NOTHING;
