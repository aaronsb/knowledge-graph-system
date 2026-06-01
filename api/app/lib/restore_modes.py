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
