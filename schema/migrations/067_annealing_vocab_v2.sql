-- ===========================================================================
-- Migration 067: Annealing Vocabulary v2 (ADR-206)
-- ===========================================================================
-- Date: 2026-05-25
-- Related: ADR-206 (Closed-Vocabulary Annealing Actions with Tiered Escalation)
--          ADR-200 (Annealing Ontologies — clarified to 6-verb vocabulary)
--
-- Migrates kg_api.annealing_proposals from the 2-verb vocabulary
-- ('promotion', 'demotion') to the 6-verb closed action vocabulary plus
-- the Opus-tier control-tuning action:
--
--   Ontology actions: CLEAVE, DISSOLVE, MERGE, RENAME, NO_ACTION, ESCALATE
--   Control action  : ADJUST_CONTROL  (proposal_kind = 'control')
--
-- Old names remain admissible at the DB layer so existing in-flight rows
-- (status pending/approved/executing) keep validating against their own
-- CHECK on update. ADR-206 §"Aliases" handles the read-side mapping in
-- application code. A future migration tightens the constraint once all
-- legacy rows have moved to terminal status.
--
-- The two new columns model parameter shapes that vary by verb:
--
--   proposal_kind  : discriminator ('ontology' | 'control')
--                    'ontology' covers the 6 closed verbs.
--                    'control'  covers ADJUST_CONTROL.
--   params         : JSONB carrying verb-specific parameters
--                    (cluster_selection, routing_map, donor_ontologies, etc.)
--                    Existing typed columns (anchor_concept_id,
--                    target_ontology, reasoning, suggested_name,
--                    suggested_description) stay populated alongside
--                    params for one migration cycle, then are dropped.
--
-- New Phase 3 control-surface options seeded into kg_api.annealing_options
-- support the ADJUST_CONTROL executor (commit 7).
-- ===========================================================================

-- ---------------------------------------------------------------------------
-- 1. Expand proposal_type CHECK constraint to admit the 6 verbs + ADJUST_CONTROL
-- ---------------------------------------------------------------------------
DO $$
BEGIN
    ALTER TABLE kg_api.annealing_proposals
        DROP CONSTRAINT IF EXISTS annealing_proposals_proposal_type_check;
    ALTER TABLE kg_api.annealing_proposals
        ADD CONSTRAINT annealing_proposals_proposal_type_check
        CHECK (proposal_type IN (
            -- ADR-206 closed action vocabulary (6 verbs, proposal_kind='ontology')
            'CLEAVE', 'DISSOLVE', 'MERGE', 'RENAME', 'NO_ACTION', 'ESCALATE',
            -- Opus-tier meta-action (proposal_kind='control')
            'ADJUST_CONTROL',
            -- Deprecated 2-verb vocabulary (read-mapped via ADR-206 aliases;
            -- retained so existing rows do not fail their own constraint on
            -- update — future migration tightens once legacy rows are gone)
            'promotion', 'demotion'
        ));
EXCEPTION WHEN duplicate_object THEN
    NULL;
END $$;

-- ---------------------------------------------------------------------------
-- 2. proposal_kind discriminator (ontology actions vs control-tuning actions)
-- ---------------------------------------------------------------------------
ALTER TABLE kg_api.annealing_proposals
    ADD COLUMN IF NOT EXISTS proposal_kind VARCHAR(20) NOT NULL DEFAULT 'ontology';

DO $$
BEGIN
    ALTER TABLE kg_api.annealing_proposals
        DROP CONSTRAINT IF EXISTS annealing_proposals_proposal_kind_check;
    ALTER TABLE kg_api.annealing_proposals
        ADD CONSTRAINT annealing_proposals_proposal_kind_check
        CHECK (proposal_kind IN ('ontology', 'control'));
EXCEPTION WHEN duplicate_object THEN
    NULL;
END $$;

-- ---------------------------------------------------------------------------
-- 3. params JSONB column for variable-shape verb parameters
-- ---------------------------------------------------------------------------
-- Per ADR-206 §1 (Closed action vocabulary):
--   CLEAVE         : source_ontology, anchor_concept_id, cluster_selection,
--                    cluster_params, target {new(name,description) | existing(name)}
--   DISSOLVE       : source_ontology, force_primordial?, rationale
--                    (executor populates per-source routing_map via
--                     get_cross_ontology_affinity at execution time)
--   MERGE          : donor_ontologies[], target {existing(name) | new(name,description)}
--   RENAME         : ontology, new_name, new_description
--   NO_ACTION      : reasoning
--   ESCALATE       : candidate_actions[], what_i_know, what_i_dont_know,
--                    recommended_action, confidence
--   ADJUST_CONTROL : control_key, current_value, recommended_value,
--                    defense_block {snapshot inputs}
ALTER TABLE kg_api.annealing_proposals
    ADD COLUMN IF NOT EXISTS params JSONB;

