-- Migration 050: Add 'exploration' to query_definitions definition_type
--
-- Supports saving graph explorations as ordered +/- Cypher statement sequences.
-- Each exploration is a replayable series of additive/subtractive graph operations.
-- ===========================================================================

-- Skip if already applied
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM public.schema_migrations WHERE version = 50) THEN
        RAISE NOTICE 'Migration 050 already applied, skipping';
        RETURN;
    END IF;

    -- Drop and recreate CHECK constraint to include 'exploration'
    ALTER TABLE kg_api.query_definitions
        DROP CONSTRAINT IF EXISTS valid_definition_type;

    ALTER TABLE kg_api.query_definitions
        ADD CONSTRAINT valid_definition_type CHECK (definition_type IN (
            'block_diagram',
            'cypher',
            'search',
            'polarity',
            'connection',
            'exploration'
        ));

    COMMENT ON COLUMN kg_api.query_definitions.definition_type IS
        'Type of query: block_diagram, cypher, search, polarity, connection, exploration';

    RAISE NOTICE 'Migration 050: Added exploration definition type';
END $$;

-- ===========================================================================
-- Record Migration
-- ===========================================================================

INSERT INTO public.schema_migrations (version, name)
VALUES (50, 'exploration_definition_type')
ON CONFLICT (version) DO NOTHING;
