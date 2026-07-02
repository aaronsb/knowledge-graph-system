-- ===========================================================================
-- Migration 044: Ontology Graph Nodes (ADR-200 Phase 1)
-- ===========================================================================
-- Date: 2026-01-29
-- Related: ADR-200 (Annealing Ontologies)
--
-- Promotes ontologies from string properties to first-class graph nodes.
-- Creates :Ontology nodes from existing s.document values on Source nodes,
-- and :SCOPED_BY edges linking each Source to its Ontology.
--
-- Existing s.document strings are preserved as a denormalized cache.
-- :Ontology nodes and :SCOPED_BY edges become the source of truth for
-- new code paths. Existing queries that filter by s.document continue
-- working unchanged.
--
-- This migration is idempotent — safe to run multiple times.
-- ===========================================================================

-- Set search path
LOAD 'age';
SET search_path = ag_catalog, kg_api, public;

-- ---------------------------------------------------------------------------
-- STEP 1: Create :Ontology nodes from distinct s.document values
-- ---------------------------------------------------------------------------

DO $migration$
DECLARE
    doc_rec RECORD;
    node_count INTEGER := 0;
    skip_count INTEGER := 0;
    current_epoch BIGINT := 0;
    new_id TEXT;
    exists_count INTEGER;
BEGIN
    RAISE NOTICE 'ADR-200 Phase 1: Creating :Ontology nodes...';

    -- Get current ingestion epoch for creation_epoch
    BEGIN
        SELECT counter INTO current_epoch
        FROM graph_metrics
        WHERE metric_name = 'document_ingestion_counter';
    EXCEPTION WHEN undefined_table THEN
        current_epoch := 0;
    END;
    current_epoch := COALESCE(current_epoch, 0);

    RAISE NOTICE '  Current ingestion epoch: %', current_epoch;

    -- Get distinct ontology names from Source nodes
    FOR doc_rec IN
        EXECUTE format(
            'SELECT trim(both ''"'' from name::text) as name
             FROM cypher(''knowledge_graph'', $cypher$
                MATCH (s:Source)
                WHERE s.document IS NOT NULL
                RETURN DISTINCT s.document as name
             $cypher$) as (name agtype)'
        )
    LOOP
        -- Check if Ontology node already exists (idempotency)
        EXECUTE format(
            'SELECT c::int FROM (
                SELECT count(*) as c FROM cypher(''knowledge_graph'', $cypher$
                    MATCH (o:Ontology {name: ''%s''})
                    RETURN o
                $cypher$) as (o agtype)
            ) sub',
            replace(doc_rec.name, '''', '''''')
        ) INTO exists_count;

        IF exists_count = 0 THEN
            new_id := 'ont_' || gen_random_uuid()::text;

            EXECUTE format(
                'SELECT * FROM cypher(''knowledge_graph'', $cypher$
                    CREATE (o:Ontology {
                        ontology_id: ''%s'',
                        name: ''%s'',
                        lifecycle_state: ''active'',
                        creation_epoch: %s
                    })
                $cypher$) as (o agtype)',
                new_id,
                replace(doc_rec.name, '''', ''''''),
                current_epoch
            );

            node_count := node_count + 1;
            RAISE NOTICE '  Created Ontology: % (id: %)', doc_rec.name, new_id;
        ELSE
            skip_count := skip_count + 1;
            RAISE NOTICE '  Already exists: %', doc_rec.name;
        END IF;
    END LOOP;

    RAISE NOTICE 'Created % Ontology nodes (% already existed)', node_count, skip_count;
END $migration$;

-- ---------------------------------------------------------------------------
-- STEP 2: Create :SCOPED_BY edges from Source → Ontology
-- ---------------------------------------------------------------------------

DO $migration$
DECLARE
    doc_rec RECORD;
    linked INTEGER;
    total_linked INTEGER := 0;
BEGIN
    RAISE NOTICE '';
    RAISE NOTICE 'Creating :SCOPED_BY edges from Source → Ontology...';

    -- Process one ontology at a time for predictable performance
    FOR doc_rec IN
        EXECUTE format(
            'SELECT trim(both ''"'' from name::text) as name
             FROM cypher(''knowledge_graph'', $cypher$
                MATCH (o:Ontology)
                RETURN o.name as name
             $cypher$) as (name agtype)'
        )
    LOOP
        -- Create SCOPED_BY edges for all Source nodes in this ontology
        -- MERGE is idempotent — existing edges are not duplicated
        EXECUTE format(
            'SELECT count(*)::int FROM cypher(''knowledge_graph'', $cypher$
                MATCH (s:Source {document: ''%s''})
                MATCH (o:Ontology {name: ''%s''})
                MERGE (s)-[:SCOPED_BY]->(o)
                RETURN s
            $cypher$) as (s agtype)',
            replace(doc_rec.name, '''', ''''''),
            replace(doc_rec.name, '''', '''''')
        ) INTO linked;

        total_linked := total_linked + COALESCE(linked, 0);
        RAISE NOTICE '  Linked % sources → Ontology "%"', COALESCE(linked, 0), doc_rec.name;
    END LOOP;

    RAISE NOTICE 'Created SCOPED_BY edges for % total sources', total_linked;
END $migration$;

-- ---------------------------------------------------------------------------
-- STEP 3: Add graph_metrics entry for ontology tracking
-- ---------------------------------------------------------------------------

INSERT INTO graph_metrics (metric_name, counter, last_measured_counter, notes)
VALUES
    ('ontology_count', 0, 0, 'Current total ontology node count'),
    ('ontology_creation_counter', 0, 0, 'Ontologies created (promoted or explicit)'),
    ('ontology_deletion_counter', 0, 0, 'Ontologies deleted or demoted')
ON CONFLICT (metric_name) DO NOTHING;

-- ---------------------------------------------------------------------------
-- STEP 4: Verification
-- ---------------------------------------------------------------------------

DO $migration$
DECLARE
    ontology_count INTEGER;
    scoped_count INTEGER;
    source_count INTEGER;
    unscoped_count INTEGER;
BEGIN
    RAISE NOTICE '';
    RAISE NOTICE 'Verifying ontology graph structure...';
    RAISE NOTICE '=====================================';

    -- Count Ontology nodes
    EXECUTE 'SELECT count(*)::int FROM cypher(''knowledge_graph'', $cypher$
        MATCH (o:Ontology) RETURN o
    $cypher$) as (o agtype)'
    INTO ontology_count;
    RAISE NOTICE '  Ontology nodes:        %', ontology_count;

    -- Count SCOPED_BY edges
    EXECUTE 'SELECT count(*)::int FROM cypher(''knowledge_graph'', $cypher$
        MATCH ()-[r:SCOPED_BY]->() RETURN r
    $cypher$) as (r agtype)'
    INTO scoped_count;
    RAISE NOTICE '  SCOPED_BY edges:       %', scoped_count;

    -- Count total Source nodes
    EXECUTE 'SELECT count(*)::int FROM cypher(''knowledge_graph'', $cypher$
        MATCH (s:Source) RETURN s
    $cypher$) as (s agtype)'
    INTO source_count;
    RAISE NOTICE '  Total Source nodes:     %', source_count;

    -- Count Source nodes WITHOUT SCOPED_BY edge (should be 0)
    -- NOTE: NOT EXISTS { } subquery syntax may not be supported in all AGE
    -- versions. Wrap in its own handler so a Cypher parse error here doesn't
    -- roll back the verification block — the migration data is already committed.
    BEGIN
        EXECUTE 'SELECT count(*)::int FROM cypher(''knowledge_graph'', $cypher$
            MATCH (s:Source)
            WHERE s.document IS NOT NULL AND NOT EXISTS {
                MATCH (s)-[:SCOPED_BY]->(:Ontology)
            }
            RETURN s
        $cypher$) as (s agtype)'
        INTO unscoped_count;

        IF unscoped_count > 0 THEN
            RAISE WARNING '  Unscoped sources:      % (sources with document but no SCOPED_BY edge)', unscoped_count;
        ELSE
            RAISE NOTICE '  Unscoped sources:      0 (all sources linked)';
        END IF;
    EXCEPTION WHEN OTHERS THEN
        RAISE NOTICE '  Unscoped sources:      (skipped — NOT EXISTS subquery not supported by this AGE version)';
    END;

    RAISE NOTICE '=====================================';

    -- Update ontology_count snapshot
    UPDATE graph_metrics
    SET counter = ontology_count, updated_at = CURRENT_TIMESTAMP
    WHERE metric_name = 'ontology_count';
END $migration$;

-- ---------------------------------------------------------------------------
-- Migration Tracking
-- ---------------------------------------------------------------------------

INSERT INTO public.schema_migrations (version, name)
VALUES (44, 'ontology_graph_nodes')
ON CONFLICT (version) DO NOTHING;

-- ===========================================================================
-- End of Migration 044
-- ===========================================================================
