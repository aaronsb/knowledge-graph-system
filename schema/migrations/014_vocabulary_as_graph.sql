-- ===========================================================================
-- Migration 014: Vocabulary as Graph Nodes (ADR-048 Phase 3)
-- ===========================================================================
-- Date: 2025-10-27
-- Related: ADR-048 (Vocabulary Metadata as First-Class Graph), ADR-047
--
-- Creates :VocabType and :VocabCategory nodes in Apache AGE graph from
-- existing kg_api.relationship_vocabulary table data.
--
-- Strategy: Direct cypher queries to create nodes from SQL data
-- ===========================================================================

-- Set search path
LOAD 'age';
SET search_path = ag_catalog, kg_api, public;

-- ---------------------------------------------------------------------------
-- STEP 1: Create VocabCategory Nodes
-- ---------------------------------------------------------------------------

DO $migration$
DECLARE
    category_rec RECORD;
    cat_count INTEGER := 0;
BEGIN
    RAISE NOTICE 'Creating VocabCategory nodes...';

    FOR category_rec IN
        SELECT DISTINCT
            category,
            COUNT(*) as type_count
        FROM kg_api.relationship_vocabulary
        WHERE is_active = true AND category IS NOT NULL
        GROUP BY category
        ORDER BY category
    LOOP
        -- Build and execute cypher query with EXECUTE (using MERGE for idempotency)
        EXECUTE format(
            'SELECT * FROM cypher(''knowledge_graph'', $cypher$ MERGE (c:VocabCategory {name: ''%s''}) SET c.type_count = %s $cypher$) as (c agtype)',
            replace(category_rec.category, '''', ''''''),
            category_rec.type_count
        );

        cat_count := cat_count + 1;
    END LOOP;

    RAISE NOTICE 'Created % VocabCategory nodes', cat_count;
END $migration$;

-- ---------------------------------------------------------------------------
-- STEP 2: Create VocabType Nodes
-- ---------------------------------------------------------------------------

DO $migration$
DECLARE
    vocab_rec RECORD;
    node_count INTEGER := 0;
BEGIN
    RAISE NOTICE 'Creating VocabType nodes...';

    FOR vocab_rec IN
        SELECT
            relationship_type,
            category,
            is_active,
            is_builtin,
            COALESCE(usage_count, 0) as usage_count
        FROM kg_api.relationship_vocabulary
        WHERE relationship_type IS NOT NULL
        ORDER BY relationship_type
    LOOP
        -- Build and execute cypher query with EXECUTE (using MERGE for idempotency)
        EXECUTE format(
            'SELECT * FROM cypher(''knowledge_graph'', $cypher$ MERGE (v:VocabType {name: ''%s''}) SET v.is_active = %L, v.is_builtin = %L, v.usage_count = %s $cypher$) as (v agtype)',
            replace(vocab_rec.relationship_type, '''', ''''''),
            vocab_rec.is_active,
            vocab_rec.is_builtin,
            vocab_rec.usage_count
        );

        node_count := node_count + 1;

        -- Show progress every 10 nodes
        IF node_count % 10 = 0 THEN
            RAISE NOTICE '  Created % VocabType nodes...', node_count;
        END IF;
    END LOOP;

    RAISE NOTICE 'Created % VocabType nodes total', node_count;
END $migration$;

-- ---------------------------------------------------------------------------
-- STEP 3: Create IN_CATEGORY Relationships
-- ---------------------------------------------------------------------------

DO $migration$
DECLARE
    vocab_rec RECORD;
    rel_count INTEGER := 0;
BEGIN
    RAISE NOTICE 'Creating IN_CATEGORY relationships...';

    FOR vocab_rec IN
        SELECT
            relationship_type,
            category
        FROM kg_api.relationship_vocabulary
        WHERE relationship_type IS NOT NULL
          AND category IS NOT NULL
        ORDER BY relationship_type
    LOOP
        -- Build and execute cypher query with EXECUTE (using MERGE for idempotency)
        EXECUTE format(
            'SELECT * FROM cypher(''knowledge_graph'', $cypher$ MATCH (v:VocabType {name: ''%s''}), (c:VocabCategory {name: ''%s''}) MERGE (v)-[:IN_CATEGORY]->(c) $cypher$) as (result agtype)',
            replace(vocab_rec.relationship_type, '''', ''''''),
            replace(vocab_rec.category, '''', '''''')
        );

        rel_count := rel_count + 1;

        -- Show progress every 10 relationships
        IF rel_count % 10 = 0 THEN
            RAISE NOTICE '  Created % IN_CATEGORY relationships...', rel_count;
        END IF;
    END LOOP;

    RAISE NOTICE 'Created % IN_CATEGORY relationships total', rel_count;
END $migration$;

-- ---------------------------------------------------------------------------
-- STEP 4: Verification
-- ---------------------------------------------------------------------------

DO $migration$
DECLARE
    vocab_count INTEGER;
    cat_count INTEGER;
    rel_count INTEGER;
    sql_vocab_count INTEGER;
BEGIN
    RAISE NOTICE '';
    RAISE NOTICE 'Verifying vocabulary graph...';
    RAISE NOTICE '=====================================';

    -- Count VocabType nodes in graph
    EXECUTE 'SELECT total::int FROM cypher(''knowledge_graph'', $cypher$ MATCH (v:VocabType) RETURN count(v) as total $cypher$) as (total agtype)'
    INTO vocab_count;

    -- Count vocabulary types in SQL
    SELECT COUNT(*) INTO sql_vocab_count
    FROM kg_api.relationship_vocabulary;

    RAISE NOTICE '  VocabType nodes in graph: %', vocab_count;
    RAISE NOTICE '  Vocabulary types in SQL:   %', sql_vocab_count;

    -- Count VocabCategory nodes
    EXECUTE 'SELECT total::int FROM cypher(''knowledge_graph'', $cypher$ MATCH (c:VocabCategory) RETURN count(c) as total $cypher$) as (total agtype)'
    INTO cat_count;
    RAISE NOTICE '  VocabCategory nodes:       %', cat_count;

    -- Count relationships
    EXECUTE 'SELECT total::int FROM cypher(''knowledge_graph'', $cypher$ MATCH ()-[r:IN_CATEGORY]->() RETURN count(r) as total $cypher$) as (total agtype)'
    INTO rel_count;
    RAISE NOTICE '  IN_CATEGORY relationships: %', rel_count;

    RAISE NOTICE '=====================================';
    RAISE NOTICE 'Vocabulary graph sync complete!';
    RAISE NOTICE '';
END $migration$;

-- ---------------------------------------------------------------------------
-- Migration Tracking
-- ---------------------------------------------------------------------------

INSERT INTO public.schema_migrations (version, name)
VALUES (14, 'vocabulary_as_graph')
ON CONFLICT (version) DO NOTHING;

-- ===========================================================================
-- End of Migration 014
-- ===========================================================================
