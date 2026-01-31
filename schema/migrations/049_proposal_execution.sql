-- ===========================================================================
-- Migration 049: Proposal Execution Schema (ADR-200 Phase 4)
-- ===========================================================================
-- Date: 2026-01-30
-- Related: ADR-200 (Breathing Ontologies, Phase 4)
--
-- Extends breathing_proposals table for automated execution:
--   - New status values: executing, executed, failed
--   - Execution tracking: executed_at, execution_result
--   - Promotion metadata: suggested_name, suggested_description
--   - Breathing options for automation level
-- ===========================================================================

-- 1. Drop and recreate CHECK constraint to add execution states
DO $$
BEGIN
    ALTER TABLE kg_api.breathing_proposals
        DROP CONSTRAINT IF EXISTS breathing_proposals_status_check;
    ALTER TABLE kg_api.breathing_proposals
        ADD CONSTRAINT breathing_proposals_status_check
        CHECK (status IN ('pending', 'approved', 'rejected', 'expired',
                          'executing', 'executed', 'failed'));
EXCEPTION WHEN duplicate_object THEN
    -- Constraint already exists with correct definition
    NULL;
END $$;

-- 2. Execution tracking columns
ALTER TABLE kg_api.breathing_proposals
    ADD COLUMN IF NOT EXISTS executed_at TIMESTAMPTZ;
ALTER TABLE kg_api.breathing_proposals
    ADD COLUMN IF NOT EXISTS execution_result JSONB;

-- 3. Store LLM's suggested name/description for promotions
--    (Previously discarded between evaluate and store in breathing_manager)
ALTER TABLE kg_api.breathing_proposals
    ADD COLUMN IF NOT EXISTS suggested_name VARCHAR(200);
ALTER TABLE kg_api.breathing_proposals
    ADD COLUMN IF NOT EXISTS suggested_description TEXT;

-- 4. Breathing options for automation level
INSERT INTO kg_api.breathing_options (key, value, description) VALUES
    ('automation_level', 'hitl',
     'Automation level: hitl (human-in-the-loop), aitl (AI-in-the-loop), autonomous'),
    ('primordial_pool_name', 'primordial',
     'Name of the primordial/default ontology for unroutable sources')
ON CONFLICT (key) DO NOTHING;

-- 5. Partial index for finding approved-but-unexecuted proposals
CREATE INDEX IF NOT EXISTS idx_breathing_proposals_approved
    ON kg_api.breathing_proposals(status) WHERE status = 'approved';

-- ===========================================================================
-- Verification
-- ===========================================================================

DO $$
BEGIN
    -- Verify new status values are accepted
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.check_constraints
        WHERE constraint_name = 'breathing_proposals_status_check'
    ) THEN
        RAISE EXCEPTION 'Migration failed: status CHECK constraint not updated';
    END IF;

    -- Verify new columns exist
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'kg_api'
          AND table_name = 'breathing_proposals'
          AND column_name = 'executed_at'
    ) THEN
        RAISE EXCEPTION 'Migration failed: executed_at column not added';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'kg_api'
          AND table_name = 'breathing_proposals'
          AND column_name = 'execution_result'
    ) THEN
        RAISE EXCEPTION 'Migration failed: execution_result column not added';
    END IF;

    IF NOT EXISTS (
        SELECT FROM kg_api.breathing_options WHERE key = 'automation_level'
    ) THEN
        RAISE EXCEPTION 'Migration failed: automation_level option not seeded';
    END IF;

    RAISE NOTICE 'Migration 049: Proposal execution schema installed successfully';
END $$;

-- ===========================================================================
-- Record Migration
-- ===========================================================================

INSERT INTO public.schema_migrations (version, name)
VALUES (49, 'proposal_execution')
ON CONFLICT (version) DO NOTHING;
