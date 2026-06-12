"""Rehydration mixin: rebuild derived graph-projection layers from Source nodes.

After a restore, the :Source nodes carry every bit of source-of-truth data
(``document``, ``garage_key``, ``content_hash``, ``source_id``). But a backup
created before a projection layer was serialized does not carry that layer, and
restore otherwise never rebuilds it — so the ontology list and the catalog read
empty even though the underlying data is intact (issue #505).

This mixin reconstructs both derived layers idempotently from the Sources:

- **Ontology layer** — ``(:Ontology)`` + ``(:Source)-[:SCOPED_BY]->(:Ontology)``,
  keyed by distinct ``s.document`` (mirrors migration 044).
- **Document layer** — ``(:DocumentMeta)`` + ``(:DocumentMeta)-[:HAS_SOURCE]->(:Source)``,
  one ``DocumentMeta`` per file (grouped by ``s.garage_key``).

Both are pure derivations of intact Source data, so the pass is idempotent
(MERGE-based) and a no-op on post-serialization backups that already carry the
layers. It also ensures the reserved ``primordial`` pool exists, since a
clone-style restore can replace a freshly-seeded graph (see migration 078 /
issue #505).
"""

import logging
import os
import re
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# The reserved default pool unroutable sources fall into (ADR-200). Must always
# exist; mirrors proposal_executor._ensure_primordial_pool and migration 078.
PRIMORDIAL_POOL_NAME = "primordial"


class RehydrationMixin:
    """Reconstruct the :Ontology and :DocumentMeta projection layers from Sources."""

    def rehydrate_projection_layers(self, created_by: Optional[str] = None) -> Dict[str, int]:
        """Rebuild the ontology + document projection layers from Source nodes.

        Idempotent: ensures each distinct ontology and file has its node and
        edges, creating only what is missing. Safe to run on every restore.

        Args:
            created_by: Actor recorded on any newly created Ontology nodes.

        Returns:
            Counts of work done: ``ontologies``, ``scoped_by_edges``,
            ``documents``, ``has_source_edges``.
        """
        stats = {"ontologies": 0, "scoped_by_edges": 0, "documents": 0, "has_source_edges": 0}

        # The primordial pool is not derivable from Sources — ensure it directly
        # so a clone restore that wiped the seeded graph still has it.
        self.ensure_ontology_exists(
            PRIMORDIAL_POOL_NAME,
            description="Default pool for unroutable sources",
            created_by=created_by,
        )

        self._rehydrate_ontology_layer(stats, created_by)
        self._rehydrate_document_layer(stats)
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

    def _rehydrate_document_layer(self, stats: Dict[str, int]) -> None:
        """Create one :DocumentMeta per file (grouped by garage_key) + :HAS_SOURCE edges."""
        rows = self._execute_cypher(
            "MATCH (s:Source) WHERE s.garage_key IS NOT NULL "
            "RETURN s.garage_key AS gk, s.document AS doc, count(s) AS cnt"
        ) or []
        # A file (garage_key) may carry chunks tagged to different ontologies, so
        # the same gk can appear on multiple rows; process each gk once.
        seen: set = set()
        for row in rows:
            garage_key = self._parse_agtype(row.get("gk"))
            if not garage_key or garage_key in seen:
                continue
            seen.add(garage_key)
            document = self._parse_agtype(row.get("doc"))
            chunk_count = int(self._parse_agtype(row.get("cnt")) or 0)

            # Stable document_id + display name from the file hash in the garage_key.
            file_hash = re.sub(r"^.*/([^/]+)\.md$", r"\1", garage_key)
            document_id = f"sha256:{file_hash}"

            self._execute_cypher(
                "MERGE (d:DocumentMeta {document_id: $document_id}) "
                "SET d.filename = $filename, d.ontology = $ontology, "
                "    d.content_type = 'document', d.source_count = $source_count "
                "RETURN d",
                params={
                    "document_id": document_id,
                    "filename": os.path.basename(garage_key),
                    "ontology": document,
                    "source_count": chunk_count,
                },
                fetch_one=True,
            )
            stats["documents"] += 1
            linked = self._execute_cypher(
                "MATCH (d:DocumentMeta {document_id: $document_id}) "
                "MATCH (s:Source {garage_key: $garage_key}) "
                "MERGE (d)-[:HAS_SOURCE]->(s) "
                "RETURN count(s) AS c",
                params={"document_id": document_id, "garage_key": garage_key},
                fetch_one=True,
            )
            if linked:
                stats["has_source_edges"] += int(self._parse_agtype(linked.get("c")) or 0)
