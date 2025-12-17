-- Migration 035: Artifact Persistence (ADR-083)
--
-- Adds multi-tier artifact storage with ownership and freshness tracking.
--
-- Creates:
--   kg_api.query_definitions - Saved query recipes (block diagrams, etc.)
--   kg_api.artifacts - Computed artifact metadata with Garage pointers
--
-- Supports:
--   - Lazy loading (metadata in SQL, payload in Garage)
--   - Graph epoch freshness validation
--   - Ownership integration with ADR-082

BEGIN;

-- ============================================================================
-- Query Definitions Table (the "recipe" that can be re-run)
-- ============================================================================

CREATE TABLE IF NOT EXISTS kg_api.query_definitions (
    id SERIAL PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    definition_type VARCHAR(50) NOT NULL,
    definition JSONB NOT NULL,
    owner_id INTEGER REFERENCES kg_auth.users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT valid_definition_type CHECK (definition_type IN (
        'block_diagram',
        'cypher',
        'search',
        'polarity',
        'connection'
    ))
);

CREATE INDEX IF NOT EXISTS idx_query_def_owner ON kg_api.query_definitions(owner_id);
CREATE INDEX IF NOT EXISTS idx_query_def_type ON kg_api.query_definitions(definition_type);
CREATE INDEX IF NOT EXISTS idx_query_def_name ON kg_api.query_definitions(name);
CREATE INDEX IF NOT EXISTS idx_query_def_updated ON kg_api.query_definitions(updated_at DESC);

COMMENT ON TABLE kg_api.query_definitions IS 'Saved query recipes that can be re-executed (ADR-083)';
COMMENT ON COLUMN kg_api.query_definitions.definition_type IS 'Type of query: block_diagram, cypher, search, polarity, connection';
COMMENT ON COLUMN kg_api.query_definitions.definition IS 'Query parameters/structure as JSON';

-- ============================================================================
-- Artifacts Table (computed results with metadata)
-- ============================================================================

