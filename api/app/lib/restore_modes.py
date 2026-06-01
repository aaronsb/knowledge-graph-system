"""Restore merge modes (ADR-102 P4).

A backup is restored under one of three modes, chosen at restore time (a request
param — the backup file is pure data and does not dictate its own restore policy):

  - ``idempotent``  — MERGE-by-id, collisions update in place. The backup's ids are
                      authoritative. Into an empty target this is a faithful clone
                      (ids preserved 1:1); into a populated target it updates matching
                      nodes and adds the rest. No id rewrite.
  - ``adjacent``    — every id is minted fresh (``IdRemapper`` ``always``): the backup
                      lands as a wholly independent copy alongside existing data, with
                      a mapping table to transpose ids afterward.
  - ``integration`` — each incoming CONCEPT is matched against the target by cosine
                      similarity (``ConceptMatcher``, 0.85 strict / 0.75 label-boosted).
                      A match attaches the incoming concept's instances/evidence/edges
                      to the EXISTING target concept (the incoming concept record is
                      dropped — the target node is left untouched); a non-match mints a
                      new concept. Sources and instances are always minted fresh (they
                      are raw inputs, not dedup targets). Like greenfield ingest, minus
                      the LLM extraction step.

Every mode produces a valid ``kg-backup/2`` object that flows through the normal
clone writer (``DataImporter._import_kg_backup_v2``) plus an old→new mapping table.
"""
import logging
from typing import Any, Dict, Optional, Tuple

from ...lib.id_remap import IdRemapper
from .concept_matcher import ConceptMatcher

logger = logging.getLogger(__name__)

MappingTable = Dict[str, Dict[str, str]]


class RestoreMode:
    """The three restore merge modes (ADR-102 P4)."""

    IDEMPOTENT = "idempotent"
    ADJACENT = "adjacent"
    INTEGRATION = "integration"
    ALL = (IDEMPOTENT, ADJACENT, INTEGRATION)
    DEFAULT = IDEMPOTENT

    @classmethod
    def validate(cls, mode: str) -> str:
        """Return ``mode`` if recognized, else raise ValueError."""
        if mode not in cls.ALL:
            raise ValueError(
                f"Unknown restore mode {mode!r}; expected one of {', '.join(cls.ALL)}"
            )
        return mode


def _empty_maps() -> MappingTable:
    return {"concepts": {}, "sources": {}, "instances": {}}


def _active_identity(profiles) -> Optional[str]:
    """The active embedding-profile identity (index 0, active-first) or None."""
    return profiles[0].get("identity") if profiles else None


def _backup_active_identity(obj: Dict[str, Any]) -> Optional[str]:
    """The backup's active text embedding-profile identity (spec §3.2), or None."""
    header = obj.get("header", {})
    profiles = header.get("embedding_profiles") or []
    idx = header.get("default_embedding_profile")
    if isinstance(idx, int) and 0 <= idx < len(profiles):
        return profiles[idx].get("identity")
    return _active_identity(profiles)


def _target_active_identity(client: Any) -> Optional[str]:
    """The target graph's active embedding-profile identity, or None if unconfigured."""
    from ...lib.serialization import DataExporter
    return _active_identity(DataExporter.export_embedding_profiles(client))


def _assert_compatible_embedding_space(obj: Dict[str, Any], client: Any) -> None:
    """Guard integration matching against an embedding-space mismatch (ADR-102 §6).

    Integration matches the backup's CARRIED concept vectors against the target by
    cosine similarity. If the backup was embedded in a different space than the
    target's active profile, those vectors are meaningless in the target space and
    — at equal dimensions — can yield plausible-but-wrong matches that silently
    mis-attach concepts. §6 requires recomputing embeddings before integration;
    until that rehydration exists (P5), a known mismatch is REJECTED.
    """
    backup_id = _backup_active_identity(obj)
    target_id = _target_active_identity(client)
    if backup_id and target_id and backup_id != target_id:
        raise ValueError(
            f"integration mode requires matching embedding spaces: backup is "
            f"{backup_id!r} but the target's active profile is {target_id!r}. The "
            f"carried vectors are in a different space — recompute embeddings before "
            f"integration matching (ADR-102 §6; embedding rehydration is P5). Use "
            f"'adjacent' to import without matching."
        )
    if not (backup_id and target_id):
        logger.warning(
            "restore(integration): could not confirm embedding-space compatibility "
            "(backup=%r, target=%r) — proceeding; verify your embedding configuration",
            backup_id, target_id,
        )


