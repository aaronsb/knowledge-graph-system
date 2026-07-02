-- ===========================================================================
-- Migration 043: Backfill content_type and storage_key on DocumentMeta Nodes
-- ===========================================================================
-- Date: 2026-01-29
-- Related: FUSE image support - content_type and storage_key were stored on
--          Source nodes but never on DocumentMeta nodes, causing GET /documents
--          to always return content_type="document" even for images, and
--          GET /documents/{id}/content to fail to find image binaries.
--
-- Copies content_type and storage_key from Source nodes to their parent
-- DocumentMeta nodes where the properties are missing.
--
-- This migration is idempotent - safe to run multiple times.
-- ===========================================================================

-- Set search path
LOAD 'age';
SET search_path = ag_catalog, kg_api, public;

-- ---------------------------------------------------------------------------
-- STEP 1: Backfill content_type from Source nodes to DocumentMeta nodes
-- ---------------------------------------------------------------------------

DO $migration$
DECLARE
    docs_updated INTEGER := 0;
BEGIN
    RAISE NOTICE 'Backfilling content_type on DocumentMeta nodes from Source nodes...';

    -- Find DocumentMeta nodes linked to image Source nodes that are missing
    -- content_type, and set it to 'image'
    EXECUTE format(
        'SELECT * FROM cypher(''knowledge_graph'', $cypher$
            MATCH (d:DocumentMeta)-[:HAS_SOURCE]->(s:Source)
            WHERE s.content_type = ''image'' AND d.content_type IS NULL
            SET d.content_type = ''image''
            RETURN count(DISTINCT d) as updated
        $cypher$) as (updated agtype)'
    ) INTO docs_updated;

    RAISE NOTICE 'Backfilled content_type=image on % DocumentMeta node(s)', docs_updated;
END $migration$;

-- ---------------------------------------------------------------------------
-- STEP 2: Backfill storage_key from Source nodes to DocumentMeta nodes
-- ---------------------------------------------------------------------------

DO $migration$
DECLARE
    docs_updated INTEGER := 0;
BEGIN
    RAISE NOTICE 'Backfilling storage_key on DocumentMeta nodes from Source nodes...';

    -- Copy storage_key from image Source nodes to their parent DocumentMeta
    -- Use the first Source node's storage_key (images have one source per doc)
    EXECUTE format(
        'SELECT * FROM cypher(''knowledge_graph'', $cypher$
            MATCH (d:DocumentMeta)-[:HAS_SOURCE]->(s:Source)
            WHERE s.content_type = ''image'' AND s.storage_key IS NOT NULL AND d.storage_key IS NULL
            SET d.storage_key = s.storage_key
            RETURN count(DISTINCT d) as updated
        $cypher$) as (updated agtype)'
    ) INTO docs_updated;

    RAISE NOTICE 'Backfilled storage_key on % DocumentMeta node(s)', docs_updated;
END $migration$;

-- ---------------------------------------------------------------------------
-- Verification
-- ---------------------------------------------------------------------------

DO $migration$
DECLARE
    total_with_type INTEGER := 0;
    total_with_key INTEGER := 0;
BEGIN
    EXECUTE format(
        'SELECT total::int FROM cypher(''knowledge_graph'', $cypher$
            MATCH (d:DocumentMeta)
            WHERE d.content_type IS NOT NULL
            RETURN count(d) as total
        $cypher$) as (total agtype)'
    ) INTO total_with_type;

    EXECUTE format(
        'SELECT total::int FROM cypher(''knowledge_graph'', $cypher$
            MATCH (d:DocumentMeta)
            WHERE d.storage_key IS NOT NULL
            RETURN count(d) as total
        $cypher$) as (total agtype)'
    ) INTO total_with_key;

    RAISE NOTICE 'DocumentMeta nodes with content_type set: %', total_with_type;
    RAISE NOTICE 'DocumentMeta nodes with storage_key set: %', total_with_key;
END $migration$;

-- ---------------------------------------------------------------------------
-- Migration Tracking
-- ---------------------------------------------------------------------------

INSERT INTO public.schema_migrations (version, name)
VALUES (43, 'backfill_document_meta_content_type')
ON CONFLICT (version) DO NOTHING;

-- ===========================================================================
-- End of Migration 043
-- ===========================================================================
