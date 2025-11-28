-- Migration: 027_source_text_embeddings
-- Description: Add source text embeddings with offset tracking and hash verification (ADR-068)
-- ADR: ADR-068 (Source Text Embeddings for Grounding Truth Retrieval)
-- Date: 2025-11-27
--
-- Philosophy:
-- - Two-level chunking: Ingestion (doc→source) + Embedding (source→chunks)
-- - Dual hash verification: chunk_hash + source_hash for referential integrity
-- - Offset-based chunk tracking for precise text highlighting
-- - System-wide embedding_config (same dimensions as concept embeddings)
-- - NULL content_hash for existing Sources (backfill via regenerate worker)

BEGIN;

-- ============================================================================
-- Source Embeddings Table
-- ============================================================================

-- Store embeddings for source text chunks with offset tracking
CREATE TABLE IF NOT EXISTS kg_api.source_embeddings (
    embedding_id SERIAL PRIMARY KEY,

    -- Reference to Source node in Apache AGE
    source_id TEXT NOT NULL,

    -- Chunk tracking
    chunk_index INTEGER NOT NULL CHECK (chunk_index >= 0),
    chunk_strategy TEXT NOT NULL CHECK (chunk_strategy IN (
        'sentence',     -- Sentence-based chunking (~500 chars)
        'paragraph',    -- Paragraph-based chunking
        'semantic',     -- Future: semantic boundary detection
        'count'         -- Simple character count chunking
    )),

    -- Offset tracking in Source.full_text (character positions)
    start_offset INTEGER NOT NULL CHECK (start_offset >= 0),
    end_offset INTEGER NOT NULL CHECK (end_offset > start_offset),
    chunk_text TEXT NOT NULL,  -- Actual chunk content (for verification)

    -- Referential integrity (double hash verification)
    chunk_hash TEXT NOT NULL,   -- SHA256 of chunk_text (verifies chunk integrity)
    source_hash TEXT NOT NULL,  -- SHA256 of Source.full_text (detects stale embeddings)

    -- Embedding data (uses active embedding_config)
    embedding BYTEA NOT NULL,           -- Vector embedding (float16 or float32 array)
    embedding_model TEXT NOT NULL,      -- Model name (e.g., "nomic-ai/nomic-embed-text-v1.5")
    embedding_dimension INTEGER NOT NULL CHECK (embedding_dimension > 0),
    embedding_provider TEXT,            -- Provider (e.g., "local", "openai")

    -- Metadata
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,

    -- Unique constraint: one embedding per (source_id, chunk_index, strategy)
    UNIQUE(source_id, chunk_index, chunk_strategy)
);

-- Indexes for efficient queries
CREATE INDEX IF NOT EXISTS idx_source_embeddings_source_id
ON kg_api.source_embeddings(source_id);

CREATE INDEX IF NOT EXISTS idx_source_embeddings_source_hash
ON kg_api.source_embeddings(source_hash);

CREATE INDEX IF NOT EXISTS idx_source_embeddings_chunk_strategy
ON kg_api.source_embeddings(chunk_strategy);

CREATE INDEX IF NOT EXISTS idx_source_embeddings_created_at
ON kg_api.source_embeddings(created_at DESC);

-- Table comments
COMMENT ON TABLE kg_api.source_embeddings IS
'ADR-068: Embeddings for source text chunks with offset tracking and hash verification';

COMMENT ON COLUMN kg_api.source_embeddings.source_id IS
'Reference to Source node in Apache AGE graph';

COMMENT ON COLUMN kg_api.source_embeddings.chunk_index IS
'0-based chunk number within source (e.g., 0, 1, 2...)';

COMMENT ON COLUMN kg_api.source_embeddings.chunk_strategy IS
'Chunking strategy used: sentence, paragraph, semantic, or count';

COMMENT ON COLUMN kg_api.source_embeddings.start_offset IS
'Character offset in Source.full_text where chunk starts (0-based)';

COMMENT ON COLUMN kg_api.source_embeddings.end_offset IS
'Character offset in Source.full_text where chunk ends (exclusive)';

COMMENT ON COLUMN kg_api.source_embeddings.chunk_text IS
'Actual chunk content stored for verification (should match Source.full_text[start_offset:end_offset])';

COMMENT ON COLUMN kg_api.source_embeddings.chunk_hash IS
'SHA256 hash of chunk_text - verifies chunk integrity';

COMMENT ON COLUMN kg_api.source_embeddings.source_hash IS
'SHA256 hash of Source.full_text - detects when source text changes (stale embedding indicator)';

COMMENT ON COLUMN kg_api.source_embeddings.embedding IS
'Vector embedding bytes (float16 or float32 array, packed as bytea)';

COMMENT ON COLUMN kg_api.source_embeddings.embedding_model IS
'Embedding model name (e.g., "nomic-ai/nomic-embed-text-v1.5", "text-embedding-3-small")';

COMMENT ON COLUMN kg_api.source_embeddings.embedding_dimension IS
'Embedding vector dimension (must match system embedding_config for cosine similarity)';

-- ============================================================================
-- Helper Views for Source Embeddings
-- ============================================================================

-- View: Sources missing embeddings (NULL content_hash indicates no embeddings generated)
CREATE OR REPLACE VIEW kg_api.v_sources_missing_embeddings AS
SELECT
    s.source_id,
    s.document,
    s.paragraph,
    LENGTH(s.full_text) as text_length,
    s.created_at