-- ---------------------------------------------------------------------------
-- 4. Seed Phase 3 control-surface options used by this PR
-- ---------------------------------------------------------------------------
-- Only the keys actually exercised by commits 6 (pressure recommendation)
-- and 7 (ADJUST_CONTROL) are seeded here. Escalation-chain / opus-confidence
-- / phone_a_friend_cost_budget seeding is deferred to the future LLM-tier
-- integration PR; out of scope for the vocab v2 bundle.
INSERT INTO kg_api.annealing_options (key, value, description) VALUES
    ('failure_cooldown_epochs',
     '5',
     'After a failed execution, suppress new proposals against the same '
     '(anchor_concept_id, proposal_type, target) triple for this many '
     'epochs. Bezier-tunable via ADJUST_CONTROL (ADR-206 Phase 3).'),
    ('max_proposals_per_cycle',
     '10',
     'Maximum number of proposals (any verb) emitted in a single annealing '
     'cycle. Throttles decision volume under high ecological pressure. '
     'Bezier-tunable via ADJUST_CONTROL (ADR-206 Phase 3).'),
    ('min_activity_for_cycle',
     '1',
     'Minimum number of epoch increments since the last cycle before a new '
     'cycle is eligible. Raises the no-op floor when the graph is quiet. '
     'Bezier-tunable via ADJUST_CONTROL (ADR-206 Phase 3).')
ON CONFLICT (key) DO NOTHING;

-- ---------------------------------------------------------------------------
-- 5. Partial index for control proposals (queried by ADJUST_CONTROL executor)
-- ---------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_annealing_proposals_control_kind
    ON kg_api.annealing_proposals(proposal_kind, status)
    WHERE proposal_kind = 'control';

-- ===========================================================================
-- Verification
-- ===========================================================================
DO $$
BEGIN
    -- proposal_type CHECK admits CLEAVE
    BEGIN
        PERFORM 'CLEAVE'::text;
        INSERT INTO kg_api.annealing_proposals
            (proposal_type, ontology_name, reasoning, proposal_kind, params)
        VALUES
            ('CLEAVE', '__migration067_probe__', 'verification probe',
             'ontology', '{"probe": true}'::jsonb);
        DELETE FROM kg_api.annealing_proposals
            WHERE ontology_name = '__migration067_probe__';
    EXCEPTION WHEN check_violation THEN
        RAISE EXCEPTION 'Migration 067 failed: proposal_type CHECK rejects CLEAVE';
    END;

    -- proposal_type CHECK admits ADJUST_CONTROL with proposal_kind='control'
    BEGIN
        INSERT INTO kg_api.annealing_proposals
            (proposal_type, ontology_name, reasoning, proposal_kind, params)
        VALUES
            ('ADJUST_CONTROL', '__migration067_probe__', 'verification probe',
             'control', '{"control_key": "probe"}'::jsonb);
        DELETE FROM kg_api.annealing_proposals
            WHERE ontology_name = '__migration067_probe__';
    EXCEPTION WHEN check_violation THEN
        RAISE EXCEPTION 'Migration 067 failed: proposal_type/kind rejects ADJUST_CONTROL';
    END;

    -- Deprecated names still admissible
    BEGIN
        INSERT INTO kg_api.annealing_proposals
            (proposal_type, ontology_name, reasoning)
        VALUES
            ('promotion', '__migration067_probe__', 'verification probe');
        DELETE FROM kg_api.annealing_proposals
            WHERE ontology_name = '__migration067_probe__';
    EXCEPTION WHEN check_violation THEN
        RAISE EXCEPTION 'Migration 067 failed: deprecated names rejected — would orphan in-flight rows';
    END;

    -- proposal_kind CHECK rejects unknown values
    BEGIN
        INSERT INTO kg_api.annealing_proposals
            (proposal_type, ontology_name, reasoning, proposal_kind)
        VALUES
            ('CLEAVE', '__migration067_probe__', 'verification probe', 'bogus');
        DELETE FROM kg_api.annealing_proposals
            WHERE ontology_name = '__migration067_probe__';
        RAISE EXCEPTION 'Migration 067 failed: proposal_kind CHECK admitted bogus value';
    EXCEPTION WHEN check_violation THEN
        -- expected
        NULL;
    END;

    -- Phase 3 control options seeded
    IF NOT EXISTS (
        SELECT FROM kg_api.annealing_options WHERE key = 'failure_cooldown_epochs'
    ) THEN
        RAISE EXCEPTION 'Migration 067 failed: failure_cooldown_epochs not seeded';
    END IF;
    IF NOT EXISTS (
        SELECT FROM kg_api.annealing_options WHERE key = 'max_proposals_per_cycle'
    ) THEN
        RAISE EXCEPTION 'Migration 067 failed: max_proposals_per_cycle not seeded';
    END IF;
    IF NOT EXISTS (
        SELECT FROM kg_api.annealing_options WHERE key = 'min_activity_for_cycle'
    ) THEN
        RAISE EXCEPTION 'Migration 067 failed: min_activity_for_cycle not seeded';
    END IF;

    RAISE NOTICE 'Migration 067: annealing vocabulary v2 installed';
END $$;

-- ===========================================================================
-- Record Migration
-- ===========================================================================
INSERT INTO public.schema_migrations (version, name)
VALUES (67, 'annealing_vocab_v2')
ON CONFLICT (version) DO NOTHING;
