-- Migration 077: Add the 'restore' graph-epoch kind (ADR-102 P5)
--
-- A portable-backup restore (ADR-102) is a graph mutation just like an
-- ingestion: it creates Concept/Source/Instance nodes and must advance the
-- ADR-207 freshness clock so every downstream derivation reads stale until the
-- restore commits. To tag the restored nodes we record a graph_epochs event,
-- and migration 064 made graph_epochs.kind a FOREIGN KEY into
-- graph_epoch_kinds — so the kind must exist in the lookup before the restore
-- worker can use it. Migration 064 was explicitly designed so new kinds are
-- added by INSERT (here) rather than by altering a CHECK constraint.
--
-- semantic_wallclock = TRUE: a restore happens "now"; the restored graph state
-- becomes current as of the restore wall-clock (epoch-simple mode collapses the
-- backup's own history into this single event). This matches 'ingestion'/'edit'
-- semantics, not the forensic-only 'reasoning'/'annealing' kinds.

INSERT INTO kg_api.graph_epoch_kinds (kind, semantic_wallclock, description) VALUES
    ('restore', TRUE, 'Graph state restored from a portable backup (ADR-102).')
ON CONFLICT (kind) DO NOTHING;

INSERT INTO public.schema_migrations (version, name)
VALUES (77, 'restore_epoch_kind')
ON CONFLICT (version) DO NOTHING;