FROM (
    SELECT *
    FROM cypher('knowledge_graph', $$
        MATCH (s:Source)
        RETURN s.source_id as source_id,
               s.document as document,
               s.paragraph as paragraph,
               s.full_text as full_text,
               s.content_hash as content_hash,
               s.created_at as created_at
    $$) AS (
        source_id text,
        document text,
        paragraph integer,
        full_text text,
        content_hash text,
        created_at text
    )
) s
WHERE s.content_hash IS NULL
ORDER BY s.created_at DESC;

COMMENT ON VIEW kg_api.v_sources_missing_embeddings IS
'ADR-068: Source nodes that need embedding generation (content_hash is NULL)';

-- View: Stale embeddings detection
CREATE OR REPLACE VIEW kg_api.v_stale_source_embeddings AS
SELECT
    se.source_id,
    se.chunk_index,
    se.chunk_strategy,
    se.source_hash as stored_hash,
    s.content_hash as current_hash,
    se.created_at as embedding_created_at,
    se.embedding_model
FROM kg_api.source_embeddings se
JOIN (
    SELECT *
    FROM cypher('knowledge_graph', $$
        MATCH (s:Source)
        RETURN s.source_id as source_id,
               s.content_hash as content_hash
    $$) AS (
        source_id text,
        content_hash text
    )
) s ON se.source_id = s.source_id
WHERE se.source_hash != s.content_hash
ORDER BY se.created_at DESC;

COMMENT ON VIEW kg_api.v_stale_source_embeddings IS
'ADR-068: Embeddings that are stale (source text changed since embedding generation)';

-- ============================================================================
-- Helper Functions for Source Embeddings
-- ============================================================================

-- Function: Get embedding count for a source
CREATE OR REPLACE FUNCTION kg_api.get_source_embedding_count(
    p_source_id TEXT,
    p_strategy TEXT DEFAULT NULL
) RETURNS INTEGER AS $$
DECLARE
    v_count INTEGER;
BEGIN
    IF p_strategy IS NULL THEN
        SELECT COUNT(*)
        INTO v_count
        FROM kg_api.source_embeddings
        WHERE source_id = p_source_id;
    ELSE
        SELECT COUNT(*)
        INTO v_count
        FROM kg_api.source_embeddings
        WHERE source_id = p_source_id
          AND chunk_strategy = p_strategy;
    END IF;

    RETURN COALESCE(v_count, 0);
END;
$$ LANGUAGE plpgsql STABLE;

COMMENT ON FUNCTION kg_api.get_source_embedding_count IS
'ADR-068: Count embeddings for a source (optionally filtered by strategy)';

-- Function: Check if embeddings are stale
CREATE OR REPLACE FUNCTION kg_api.are_source_embeddings_stale(
    p_source_id TEXT,
    p_current_source_hash TEXT
) RETURNS BOOLEAN AS $$
DECLARE
    v_stored_hash TEXT;
BEGIN
    -- Get stored hash from any embedding for this source
    SELECT source_hash
    INTO v_stored_hash
    FROM kg_api.source_embeddings
    WHERE source_id = p_source_id
    LIMIT 1;

    -- If no embeddings exist, they're not stale (they're missing)
    IF v_stored_hash IS NULL THEN
        RETURN FALSE;
    END IF;

    -- Compare hashes
    RETURN v_stored_hash != p_current_source_hash;
END;
$$ LANGUAGE plpgsql STABLE;

COMMENT ON FUNCTION kg_api.are_source_embeddings_stale IS
'ADR-068: Check if source embeddings are stale (source text changed)';

-- Function: Delete embeddings for a source (for regeneration)
CREATE OR REPLACE FUNCTION kg_api.delete_source_embeddings(
    p_source_id TEXT,
    p_strategy TEXT DEFAULT NULL
) RETURNS INTEGER AS $$
DECLARE
    v_deleted_count INTEGER;
BEGIN
    IF p_strategy IS NULL THEN
        -- Delete all embeddings for source
        DELETE FROM kg_api.source_embeddings
        WHERE source_id = p_source_id;
    ELSE
        -- Delete embeddings for specific strategy
        DELETE FROM kg_api.source_embeddings
        WHERE source_id = p_source_id
          AND chunk_strategy = p_strategy;
    END IF;

    GET DIAGNOSTICS v_deleted_count = ROW_COUNT;
    RETURN v_deleted_count;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION kg_api.delete_source_embeddings IS
'ADR-068: Delete source embeddings (optionally filtered by strategy) for regeneration';

-- ============================================================================
-- Trigger: Auto-update updated_at timestamp
-- ============================================================================

CREATE OR REPLACE FUNCTION kg_api.update_source_embedding_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_update_source_embedding_timestamp ON kg_api.source_embeddings;
CREATE TRIGGER trigger_update_source_embedding_timestamp
    BEFORE UPDATE ON kg_api.source_embeddings
    FOR EACH ROW
    EXECUTE FUNCTION kg_api.update_source_embedding_timestamp();

COMMENT ON TRIGGER trigger_update_source_embedding_timestamp ON kg_api.source_embeddings IS
'ADR-068: Automatically update updated_at timestamp on embedding updates';

-- ============================================================================
-- Record Migration
-- ============================================================================

INSERT INTO public.schema_migrations (version, name)
VALUES (27, 'source_text_embeddings')
ON CONFLICT (version) DO NOTHING;

COMMIT;
