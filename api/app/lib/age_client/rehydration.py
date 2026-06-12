"""Rehydration mixin: rebuild the derived :Ontology layer from Source nodes.

After a restore, the :Source nodes carry every bit of source-of-truth data
(``document``, ``garage_key``, ``content_hash``, ``source_id``). But a backup
created before the :Ontology layer was serialized (pre-v0.15.1) does not carry
that layer, and restore otherwise never rebuilds it — so the ontology list and
the catalog read empty even though the underlying data is intact (issue #505).

This mixin reconstructs the **ontology layer** idempotently from the Sources:
``(:Ontology)`` + ``(:Source)-[:SCOPED_BY]->(:Ontology)``, keyed by distinct
``s.document`` (mirrors migration 044). For new backups the importer already
MERGEs these nodes/edges (serialization), so the pass is a harmless idempotent
no-op; for old backups it is the reconstruction fallback. It also ensures the
reserved ``primordial`` pool exists, since a clone-style restore can replace a
freshly-seeded graph (see migration 078 / issue #505).

The :DocumentMeta layer is intentionally NOT reconstructed here: its canonical
identity (``document_id == content_hash == sha256(document bytes)``) is not
recoverable from Source nodes (the garage_key carries only a 32-char hash
prefix), so a Source-derived DocumentMeta would have a truncated id that breaks
drill-down and re-ingest dedup. That layer is handled authoritatively by
serializing it into ``kg-backup/2`` (Option B, issue #505), with a faithful
Garage-hashed reconstruction reserved for old backups.
"""

import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# The reserved default pool unroutable sources fall into (ADR-200). Must always
# exist; mirrors proposal_executor._ensure_primordial_pool and migration 078.
PRIMORDIAL_POOL_NAME = "primordial"


class RehydrationMixin:
    """Reconstruct the :Ontology projection layer from Sources (issue #505)."""

    def rehydrate_projection_layers(self, created_by: Optional[str] = None) -> Dict[str, int]:
        """Rebuild the ontology projection layer from Source nodes.

        Idempotent: ensures each distinct ontology has its node and SCOPED_BY
        edges, creating only what is missing. Safe to run on every restore — a
        no-op on backups that already carry the serialized ontology layer, the
        reconstruction fallback on pre-serialization backups.

        Args:
            created_by: Actor recorded on any newly created Ontology nodes.

        Returns:
            Counts of work done: ``ontologies``, ``scoped_by_edges``.
        """
        stats = {"ontologies": 0, "scoped_by_edges": 0}

        # The primordial pool is not derivable from Sources — ensure it directly
        # so a clone restore that wiped the seeded graph still has it.
        self.ensure_ontology_exists(
            PRIMORDIAL_POOL_NAME,
            description="Default pool for unroutable sources",
            created_by=created_by,
        )

        self._rehydrate_ontology_layer(stats, created_by)
        return stats

    def _rehydrate_ontology_layer(self, stats: Dict[str, int], created_by: Optional[str]) -> None:
        """Create an :Ontology node + :SCOPED_BY edges for each distinct s.document."""
        rows = self._execute_cypher(
            "MATCH (s:Source) WHERE s.document IS NOT NULL RETURN DISTINCT s.document AS name"
        ) or []
        for row in rows:
            name = self._parse_agtype(row.get("name"))
            if not name:
                continue
            self.ensure_ontology_exists(name, created_by=created_by)
            stats["ontologies"] += 1
            linked = self._execute_cypher(
                "MATCH (s:Source {document: $name}) "
                "MATCH (o:Ontology {name: $name}) "
                "MERGE (s)-[:SCOPED_BY]->(o) "
                "RETURN count(s) AS c",
                params={"name": name},
                fetch_one=True,
            )
            if linked:
                stats["scoped_by_edges"] += int(self._parse_agtype(linked.get("c")) or 0)
