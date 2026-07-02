-- Migration 069: Vocabulary embedding lifecycle (#420 follow-up)
-- Purpose: Track vocab embedding generation events independently from vocab membership,
--          and replace the cold-start binary init flag with last-processed-counter semantics.
-- Date: 2026-05-26
--
-- ## Background
--
-- The Feb 2 cluster verification (PR #420) exposed two pre-existing lifecycle bugs:
--
-- 1. The polarity-axis cache in GroundingMixin keys against
--    `vocabulary_change_counter` (membership counter). But that counter advances
--    only when vocab rows are added/removed/categorized — not when their
--    `embedding` column is updated. After `kg admin embedding regenerate
--    --type vocabulary`, the cache held a stale (vocab_gen, axis=None) entry
--    and never invalidated until the API process restarted.
--
-- 2. Cold-start uses a binary `initialized` flag on system_initialization_status.
--    If cold-start ran when the vocab table was empty (count=0), the row was
--    marked initialized=TRUE forever, and the 48 builtin types seeded by later
--    migrations never got embeddings on subsequent boots.
--
-- ## What this migration adds
--
-- - `vocabulary_embedding_generation_counter` row in graph_metrics. Bumped by
--   code paths that actually change embedding values (batch generation, add_edge_type
--   inline generation). The polarity-axis cache will key against this in a
--   follow-up commit, so embedding changes invalidate the cache without needing
--   a process restart.
--
-- - `last_processed_vocab_change_counter` column on
--   kg_api.system_initialization_status. Stores the value of
--   `vocabulary_change_counter` at the time embedding work last completed for
--   this component. Replaces the binary `initialized` flag's role as the
--   "should I do work?" gate — the cold-start path and the new
--   VocabEmbeddingLauncher (separate commit) both compare current vs. last
--   processed instead of checking a one-shot flag.
--
-- ## Idempotency
--
-- All operations are safe to re-run:
--   - `INSERT ... ON CONFLICT (metric_name) DO NOTHING` for the counter row
--   - `ADD COLUMN IF NOT EXISTS` for the new column
--   - `INSERT ... ON CONFLICT (version) DO NOTHING` for schema_migrations
--
-- The migration leaves existing data untouched: the new column defaults to 0,
-- which by the new semantics means "no embedding work has completed yet" —
-- which is the correct initial state regardless of what `initialized` says.

BEGIN;

-- ----------------------------------------------------------------------------
-- 1. Counter for vocabulary embedding generation events
-- ----------------------------------------------------------------------------

INSERT INTO public.graph_metrics (metric_name, counter, last_measured_counter, notes)
VALUES (
    'vocabulary_embedding_generation_counter',
    0,
    0,
    'Increments each time a vocabulary type embedding is generated or regenerated. The polarity-axis cache (GroundingMixin) keys against this counter — bumping it invalidates the cache without requiring a process restart. Distinct from vocabulary_change_counter, which tracks row membership rather than embedding contents.'
)
ON CONFLICT (metric_name) DO NOTHING;

-- ----------------------------------------------------------------------------
-- 2. Last-processed-counter column on initialization status
-- ----------------------------------------------------------------------------

ALTER TABLE kg_api.system_initialization_status
    ADD COLUMN IF NOT EXISTS last_processed_vocab_change_counter BIGINT NOT NULL DEFAULT 0;

COMMENT ON COLUMN kg_api.system_initialization_status.last_processed_vocab_change_counter IS
'Snapshot of vocabulary_change_counter at the time this initialization component last completed embedding work. The cold-start and VocabEmbeddingLauncher paths compare current counter vs. this value to detect new work since the last successful run. Replaces the binary `initialized` flag for embedding components (the flag stays for non-counter-driven components). Default 0 means "no work has completed yet" — correct initial state.';

-- ----------------------------------------------------------------------------
-- 3. Migration tracking
-- ----------------------------------------------------------------------------

INSERT INTO public.schema_migrations (version, name)
VALUES (69, 'vocab_embedding_lifecycle')
ON CONFLICT (version) DO NOTHING;

COMMIT;
