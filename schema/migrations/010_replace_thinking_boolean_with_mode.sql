-- Migration: 010_replace_thinking_boolean_with_mode
-- Description: Replace enable_thinking boolean with thinking_mode enum
-- ADR: ADR-042 (Local LLM Inference for Concept Extraction)
-- Date: 2025-10-23
--
-- Rationale:
-- Unified thinking mode interface: "off", "low", "medium", "high"
-- Model-specific behavior handled by provider:
--   - GPT-OSS: "off" → "low", "low/medium/high" → pass through
--   - Standard models: "off" → false, "low/medium/high" → true
--   - DeepSeek-R1, Qwen3: Similar to GPT-OSS (may support levels)
--
-- This provides consistent user interface while handling model quirks internally.

BEGIN;

-- ============================================================================
-- Replace enable_thinking with thinking_mode
-- ============================================================================

-- 1. Add new thinking_mode column
ALTER TABLE kg_api.ai_extraction_config
ADD COLUMN IF NOT EXISTS thinking_mode VARCHAR(20) DEFAULT 'off'
CHECK (thinking_mode IN ('off', 'low', 'medium', 'high'));

COMMENT ON COLUMN kg_api.ai_extraction_config.thinking_mode IS
'Thinking mode for reasoning models (Ollama 0.12.x+): off, low, medium, high.
GPT-OSS: off=low, others pass through. Standard models: off=disabled, low/medium/high=enabled.';

-- 2. Migrate existing data (enable_thinking → thinking_mode)
UPDATE kg_api.ai_extraction_config
SET thinking_mode = CASE
    WHEN enable_thinking = TRUE THEN 'low'
    ELSE 'off'
END
WHERE thinking_mode = 'off';  -- Only update rows that haven't been migrated

-- 3. Drop old enable_thinking column
ALTER TABLE kg_api.ai_extraction_config
DROP COLUMN IF EXISTS enable_thinking;

-- ============================================================================
-- Record Migration
-- ============================================================================

INSERT INTO public.schema_migrations (version, name)
VALUES (10, 'replace_thinking_boolean_with_mode')
ON CONFLICT (version) DO NOTHING;

COMMIT;
