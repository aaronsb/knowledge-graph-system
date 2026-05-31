-- Migration 076: Trustworthy freshness clock (ADR-207, #384)
--
-- ADR-207 makes the ADR-203 epoch event log the canonical version signal for
-- every materialized graph derivation (catalog index, grounding cache tiers,
-- artifacts). Two things are needed before any derivation can stamp against it:
--
--   1. Epoch events must distinguish committed mutations from in-flight and
--      failed ones (#384). record_graph_epoch() inserts a row at job *start*,
--      so a bare event_id reflects an *attempt*, not a commit.
--
--   2. The freshness signal must be a contiguous committed prefix, NOT
--      MAX(event_id WHERE completed). Epochs complete OUT OF ORDER (a long
--      ingestion at id 6 may finish after a short one at id 7), so MAX-of-
--      completed would skip event 6's eventual commit and read false-FRESH.
--      The watermark is the highest N such that NO event <= N is still
--      in flight.
--
-- This migration also widens the derivation stamp columns to BIGINT (the event
-- sequence is BIGINT) and re-documents graph_change_counter (ADR-079) as a
-- one-directional dirty-hint only — sound for proving "changed", never trusted
-- to prove "fresh" (it is a non-injective count checksum; see ADR-203).
--
-- No data back-fill of existing stamps is performed: per ADR-207's clean-
-- rebuild assumption the platform carries no data to preserve. The status
-- back-fill below only matters for environments that already hold epoch rows,
-- where pre-existing rows are by definition historical/committed.

-- ---------------------------------------------------------------------------
-- 1. Epoch event status (#384): in_progress (default) | completed | failed
-- ---------------------------------------------------------------------------
ALTER TABLE kg_api.graph_epochs
    ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'in_progress'
    CHECK (status IN ('in_progress', 'completed', 'failed'));

-- Pre-existing rows predate this column and represent completed historical
-- mutations — mark them committed so they never block the watermark.
UPDATE kg_api.graph_epochs
   SET status = 'completed'
 WHERE status = 'in_progress'
   AND occurred_at < NOW();

COMMENT ON COLUMN kg_api.graph_epochs.status IS
    'ADR-207/#384: in_progress (set at record_graph_epoch) | completed | failed. '
    'Only in_progress blocks the committed watermark — both completed and failed '
    'count toward it (per-chunk commits mean a failed job may have mutated the '
    'graph). The completed/failed split is for analytics (drop zero-instance '
    'jobs from hot/stale signals), not for freshness.';

-- The watermark query probes the lowest still-in-flight event; a partial index
-- keeps that O(1)-ish regardless of how many committed rows accumulate.
CREATE INDEX IF NOT EXISTS idx_graph_epochs_in_flight
    ON kg_api.graph_epochs (event_id)
    WHERE status = 'in_progress';

-- ---------------------------------------------------------------------------
-- 2. Mark an epoch resolved (completed or failed)
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION kg_api.complete_graph_epoch(
    p_event_id BIGINT,
    p_status   TEXT DEFAULT 'completed'
) RETURNS VOID AS $$
BEGIN
    IF p_status NOT IN ('completed', 'failed') THEN
        RAISE EXCEPTION 'complete_graph_epoch: status must be completed or failed, got %', p_status;
    END IF;

    UPDATE kg_api.graph_epochs
       SET status = p_status
     WHERE event_id = p_event_id;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION kg_api.complete_graph_epoch IS
    'ADR-207/#384: resolve an epoch event recorded by record_graph_epoch(). '
    'Call with completed when the mutation transaction commits, failed when it '
    'aborts/rolls back. Until called, the event is in_progress and holds the '
    'committed watermark below its event_id.';

-- ---------------------------------------------------------------------------
-- 3. The canonical clock: contiguous committed-prefix watermark
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION kg_api.get_committed_epoch()
RETURNS BIGINT AS $$
DECLARE
    v_first_in_flight BIGINT;
    v_max             BIGINT;
BEGIN
    -- Lowest event still in flight: every event below it is RESOLVED (whether
    -- it committed or failed), and no event above it may be exposed yet (the
    -- in-flight one is logically earlier and may still be committing).
    SELECT MIN(event_id) INTO v_first_in_flight
      FROM kg_api.graph_epochs
     WHERE status = 'in_progress';

    IF v_first_in_flight IS NOT NULL THEN
        RETURN v_first_in_flight - 1;
    END IF;

    -- Nothing in flight: the watermark is the highest event id recorded,
    -- counting BOTH completed and failed events. Failed events count on
    -- purpose: ingestion commits per-chunk, so a job that aborted or was
    -- cancelled mid-run may have already committed partial graph changes.
    -- Excluding it (MAX WHERE completed) would hide those commits and read
    -- false-FRESH. A cleanly-rolled-back failed event that committed nothing
    -- costs at most one benign no-op rebuild — the safe direction to err.
    -- The completed/failed distinction is for analytics (#384: drop zero-
    -- instance jobs from hot/stale signals), NOT for this watermark.
    -- Monotonic: event_id is BIGSERIAL, so a new in-flight event always has a
    -- higher id than the resolved prefix and the watermark never regresses.
    SELECT MAX(event_id) INTO v_max FROM kg_api.graph_epochs;
    RETURN COALESCE(v_max, 0);
END;
$$ LANGUAGE plpgsql STABLE;

COMMENT ON FUNCTION kg_api.get_committed_epoch IS
    'ADR-207: canonical freshness clock. Committed-prefix watermark: '
    'MIN(in_flight)-1 if any job is in flight, else MAX(event_id) over all '
    'resolved events (completed AND failed both count — per-chunk commits mean '
    'a failed job may have mutated the graph). Monotonic high-water signal: a '
    'derivation whose stamp < this value is provably stale. Out-of-order '
    'completion safe.';

-- ---------------------------------------------------------------------------
-- 4. Widen derivation stamp columns INTEGER -> BIGINT (match the event seq)
-- ---------------------------------------------------------------------------
ALTER TABLE kg_api.artifacts    ALTER COLUMN graph_epoch TYPE BIGINT;
ALTER TABLE kg_api.catalog_node ALTER COLUMN graph_epoch TYPE BIGINT;
ALTER TABLE kg_api.catalog_edge ALTER COLUMN graph_epoch TYPE BIGINT;

-- ---------------------------------------------------------------------------
-- 5. Demote graph_change_counter to a one-directional dirty-hint
-- ---------------------------------------------------------------------------
-- get_graph_epoch() still returns the count checksum, but ADR-207 forbids
-- trusting it for freshness. Widen its return type to BIGINT for consistency
-- with the clock (DROP first: PostgreSQL will not change a return type in
-- place via CREATE OR REPLACE).
DROP FUNCTION IF EXISTS kg_api.get_graph_epoch();
CREATE OR REPLACE FUNCTION kg_api.get_graph_epoch()
RETURNS BIGINT AS $$
DECLARE
    v_epoch BIGINT;
BEGIN
    SELECT counter INTO v_epoch
    FROM public.graph_metrics
    WHERE metric_name = 'graph_change_counter';

    RETURN COALESCE(v_epoch, 0);
END;
$$ LANGUAGE plpgsql STABLE;

COMMENT ON FUNCTION kg_api.get_graph_epoch IS
    'ADR-079 graph_change_counter (composite count checksum). ADR-207: a '
    'ONE-DIRECTIONAL DIRTY HINT ONLY — counter != stamp reliably proves the '
    'graph changed, but counter == stamp does NOT prove freshness (the checksum '
    'is non-injective; ADR-203). Use kg_api.get_committed_epoch() for any '
    'freshness/staleness decision. Do not reintroduce this as a freshness signal.';

INSERT INTO public.schema_migrations (version, name)
VALUES (76, 'freshness_clock')
ON CONFLICT (version) DO NOTHING;
