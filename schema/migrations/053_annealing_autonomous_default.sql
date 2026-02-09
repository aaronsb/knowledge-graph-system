-- Migration 053: Change annealing automation_level default to autonomous
--
-- Graph annealing proposals previously defaulted to hitl (human-in-the-loop),
-- requiring manual review before execution. Like vocabulary consolidation,
-- the system is designed for autonomous operation — math grounds the LLM,
-- the LLM reasons over the math, and the combination is more consistent
-- than a human reviewer for routine ontology maintenance.
--
-- hitl mode remains available as a diagnostic/audit tool.

UPDATE kg_api.annealing_options
SET value = 'autonomous',
    description = 'Automation level: autonomous (default, proposals auto-execute), hitl (human review)'
WHERE key = 'automation_level' AND value = 'hitl';

-- Verification
DO $$
DECLARE
    v_level TEXT;
BEGIN
    SELECT value INTO v_level
    FROM kg_api.annealing_options
    WHERE key = 'automation_level';

    IF v_level IS NULL THEN
        RAISE EXCEPTION 'Migration failed: automation_level option not found';
    END IF;

    RAISE NOTICE 'automation_level = %', v_level;
END $$;
