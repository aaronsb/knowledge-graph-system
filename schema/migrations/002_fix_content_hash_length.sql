-- Migration: Fix PostgreSQL job queue schema issues
-- Issues:
--   1. content_hash VARCHAR(64) too short for "sha256:" + 64 hex (71 chars)
--   2. status CHECK constraint missing 'approved' and 'queued' states
-- Date: 2025-10-12

-- Fix 1: Increase content_hash length
ALTER TABLE kg_api.ingestion_jobs
ALTER COLUMN content_hash TYPE VARCHAR(80);

-- Fix 2: Update status constraint to include all workflow states
ALTER TABLE kg_api.ingestion_jobs DROP CONSTRAINT IF EXISTS ingestion_jobs_status_check;
ALTER TABLE kg_api.ingestion_jobs ADD CONSTRAINT ingestion_jobs_status_check
  CHECK (status IN (
    'pending',
    'awaiting_approval',
    'approved',
    'queued',
    'running',
    'completed',
    'failed',
    'cancelled'
  ));

-- Verification
DO $$
DECLARE
    column_length INTEGER;
    constraint_count INTEGER;
BEGIN
    -- Verify content_hash length
    SELECT character_maximum_length INTO column_length
    FROM information_schema.columns
    WHERE table_schema = 'kg_api'
      AND table_name = 'ingestion_jobs'
      AND column_name = 'content_hash';

    IF column_length >= 80 THEN
        RAISE NOTICE '✓ content_hash column length: % characters', column_length;
    ELSE
        RAISE EXCEPTION 'Migration failed: content_hash still too short (% chars)', column_length;
    END IF;

    -- Verify status constraint exists
    SELECT COUNT(*) INTO constraint_count
    FROM information_schema.constraint_column_usage
    WHERE table_schema = 'kg_api'
      AND table_name = 'ingestion_jobs'
      AND constraint_name = 'ingestion_jobs_status_check';

    IF constraint_count > 0 THEN
        RAISE NOTICE '✓ status CHECK constraint updated';
    ELSE
        RAISE EXCEPTION 'Migration failed: status constraint not found';
    END IF;

    RAISE NOTICE '✓ Migration 002 complete';
END $$;
