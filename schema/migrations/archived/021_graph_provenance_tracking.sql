-- Migration 021: Graph-Based Provenance Tracking
-- ADR-051: Add source metadata for document deduplication and relationship audit trails
-- Date: 2025-10-31
--
-- Context:
-- - Move deduplication source of truth from jobs table to graph (DocumentMeta nodes)
-- - Track document source provenance (file path, hostname, ingestion method)
-- - Enable relationship audit trails (who/when/how relationships created)
-- - Support MCP silent enrichment (metadata stored but not exposed to AI)
--
-- Changes:
-- 1. Add source metadata columns to kg_api.jobs table
-- 2. DocumentMeta nodes created in graph via application code (no schema changes)
-- 3. Edge metadata added via application code (Apache AGE supports natively)
--
-- Related: ADR-051, ADR-014 (Job Approval Workflow), ADR-044 (Probabilistic Truth)

BEGIN;

-- ============================================================================
-- Part 1: Add Source Metadata to Jobs Table
-- ============================================================================

-- Add optional source provenance columns
ALTER TABLE kg_api.jobs
    ADD COLUMN source_filename TEXT,    -- Display name: filename, "stdin", or MCP session ID
    ADD COLUMN source_type TEXT,        -- Ingestion method: "file" | "stdin" | "mcp" | "api"
    ADD COLUMN source_path TEXT,        -- Full filesystem path (file ingestion only, null otherwise)
    ADD COLUMN source_hostname TEXT;    -- Hostname where ingestion initiated (CLI only, null for MCP)

-- Create index for source type queries (analytics, debugging)
CREATE INDEX IF NOT EXISTS idx_jobs_source_type ON kg_api.jobs(source_type);

-- Add constraint to validate source_type enum values
ALTER TABLE kg_api.jobs
    ADD CONSTRAINT chk_source_type
    CHECK (source_type IS NULL OR source_type IN ('file', 'stdin', 'mcp', 'api'));

-- Add comments documenting the new columns
COMMENT ON COLUMN kg_api.jobs.source_filename IS 'Display name for source: filename, "stdin", or MCP session ID (best-effort metadata)';
COMMENT ON COLUMN kg_api.jobs.source_type IS 'Ingestion method: file (CLI file), stdin (pipe), mcp (Claude), api (direct) - enables source-aware queries';
COMMENT ON COLUMN kg_api.jobs.source_path IS 'Full filesystem path for file ingestion (null for stdin/mcp/api) - helps identify exact source file';
COMMENT ON COLUMN kg_api.jobs.source_hostname IS 'Hostname where ingestion initiated (CLI only, null for MCP/API) - useful for distributed deployments';

-- ============================================================================
-- Part 2: DocumentMeta Nodes (Created by Application Code)
-- ============================================================================

-- NOTE: DocumentMeta nodes are created in the Apache AGE graph by application code.
-- No schema migration needed here. Schema:
--
-- (:DocumentMeta {
--   document_id: "sha256:abc123...",           -- Hash-based ID
--   content_hash: "sha256:abc123...",          -- For deduplication
--   ontology: "My Docs",                       -- Target ontology
--   source_count: 15,                          -- Number of Source nodes
--   filename: "chapter1.txt",                  -- Display name
--   source_type: "file",                       -- "file" | "stdin" | "mcp" | "api"
--   file_path: "/home/user/docs/chapter1.txt", -- Full path (optional)
--   hostname: "workstation-01",                -- Hostname (optional)
--   ingested_at: "2025-10-31T12:34:56Z",      -- Timestamp
--   ingested_by: "user_123",                   -- User ID
--   job_id: "job_xyz"                          -- Link to job
-- })
--
-- Relationships:
-- (:DocumentMeta)-[:HAS_SOURCE]->(:Source)

-- ============================================================================
-- Part 3: Edge Metadata (Added by Application Code)
-- ============================================================================

-- NOTE: Edge metadata is added via application code when creating relationships.
-- Apache AGE natively supports edge properties. No schema migration needed.
-- All relationships now include provenance metadata:
--
-- (:Concept)-[:IMPLIES {
--   created_at: "2025-10-31T12:34:56Z",
--   created_by: "user_123",
--   source: "llm_extraction",               -- or "human_curation"
--   job_id: "job_xyz",
--   document_id: "sha256:abc..."
-- }]->(:Concept)
--
-- Benefits:
-- - Audit trail: "Which job created this relationship?"
-- - Human vs LLM distinction: Weight human-curated relationships differently
-- - Cascade delete: Delete all edges from a document
-- - Debugging: Trace relationship origin
-- - MCP silent storage: Metadata NOT exposed to Claude

-- ============================================================================
-- Part 4: Backward Compatibility Notes
-- ============================================================================

-- Existing ingestion jobs will have NULL values for new source metadata columns.
-- This is acceptable:
-- - Old jobs still work (deduplication via jobs table until DocumentMeta created)
-- - New jobs populate source metadata (gradually migrates to new system)
-- - Optional backfill script can populate metadata for old jobs from job_data JSONB

-- ============================================================================
-- Migration Complete
-- ============================================================================

-- Verify migration
DO $$
BEGIN
    -- Check that all new columns exist
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'kg_api'
          AND table_name = 'jobs'
          AND column_name = 'source_filename'
    ) THEN
        RAISE EXCEPTION 'Migration failed: source_filename column not created';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'kg_api'
          AND table_name = 'jobs'
          AND column_name = 'source_type'
    ) THEN
        RAISE EXCEPTION 'Migration failed: source_type column not created';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'kg_api'
          AND table_name = 'jobs'
          AND column_name = 'source_path'
    ) THEN
        RAISE EXCEPTION 'Migration failed: source_path column not created';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'kg_api'
          AND table_name = 'jobs'
          AND column_name = 'source_hostname'
    ) THEN
        RAISE EXCEPTION 'Migration failed: source_hostname column not created';
    END IF;

    RAISE NOTICE 'Migration 021 completed successfully';
    RAISE NOTICE '  ✓ Added source metadata columns to kg_api.jobs';
    RAISE NOTICE '  ✓ Created index on source_type';
    RAISE NOTICE '  ✓ Added constraint for source_type validation';
    RAISE NOTICE '';
    RAISE NOTICE 'Next steps (application code):';
    RAISE NOTICE '  1. Update API ingest endpoints to accept source_metadata parameters';
    RAISE NOTICE '  2. Update ingestion_worker.py to create DocumentMeta nodes';
    RAISE NOTICE '  3. Update deduplication check to prioritize graph over jobs table';
    RAISE NOTICE '  4. Add edge metadata to all relationship creation calls';
    RAISE NOTICE '  5. Update kg CLI and MCP server to send source metadata';
END $$;

-- ============================================================================
-- Record Migration
-- ============================================================================

INSERT INTO public.schema_migrations (version, name)
VALUES (21, 'graph_provenance_tracking')
ON CONFLICT (version) DO NOTHING;

COMMIT;
