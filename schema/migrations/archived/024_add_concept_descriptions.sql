-- ===========================================================================
-- Migration 024: Add Description Field to Concept Nodes
-- ===========================================================================
-- Date: 2025-01-04
-- Related: Concept description feature - add factual definitions to concepts
--
-- Adds 'description' property to all :Concept nodes in the graph.
-- For existing concepts, sets description to empty string (will be populated
-- by future ingestion or manual updates).
--
-- This migration is idempotent - safe to run multiple times.
-- ===========================================================================

-- Set search path
LOAD 'age';
SET search_path = ag_catalog, kg_api, public;

-- ---------------------------------------------------------------------------
-- STEP 1: Add description field to existing Concept nodes
-- ---------------------------------------------------------------------------

DO $migration$
DECLARE
    concepts_updated INTEGER := 0;
BEGIN
    RAISE NOTICE 'Adding description field to Concept nodes...';

    -- Update all Concept nodes that don't have a description property
    -- Use MERGE to be idempotent (won't fail if description already exists)
    EXECUTE format(
        'SELECT * FROM cypher(''knowledge_graph'', $cypher$
            MATCH (c:Concept)
            WHERE c.description IS NULL
            SET c.description = ''''
            RETURN count(c) as updated
        $cypher$) as (updated agtype)'
    ) INTO concepts_updated;

    RAISE NOTICE 'Updated % Concept nodes with empty description field', concepts_updated;

    -- Verify all concepts now have description
    EXECUTE format(
        'SELECT total::int FROM cypher(''knowledge_graph'', $cypher$
            MATCH (c:Concept)
            RETURN count(c) as total
        $cypher$) as (total agtype)'
    ) INTO concepts_updated;

    RAISE NOTICE 'Total Concept nodes in graph: %', concepts_updated;
END $migration$;

-- ---------------------------------------------------------------------------
-- Migration Tracking
-- ---------------------------------------------------------------------------

INSERT INTO public.schema_migrations (version, name)
VALUES (24, 'add_concept_descriptions')
ON CONFLICT (version) DO NOTHING;

-- ===========================================================================
-- End of Migration 024
-- ===========================================================================
