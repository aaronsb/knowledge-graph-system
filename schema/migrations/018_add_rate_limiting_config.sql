-- Migration: 018_add_rate_limiting_config
-- Description: Add rate limiting and concurrency configuration for AI providers
-- ADR: ADR-TBD (Rate Limiting and Concurrency Management)
-- Date: 2025-10-28
--
-- Rationale:
-- Different AI providers have different rate limits and resource constraints:
-- - OpenAI: Higher API rate limits, can handle more concurrent requests
-- - Anthropic: Moderate API rate limits
-- - Ollama: Local inference, single GPU/CPU bottleneck
--
-- Per-provider configuration allows:
-- 1. Concurrency control - Limit simultaneous API calls per provider
-- 2. Retry behavior - Configure exponential backoff attempts
-- 3. Resource optimization - Prevent GPU thrashing on local models
--
-- Defaults:
-- - OpenAI: 8 concurrent, 8 retries (higher throughput)
-- - Anthropic: 4 concurrent, 8 retries (moderate throughput)
-- - Ollama: 1 concurrent, 3 retries (single GPU serialization)

BEGIN;

-- ============================================================================
-- Add Rate Limiting Columns
-- ============================================================================

ALTER TABLE kg_api.ai_extraction_config
ADD COLUMN IF NOT EXISTS max_concurrent_requests INTEGER DEFAULT 4
CHECK (max_concurrent_requests >= 1 AND max_concurrent_requests <= 100);

ALTER TABLE kg_api.ai_extraction_config
ADD COLUMN IF NOT EXISTS max_retries INTEGER DEFAULT 8
CHECK (max_retries >= 0 AND max_retries <= 20);

COMMENT ON COLUMN kg_api.ai_extraction_config.max_concurrent_requests IS
'Maximum number of concurrent API requests allowed for this provider.
Limits parallelism to prevent rate limit errors and resource thrashing.
Recommended: OpenAI=8, Anthropic=4, Ollama=1';

COMMENT ON COLUMN kg_api.ai_extraction_config.max_retries IS
'Maximum number of retry attempts for rate-limited requests (429 errors).
Uses exponential backoff with jitter: 1s, 2s, 4s, 8s, 16s, 32s, 64s, ...
Higher values provide more resilience with multiple workers.
Recommended: 8 for cloud providers, 3 for local';

-- ============================================================================
-- Update Existing Configurations with Provider-Specific Defaults
-- ============================================================================

-- OpenAI: High throughput (8 concurrent, 8 retries)
UPDATE kg_api.ai_extraction_config
SET
    max_concurrent_requests = 8,
    max_retries = 8
WHERE provider = 'openai'
AND max_concurrent_requests = 4;  -- Only update if still at default

-- Anthropic: Moderate throughput (4 concurrent, 8 retries)
UPDATE kg_api.ai_extraction_config
SET
    max_concurrent_requests = 4,
    max_retries = 8
WHERE provider = 'anthropic'
AND max_concurrent_requests = 4;  -- Only update if still at default

-- Ollama: Serialized (1 concurrent, 3 retries)
-- Note: Ollama not in current provider list, but adding for future support
UPDATE kg_api.ai_extraction_config
SET
    max_concurrent_requests = 1,
    max_retries = 3
WHERE provider = 'ollama'
AND max_concurrent_requests = 4;  -- Only update if still at default

-- ============================================================================
-- Expand Provider Check Constraint to Include Ollama
-- ============================================================================

-- Drop existing constraint and add new one (idempotent)
DO $$
BEGIN
    -- Drop existing constraint if it exists
    ALTER TABLE kg_api.ai_extraction_config
    DROP CONSTRAINT IF EXISTS ai_extraction_config_provider_check;

    -- Add new constraint with ollama
    ALTER TABLE kg_api.ai_extraction_config
    ADD CONSTRAINT ai_extraction_config_provider_check
    CHECK (provider IN ('openai', 'anthropic', 'ollama'));
EXCEPTION
    WHEN duplicate_object THEN
        -- Constraint already exists, skip
        NULL;
END $$;

-- ============================================================================
-- Record Migration
-- ============================================================================

INSERT INTO public.schema_migrations (version, name)
VALUES (18, 'add_rate_limiting_config')
ON CONFLICT (version) DO NOTHING;

COMMIT;
