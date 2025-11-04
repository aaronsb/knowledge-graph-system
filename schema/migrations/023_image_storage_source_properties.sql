-- ============================================================================
-- Migration 023: Image Storage Source Properties (ADR-057)
-- ============================================================================
-- Date: 2025-11-03
-- Description:
--   Extends Source nodes to support multimodal image ingestion with MinIO
--   storage and visual embeddings. No ALTER statements needed - AGE graph
--   nodes accept arbitrary properties. This migration documents the schema.
--
-- New Source Properties:
--   - minio_object_key: Path to original image in MinIO (null for text sources)
--   - visual_embedding: 768-dim Nomic Vision embedding (null for text sources)
--   - content_type: "image" or "document" (distinguishes source type)
--   - embedding: Text embedding (already exists, now used for both text AND image prose)
--
-- Design Note:
--   Image sources have BOTH embeddings:
--     1. visual_embedding: From raw image pixels (visual similarity)
--     2. embedding: From prose description (concept matching)
--
--   Text sources have ONE embedding:
--     1. embedding: From document text
--
--   This enables three search paths:
--     Path 1: Text query → concept embeddings → find concepts → sources
--     Path 2: Text query → source prose embeddings → find images
--     Path 3: Upload image → visual embeddings → find similar images
--
-- Related:
--   - ADR-057: Multimodal Image Ingestion
--   - MinIO object storage (docker-compose.yml)
--   - src/api/lib/minio_client.py
--   - src/api/lib/visual_embeddings.py
-- ============================================================================

-- No schema changes needed - AGE graph nodes are schemaless JSON
-- This migration exists for documentation only

-- Example Source node for IMAGE:
-- (:Source {
--   source_id: "src_abc123",
--   document: "Architecture Diagrams",
--   paragraph: 1,
--   full_text: "Flowchart showing recursive awareness loop with arrows...",  -- Prose from vision model
--   file_path: "/path/to/original.jpg",
--   content_type: "image",  -- NEW
--   minio_object_key: "Architecture_Diagrams/src_abc123.jpg",  -- NEW
--   visual_embedding: [0.123, -0.456, ...],  -- NEW: 768-dim Nomic Vision
--   embedding: [0.789, 0.234, ...]  -- EXISTING: text embedding of prose
-- })

-- Example Source node for DOCUMENT:
-- (:Source {
--   source_id: "src_xyz789",
--   document: "Research Papers",
--   paragraph: 5,
--   full_text: "The recursive nature of consciousness...",  -- Original document text
--   file_path: "/path/to/paper.txt",
--   content_type: "document",  -- NEW
--   minio_object_key: null,  -- No MinIO storage for text
--   visual_embedding: null,  -- No visual embedding for text
--   embedding: [0.456, -0.123, ...]  -- Text embedding of document
-- })

-- Query examples:
--
-- Find all image sources:
-- MATCH (s:Source {content_type: 'image'}) RETURN s
--
-- Find image sources with MinIO storage:
-- MATCH (s:Source) WHERE s.minio_object_key IS NOT NULL RETURN s
--
-- Find image sources with visual embeddings:
-- MATCH (s:Source) WHERE s.visual_embedding IS NOT NULL RETURN s

-- Success marker
DO $$
BEGIN
    RAISE NOTICE 'Migration 023 applied: Image storage Source properties documented';
    RAISE NOTICE 'New properties: minio_object_key, visual_embedding, content_type';
    RAISE NOTICE 'No schema changes needed - AGE graph nodes are schemaless';
END $$;
