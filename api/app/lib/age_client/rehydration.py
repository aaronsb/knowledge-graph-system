"""Rehydration mixin: rebuild the derived :Ontology layer from Source nodes.

After a restore, the :Source nodes carry every bit of source-of-truth data
(``document``, ``garage_key``, ``content_hash``, ``source_id``). But a backup
created before the :Ontology layer was serialized (pre-v0.15.1) does not carry
that layer, and restore otherwise never rebuilds it — so the ontology list and
the catalog read empty even though the underlying data is intact (issue #505).

This mixin provides two restore-time rebuilds:

- :meth:`rehydrate_projection_layers` — the **ontology layer**:
  ``(:Ontology)`` + ``(:Source)-[:SCOPED_BY]->(:Ontology)``, keyed by distinct
  ``s.document`` (mirrors migration 044). For new backups the importer already
  MERGEs these nodes/edges (serialization), so the pass is a harmless idempotent
  no-op; for old backups it is the reconstruction. It also ensures the reserved
  ``primordial`` pool exists, since a clone-style restore can replace a
  freshly-seeded graph (see migration 078 / issue #505).

- :meth:`rehydrate_document_layer` — **restore-time durability** for the
  :DocumentMeta tier. New backups serialize :DocumentMeta into ``kg-backup/2``
  (Option B) and the importer rebuilds it authoritatively. Old backups carry no
  such stream, so this reconstructs it from the restored Sources — but
  faithfully: the canonical identity (``document_id == content_hash ==
  sha256(document bytes)``) is unrecoverable from Source nodes alone (the
  ``garage_key`` carries only a 32-char hash prefix), so this hashes the actual
  document bytes (fetched from Garage) to recover the full digest rather than
  using the truncated prefix. Garage I/O is injected so the mixin stays DB-only.
"""

import hashlib
import os
import logging
from typing import Callable, Dict, Optional

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

    def rehydrate_document_layer(
        self,
        fetch_bytes: Callable[[str], Optional[bytes]],
        created_by: Optional[str] = None,
    ) -> Dict[str, int]:
        """Restore-time durability: rebuild :DocumentMeta from Sources + Garage bytes.

        For a backup that carried no serialized ``documents`` stream (pre-Option-B),
        reconstruct the document tier so ``kg catalog ls`` / document drill-down work
        after restore. One :DocumentMeta per distinct ``garage_key`` (a file), linked
        to its Source chunks via :HAS_SOURCE.

        The canonical identity is recovered **faithfully**: the full document hash is
        not on the graph (``garage_key`` holds only its first 32 chars), so this
        fetches each document's bytes via ``fetch_bytes`` and ``sha256``-es them to
        get the full digest, then sets ``document_id`` / ``content_hash`` to the
        canonical ``"sha256:" + <64 hex>`` form — matching what native ingestion
        writes, so re-ingest dedup and drill-down behave identically. A document whose
        bytes can't be fetched is skipped (no truncated node is ever created).

        Idempotent (MERGE on ``document_id``). Intended to run only when the backup
        lacked the stream; harmless if re-run.

        Known limitation (issue #505 multi-ontology follow-up, tracked separately): a
        file ingested into multiple ontologies has one ``garage_key`` per ontology but
        the SAME content hash, so the per-key MERGE collapses to one node (last
        garage_key wins) — matching native ingest's own last-writer-wins behavior.

        Args:
            fetch_bytes: Garage accessor ``garage_key -> bytes | None`` (injected so
                this mixin needs no storage dependency).
            created_by: Recorded as ``ingested_by`` provenance on rebuilt nodes (these
                came from a restore, not a native ingest); accepted for signature
                symmetry with :meth:`rehydrate_projection_layers`.

        Returns:
            Counts: ``documents`` (nodes written), ``has_source_edges``, ``skipped``
            (garage_keys whose bytes could not be fetched), ``mismatches``
            (garage_key prefix != recomputed hash — corruption-grade, see logs).
        """
        stats = {"documents": 0, "has_source_edges": 0, "skipped": 0, "mismatches": 0}
        rows = self._execute_cypher(
            "MATCH (s:Source) WHERE s.garage_key IS NOT NULL "
            "RETURN s.garage_key AS gk, head(collect(s.document)) AS doc, count(s) AS cnt"
        ) or []
        for row in rows:
            garage_key = self._parse_agtype(row.get("gk"))
            if not garage_key:
                continue
            document = self._parse_agtype(row.get("doc"))
            chunk_count = int(self._parse_agtype(row.get("cnt")) or 0)

            try:
                content = fetch_bytes(garage_key)
            except Exception as e:  # storage hiccup must not abort the whole rebuild
                logger.warning("Could not fetch %s for document rehydration: %s", garage_key, e)
                content = None
            if not content:
                stats["skipped"] += 1
                continue

            full_hash = hashlib.sha256(content).hexdigest()
            # Integrity check: garage_key embeds content_hash[:32]; a mismatch means
            # the stored bytes are not what produced the key (corruption / wrong object).
            key_prefix = os.path.splitext(os.path.basename(garage_key))[0]
            if key_prefix and not full_hash.startswith(key_prefix):
                stats["mismatches"] += 1
                logger.warning(
                    "garage_key prefix %s does not match recomputed hash %s (%s) — "
                    "rebuilding DocumentMeta from the recomputed (authoritative) hash",
                    key_prefix, full_hash[:32], garage_key,
                )
            document_id = f"sha256:{full_hash}"

            self._execute_cypher(
                "MERGE (d:DocumentMeta {document_id: $document_id}) "
                "SET d.content_hash = $content_hash, d.ontology = $ontology, "
                "    d.garage_key = $garage_key, d.filename = $filename, "
                "    d.content_type = 'document', d.source_count = $source_count, "
                "    d.ingested_by = $ingested_by "
                "RETURN d",
                params={
                    "document_id": document_id,
                    "content_hash": document_id,  # canonical: content_hash == document_id
                    "ontology": document,
                    "garage_key": garage_key,
                    # Original filename lived only on the (absent) DocumentMeta; the
                    # garage_key basename is the best available name for old backups.
                    "filename": os.path.basename(garage_key),
                    "source_count": chunk_count,
                    # Provenance: these nodes were reconstructed at restore, not ingested.
                    "ingested_by": created_by or "post_restore_rehydration",
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

        return stats
