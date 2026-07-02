-- Migration: 078_seed_primordial_ontology
-- Description: Seed the reserved 'primordial' ontology pool on clean install
-- Issue: #505
-- ADR: ADR-200 (Annealing Ontologies)
--
-- The 'primordial' pool is the reserved default ontology that unroutable
-- sources fall into. It was only created LAZILY — the first time an annealing
-- cycle ran (proposal_executor._ensure_primordial_pool) — so a fresh instance
-- had no primordial pool until then. Seed it eagerly at install so it always
-- exists. Idempotent: creates the node only if absent.
--
-- (Restore also ensures primordial via AGEClient.rehydrate_projection_layers,
-- since a clone-style restore can replace this freshly-seeded graph.)

LOAD 'age';
SET search_path = ag_catalog, kg_api, public;

DO $migration$
DECLARE
    exists_count INTEGER;
    new_id TEXT;
BEGIN
    -- The :Ontology label is precreated by migration 058, so this MATCH is safe
    -- on a fresh graph (empty, not missing).
    EXECUTE 'SELECT count(*)::int FROM cypher(''knowledge_graph'', $cypher$
        MATCH (o:Ontology {name: ''primordial''})
        RETURN o
    $cypher$) as (o agtype)' INTO exists_count;

    IF exists_count = 0 THEN
        new_id := 'ont_' || gen_random_uuid()::text;
        EXECUTE format(
            'SELECT * FROM cypher(''knowledge_graph'', $cypher$
                CREATE (o:Ontology {
                    ontology_id: ''%s'',
                    name: ''primordial'',
                    description: ''Default pool for unroutable sources'',
                    lifecycle_state: ''active'',
                    creation_epoch: 0,
                    created_by: ''system''
                })
            $cypher$) as (o agtype)',
            new_id
        );
        RAISE NOTICE 'Seeded primordial ontology (id: %)', new_id;
    ELSE
        RAISE NOTICE 'primordial ontology already exists, skipping';
    END IF;
END $migration$;

-- ---------------------------------------------------------------------------
-- Migration Tracking
-- ---------------------------------------------------------------------------

INSERT INTO public.schema_migrations (version, name)
VALUES (78, 'seed_primordial_ontology')
ON CONFLICT (version) DO NOTHING;