CREATE TABLE IF NOT EXISTS kg_api.artifacts (
    id SERIAL PRIMARY KEY,

    -- Classification
    artifact_type VARCHAR(50) NOT NULL,
    representation VARCHAR(50) NOT NULL,
    name VARCHAR(200),

    -- Ownership (NULL = system-owned, integrates with ADR-082)
    owner_id INTEGER REFERENCES kg_auth.users(id),

    -- Freshness tracking
    graph_epoch INTEGER NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ,

    -- Content (either inline or pointer to Garage)
    parameters JSONB NOT NULL,
    metadata JSONB,
    inline_result JSONB,
    garage_key VARCHAR(200),

    -- Relationships
    query_definition_id INTEGER REFERENCES kg_api.query_definitions(id) ON DELETE SET NULL,
    ontology VARCHAR(200),
    concept_ids TEXT[],

    -- Validation
    CONSTRAINT valid_artifact_type CHECK (artifact_type IN (
        'polarity_analysis',
        'projection',
        'query_result',
        'graph_subgraph',
        'vocabulary_analysis',
        'epistemic_measurement',
        'consolidation_result',
        'search_result',
        'connection_path',
        'report',
        'stats_snapshot'
    )),
    CONSTRAINT valid_representation CHECK (representation IN (
        'polarity_explorer',
        'embedding_landscape',
        'block_builder',
        'edge_explorer',
        'vocabulary_chord',
        'force_graph_2d',
        'force_graph_3d',
        'report_workspace',
        'cli',
        'mcp_server',
        'api_direct'
    )),
    CONSTRAINT has_content CHECK (
        inline_result IS NOT NULL OR garage_key IS NOT NULL
    )
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_artifacts_owner ON kg_api.artifacts(owner_id);
CREATE INDEX IF NOT EXISTS idx_artifacts_type ON kg_api.artifacts(artifact_type);
CREATE INDEX IF NOT EXISTS idx_artifacts_representation ON kg_api.artifacts(representation);
CREATE INDEX IF NOT EXISTS idx_artifacts_ontology ON kg_api.artifacts(ontology);
CREATE INDEX IF NOT EXISTS idx_artifacts_epoch ON kg_api.artifacts(graph_epoch);
CREATE INDEX IF NOT EXISTS idx_artifacts_created ON kg_api.artifacts(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_artifacts_query_def ON kg_api.artifacts(query_definition_id);
CREATE INDEX IF NOT EXISTS idx_artifacts_expires ON kg_api.artifacts(expires_at)
    WHERE expires_at IS NOT NULL;

-- Composite index for listing user's artifacts by type
CREATE INDEX IF NOT EXISTS idx_artifacts_owner_type
    ON kg_api.artifacts(owner_id, artifact_type, created_at DESC);

COMMENT ON TABLE kg_api.artifacts IS 'Computed artifact metadata with Garage blob pointers (ADR-083)';
COMMENT ON COLUMN kg_api.artifacts.artifact_type IS 'Type of computation: polarity_analysis, projection, etc.';
COMMENT ON COLUMN kg_api.artifacts.representation IS 'Source UI/tool: polarity_explorer, cli, mcp_server, etc.';
COMMENT ON COLUMN kg_api.artifacts.graph_epoch IS 'graph_change_counter at creation for freshness validation';
COMMENT ON COLUMN kg_api.artifacts.inline_result IS 'Small results (<10KB) stored inline';
COMMENT ON COLUMN kg_api.artifacts.garage_key IS 'Pointer to Garage blob for large results';
COMMENT ON COLUMN kg_api.artifacts.concept_ids IS 'Concept IDs involved in this artifact';

-- ============================================================================
-- Helper: Get Current Graph Epoch
-- ============================================================================

CREATE OR REPLACE FUNCTION kg_api.get_graph_epoch()
RETURNS INTEGER AS $$
DECLARE
    v_epoch INTEGER;
BEGIN
    SELECT counter INTO v_epoch
    FROM public.graph_metrics
    WHERE metric_name = 'graph_change_counter';

    RETURN COALESCE(v_epoch, 0);
END;
$$ LANGUAGE plpgsql STABLE;

COMMENT ON FUNCTION kg_api.get_graph_epoch IS 'Get current graph change counter for freshness tracking';

-- ============================================================================
-- Helper: Check Artifact Freshness
-- ============================================================================

CREATE OR REPLACE FUNCTION kg_api.is_artifact_fresh(p_artifact_id INTEGER)
RETURNS BOOLEAN AS $$
DECLARE
    v_artifact_epoch INTEGER;
    v_current_epoch INTEGER;
BEGIN
    SELECT graph_epoch INTO v_artifact_epoch
    FROM kg_api.artifacts
    WHERE id = p_artifact_id;

    IF v_artifact_epoch IS NULL THEN
        RETURN FALSE;  -- Artifact not found
    END IF;

    v_current_epoch := kg_api.get_graph_epoch();

    RETURN v_artifact_epoch = v_current_epoch;
END;
$$ LANGUAGE plpgsql STABLE;

COMMENT ON FUNCTION kg_api.is_artifact_fresh IS 'Check if artifact is fresh (graph unchanged since creation)';

-- ============================================================================
-- Trigger: Update query_definitions.updated_at
-- ============================================================================

CREATE OR REPLACE FUNCTION kg_api.update_query_definition_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_query_definition_updated ON kg_api.query_definitions;
CREATE TRIGGER trg_query_definition_updated
    BEFORE UPDATE ON kg_api.query_definitions
    FOR EACH ROW
    EXECUTE FUNCTION kg_api.update_query_definition_timestamp();

-- ============================================================================
-- Migration Record
-- ============================================================================

INSERT INTO public.schema_migrations (version, name)
VALUES (35, 'artifact_persistence')
ON CONFLICT (version) DO NOTHING;

COMMIT;