def prepare_backup(obj: Dict[str, Any], mode: str,
                   client: Optional[Any] = None) -> Tuple[Dict[str, Any], MappingTable]:
    """Transform a kg-backup/2 object for ``mode``; return ``(prepared_obj, mapping_table)``.

    The prepared object is fed verbatim to the clone writer. ``client`` (an AGEClient)
    is required only for ``integration`` (it queries the target for similar concepts).
    """
    RestoreMode.validate(mode)

    if mode == RestoreMode.IDEMPOTENT:
        # Authoritative ids, MERGE-by-id in the writer — no transformation.
        return obj, _empty_maps()

    if mode == RestoreMode.ADJACENT:
        new_obj, maps = IdRemapper(mode=IdRemapper.MODE_ALWAYS).remap(obj)
        logger.info("restore(adjacent): minted %d concept / %d source / %d instance new ids",
                    len(maps["concepts"]), len(maps["sources"]), len(maps["instances"]))
        return new_obj, maps

    if mode == RestoreMode.INTEGRATION:
        if client is None:
            raise ValueError("integration mode requires a client to match against the target")
        return _prepare_integration(obj, client)

    raise ValueError(f"Unknown restore mode: {mode!r}")  # pragma: no cover (validate guards)


def _prepare_integration(obj: Dict[str, Any], client: Any) -> Tuple[Dict[str, Any], MappingTable]:
    """Build integration maps: concepts match-or-mint; sources/instances always mint.

    A matched concept is recorded in ``concept_map`` pointing at the EXISTING target
    concept_id and added to ``drop_concepts`` so its record is not emitted (the target
    node stays untouched); its instances/evidence/edges rewire to the target. Unmatched
    concepts — and all sources/instances — get freshly minted ids.
    """
    # ADR-102 §6: refuse to match across embedding spaces (silent mis-attach risk).
    _assert_compatible_embedding_space(obj, client)

    bulk = obj["bulk"]
    # Reuse the always-minter for fresh ids (sources, instances, unmatched concepts).
    minted = IdRemapper(mode=IdRemapper.MODE_ALWAYS).build_maps(bulk)

    matcher = ConceptMatcher(client)
    concept_map: Dict[str, str] = {}
    drop_concepts = set()
    matched_count = 0

    for c in bulk.get("concepts", []):
        cid = c["concept_id"]
        match = matcher.match_concept_in_database(
            {"embedding": c.get("embedding"), "label": c.get("label")}
        )
        if match:
            concept_map[cid] = match["concept_id"]   # attach to existing target concept
            drop_concepts.add(cid)                    # do not emit/overwrite the target node
            matched_count += 1
        else:
            concept_map[cid] = minted["concepts"][cid]  # new concept

    maps: MappingTable = {
        "concepts": concept_map,
        "sources": minted["sources"],
        "instances": minted["instances"],
    }
    prepared = IdRemapper.apply_maps(
        obj, concept_map, maps["sources"], maps["instances"], drop_concepts=frozenset(drop_concepts)
    )
    logger.info(
        "restore(integration): %d concepts matched-and-attached to existing, %d new; "
        "%d sources / %d instances minted",
        matched_count, len(concept_map) - matched_count, len(maps["sources"]), len(maps["instances"]),
    )
    return prepared, maps
