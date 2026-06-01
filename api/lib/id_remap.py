"""ID remapping for ADJACENT-mode restore (ADR-102 P3).

Adjacent mode imports a ``kg-backup/2`` backup *alongside* existing graph data
without identity collisions: every app-assigned id (concept / source / instance)
is rewritten old→new, and **every reference class** that cites those ids is
rewritten through the maps. A missed class silently orphans edges (ADR-102
Consequences: "a missed class silently orphans relationships"), so the rewrite is
exhaustive and is covered class-by-class by the test matrix:

  - ``concept_id``  → concepts, ``evidence.concept_id``, relationship ``from``/``to``
  - ``source_id``   → sources, ``instances.source_id``, **and the ``learned_id`` EDGE
                      property** (a source_id carried on agent-learned edges)
  - ``instance_id`` → instances, ``evidence.instance_id``
  - image ``storage_key`` → **recomputed** from the new source_id (derived, not an id)
  - ``garage_key`` (source document) → content-addressed (sha256): **IMMUNE**, preserved

Pure and DB-free: emits a NEW valid ``kg-backup/2`` object (which flows through the
normal clone path unchanged) plus the old→new mapping table — a restore artifact
that lets callers transpose ids afterward. The clone/merge *mode selection* and the
DB fetch of the target's existing ids are wired in P4.
"""
import uuid
from typing import Dict, Any, Optional, Set, Callable, Tuple


def _default_id_factory(kind: str, old_id: str) -> str:
    """Mint a fresh, collision-free id, prefixed by kind initial for debuggability."""
    return f"{kind[0]}_{uuid.uuid4().hex}"


def _remap_storage_key(storage_key: str, old_sid: str, new_sid: str) -> str:
    """Recompute an image storage_key for a new source_id.

    Key format (``api/app/lib/garage/image_storage.py``):
    ``images/{ontology}/{source_id}.{ext}``. The ontology (``Source.document``) is
    preserved in adjacent mode, so only the source_id filename stem changes; anchor
    on ``/{old}.`` so nothing else in the path is touched.
    """
    needle = f"/{old_sid}."
    if needle in storage_key:
        return storage_key.replace(needle, f"/{new_sid}.", 1)
    # Fallback: source_id used without a clean filename anchor.
    return storage_key.replace(old_sid, new_sid, 1)


class IdRemapper:
    """Rewrite all app-assigned ids in a kg-backup/2 object for adjacent-mode restore.

    Modes:
      - ``always`` — mint a new id for every record (adjacent-without-integration:
        the backup lands as a wholly independent copy).
      - ``collision`` — remap an id only when it already exists in the target
        (``existing_ids``); non-colliding ids are preserved.
    """

    MODE_ALWAYS = "always"
    MODE_COLLISION = "collision"

    def __init__(self, mode: str = MODE_ALWAYS,
                 existing_ids: Optional[Dict[str, Set[str]]] = None,
                 id_factory: Optional[Callable[[str, str], str]] = None):
        if mode not in (self.MODE_ALWAYS, self.MODE_COLLISION):
            raise ValueError(f"Unknown remap mode: {mode!r}")
        self.mode = mode
        self.existing = existing_ids or {}
        self._mint = id_factory or _default_id_factory

    def _decide(self, kind: str, old_id: str) -> str:
        """Return the new id for ``old_id`` under the active mode."""
        if self.mode == self.MODE_ALWAYS:
            return self._mint(kind, old_id)
        if old_id in self.existing.get(kind, set()):
            return self._mint(kind, old_id)
        return old_id  # collision mode, no collision → preserve

    def build_maps(self, bulk: Dict[str, Any]) -> Dict[str, Dict[str, str]]:
        """Build the old→new id maps for one mode (concepts / sources / instances)."""
        return {
            "concepts": {c["concept_id"]: self._decide("concept", c["concept_id"])
                         for c in bulk.get("concepts", [])},
            "sources": {s["source_id"]: self._decide("source", s["source_id"])
                        for s in bulk.get("sources", [])},
            "instances": {i["instance_id"]: self._decide("instance", i["instance_id"])
                          for i in bulk.get("instances", [])},
        }

    def remap(self, obj: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Dict[str, str]]]:
        """Return ``(new_backup_object, mapping_table)`` for this remapper's mode.

        The header is carried unchanged (it holds no app-ids — only ontology names,
        profile identities, and interned dictionaries). All ids live in ``bulk``.
        """
        maps = self.build_maps(obj["bulk"])
        new_obj = self.apply_maps(obj, maps["concepts"], maps["sources"], maps["instances"])
        return new_obj, maps

    @staticmethod
    def apply_maps(obj: Dict[str, Any],
                   concept_map: Dict[str, str],
                   source_map: Dict[str, str],
                   instance_map: Dict[str, str],
                   drop_concepts: "frozenset[str]" = frozenset()) -> Dict[str, Any]:
        """Rewrite every reference class in ``obj`` through the supplied maps.

        Pure: same rewrite for every mode. ``drop_concepts`` names incoming
        concept_ids whose CONCEPT RECORD must NOT be emitted (integration mode:
        a matched concept attaches to an existing target, so its node is left
        untouched) — references to it are still rewritten through ``concept_map``.
        Unmapped references fall through unchanged (``.get(x, x)``): external
        endpoints that already live in the target.
        """
        bulk = obj["bulk"]
        new_bulk: Dict[str, Any] = {}

        new_bulk["concepts"] = [
            {**c, "concept_id": concept_map[c["concept_id"]]}
            for c in bulk.get("concepts", [])
            if c["concept_id"] not in drop_concepts
        ]

        new_sources = []
        for s in bulk.get("sources", []):
            old_sid = s["source_id"]
            new_sid = source_map.get(old_sid, old_sid)
            s2 = {**s, "source_id": new_sid}
            if s2.get("storage_key") and new_sid != old_sid:
                s2["storage_key"] = _remap_storage_key(s2["storage_key"], old_sid, new_sid)
            # garage_key is content-addressed (sha256) — immune, left untouched.
            new_sources.append(s2)
        new_bulk["sources"] = new_sources

        new_bulk["instances"] = [
            {**i,
             "instance_id": instance_map.get(i["instance_id"], i["instance_id"]),
             "source_id": source_map.get(i["source_id"], i["source_id"])}
            for i in bulk.get("instances", [])
        ]

        new_bulk["evidence"] = [
            {"concept_id": concept_map.get(e["concept_id"], e["concept_id"]),
             "instance_id": instance_map.get(e["instance_id"], e["instance_id"])}
            for e in bulk.get("evidence", [])
        ]

        new_rels = []
        for r in bulk.get("relationships", []):
            r2 = {**r,
                  "from": concept_map.get(r["from"], r["from"]),
                  "to": concept_map.get(r["to"], r["to"])}
            props = r.get("properties")
            if props:
                p2 = dict(props)
                # learned_id is a source_id carried on the edge — remap via SOURCE map.
                if p2.get("learned_id") is not None:
                    p2["learned_id"] = source_map.get(p2["learned_id"], p2["learned_id"])
                r2["properties"] = p2
            new_rels.append(r2)
        new_bulk["relationships"] = new_rels

        # Streams with no app-ids are carried through unchanged.
        new_bulk["vocabulary"] = bulk.get("vocabulary", [])
        if "graph_epochs" in bulk:
            new_bulk["graph_epochs"] = bulk["graph_epochs"]

        return {"header": obj["header"], "bulk": new_bulk}
