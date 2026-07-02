-- Migration 052: Add 'program' to query_definitions definition_type
--
-- Supports storing notarized GraphProgram ASTs (ADR-500 Phase 2b).
-- Programs are validated by the server before storage and can be
-- retrieved and executed by any client.
-- ===========================================================================

-- Skip if already applied
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM public.schema_migrations WHERE version = 52) THEN
        RAISE NOTICE 'Migration 052 already applied, skipping';
        RETURN;
    END IF;

    -- Drop and recreate CHECK constraint to include 'program'
    ALTER TABLE kg_api.query_definitions
        DROP CONSTRAINT IF EXISTS valid_definition_type;

    ALTER TABLE kg_api.query_definitions
        ADD CONSTRAINT valid_definition_type CHECK (definition_type IN (
            'block_diagram',
            'cypher',
            'search',
            'polarity',
            'connection',
            'exploration',
            'program'
        ));

    COMMENT ON COLUMN kg_api.query_definitions.definition_type IS
        'Type of query: block_diagram, cypher, search, polarity, connection, exploration, program';

    RAISE NOTICE 'Migration 052: Added program definition type';
END $$;

-- ===========================================================================
-- Record Migration
-- ===========================================================================

INSERT INTO public.schema_migrations (version, name)
VALUES (52, 'program_definition_type')
ON CONFLICT (version) DO NOTHING;
