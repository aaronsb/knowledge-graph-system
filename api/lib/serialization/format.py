"""
kg-backup/2 format layer — version constant, schema probe, and the read path.

Holds :class:`BackupFormat` (schema-version probe) and :class:`KgBackupV2Reader`
(de-intern / evidence-group / external-deps reader). Pure of any graph-write
logic. Split out of the former monolithic ``api/lib/serialization.py`` (ADR-102 P6d).
"""

from typing import Dict, Any, List

from api.app.lib.age_client import AGEClient

# kg-backup/2 format version emitted by build_kg_backup_v2 (BACKUP_OBJECT_SPEC).
KG_BACKUP_FORMAT_VERSION = "kg-backup/2"


class BackupFormat:
    """Schema-version probe for backups (ADR-102 P3).

    The legacy v1 metadata (``VERSION``/``FULL_BACKUP``/``ONTOLOGY_BACKUP`` strings
    and ``create_metadata``) was removed in the single-path ``kg-backup/2``
    convergence — there is now exactly one backup model. Only the schema-version
    probe survives; it stamps ``header.schema_version`` in
    :meth:`DataExporter.export_kg_backup_v2`.
    """

    @staticmethod
    def get_schema_version(client: AGEClient) -> int:
        """
        Get current database schema version (last applied migration number)

        Queries kg_api.schema_migrations table to find the highest migration
        version that has been applied. This version is included in backups to
        track schema compatibility across backup/restore cycles.

        Returns:
            Schema version number (e.g., 13 for migration 013_*.sql)
        """
        conn = client.pool.getconn()
        try:
            with conn.cursor() as cur:
                # Check if schema_migrations table exists
                cur.execute("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables
                        WHERE table_schema = 'kg_api'
                        AND table_name = 'schema_migrations'
                    )
                """)
                table_exists = cur.fetchone()[0]

                if not table_exists:
                    # Table doesn't exist yet, return 12 (last migration before this one)
                    return 12

                # Get highest version from schema_migrations
                cur.execute("""
                    SELECT COALESCE(MAX(version), 12)
                    FROM kg_api.schema_migrations
                """)
                version = cur.fetchone()[0]
                return int(version)

        finally:
            conn.commit()
            client.pool.putconn(conn)


class KgBackupV2Reader:
    """Read a kg-backup/2 object into normalized, de-interned records (ADR-102 P3).

    Pure and DB-free: dereferences the declarative header dictionaries (relationship
    vocabulary, content types, epoch kinds, actors) and groups the M:N evidence
    stream, so the clone/merge writers consume plain records and the offline tests
    exercise it without a database. It is intentionally a data-access view over one
    object — its several accessors are all "the same backup, seen as records".

    Single-path: there is exactly one backup model. The reader REFUSES anything that
    is not ``kg-backup/<=2`` (no legacy v1 reading, no upcast — ADR-102 P3); the v1
    JSON shape was a prototype and has been removed.
    """

    SUPPORTED_MAJOR = 2

    def __init__(self, obj: Dict[str, Any]):
        if not isinstance(obj, dict) or "header" not in obj or "bulk" not in obj:
            raise ValueError(
                "Not a kg-backup object: missing header/bulk "
                "(the legacy v1 format is no longer supported — ADR-102 P3)"
            )
        self.header = obj["header"]
        self.bulk = obj["bulk"]
        self.format_version = self._negotiate(self.header.get("format_version"))

        # De-intern lookup tables (header index -> value).
        self._rel_types = [
            v.get("relationship_type") for v in self.header.get("relationship_vocabulary", [])
        ]
        self._content_types = list(self.header.get("content_types", []))
        self._epoch_kinds = [k.get("kind") for k in self.header.get("epoch_kinds", [])]
        self._actors = list(self.header.get("actors", []))

    @classmethod
    def _negotiate(cls, fmt):
        """Accept kg-backup/<=SUPPORTED_MAJOR; refuse unknown family / higher major (spec §7)."""
        family, _, major = (fmt or "").partition("/")
        if family != "kg-backup" or not major.isdigit():
            raise ValueError(f"Unknown backup format_version: {fmt!r}")
        if int(major) > cls.SUPPORTED_MAJOR:
            raise ValueError(
                f"Refusing {fmt}: newer than supported kg-backup/{cls.SUPPORTED_MAJOR} — "
                "partially applying primary inputs is unsafe (ADR-102 §8)"
            )
        return fmt

    def _rel_type(self, idx):
        """Resolve an edge-type index to its relationship_type string."""
        return self._rel_types[idx] if isinstance(idx, int) else idx

    def _content_type(self, idx):
        """Resolve a content-type index to its MIME string (None-safe)."""
        if idx is None:
            return None
        return self._content_types[idx] if isinstance(idx, int) else idx

    def concepts(self):
        """Yield concept records (concept_id, label, search_terms, embedding, epoch stamps)."""
        for c in self.bulk.get("concepts", []):
            yield dict(c)

    def sources(self):
        """Yield source records with content_type de-interned back to its MIME string."""
        for s in self.bulk.get("sources", []):
            rec = dict(s)
            rec["content_type"] = self._content_type(s.get("content_type"))
            yield rec

    def instances(self):
        """Yield normalized instance records (unique; no concept_id — see evidence)."""
        for i in self.bulk.get("instances", []):
            yield dict(i)

    def evidence_by_instance(self):
        """Group the M:N evidence stream as ``{instance_id: [concept_id, ...]}``."""
        grouped: Dict[str, List[str]] = {}
        for e in self.bulk.get("evidence", []):
            grouped.setdefault(e["instance_id"], []).append(e["concept_id"])
        return grouped

    def relationships(self):
        """Yield relationship records with ``type`` de-interned to its label string."""
        for r in self.bulk.get("relationships", []):
            rec = dict(r)
            rec["type"] = self._rel_type(r.get("type"))
            rec["properties"] = r.get("properties") or {}
            yield rec

    def vocabulary(self):
        """Return the bulk vocabulary rows (full descriptors, not interned)."""
        return list(self.bulk.get("vocabulary", []))

    def graph_epochs(self):
        """Yield epoch-log rows with kind/actor de-interned (faithful replay — P5)."""
        for ep in self.bulk.get("graph_epochs", []):
            rec = dict(ep)
            k = ep.get("kind")
            rec["kind"] = self._epoch_kinds[k] if isinstance(k, int) else k
            a = ep.get("actor")
            rec["actor"] = self._actors[a] if isinstance(a, int) else a
            yield rec

    def ontologies(self):
        """Yield :Ontology node records (name, embedding, lifecycle_state, ...).

        Empty for backups taken before the ontology stream existed — restoring
        such a backup simply creates no ontology nodes (the prior behavior).
        """
        for o in self.bulk.get("ontologies", []):
            yield dict(o)

    def scoped_by(self):
        """Return (:Source)-[:SCOPED_BY]->(:Ontology) edges as ``{source_id, ontology}``."""
        return list(self.bulk.get("scoped_by", []))

    def anchored_by(self):
        """Return (:Ontology)-[:ANCHORED_BY]->(:Concept) edges as ``{ontology, concept_id}``."""
        return list(self.bulk.get("anchored_by", []))

    def documents(self):
        """Yield :DocumentMeta node records (the catalog's document tier — issue #505).

        Carries the canonical document identity (``document_id``/``content_hash`` —
        the full ``sha256:``-prefixed digest) and Garage location, so restore
        rebuilds the layer authoritatively rather than re-deriving it from Sources
        (where the full document hash is unrecoverable). Empty for backups taken
        before this stream existed — restoring such a backup falls back to the
        Garage-hashed reconstruction in restore (Option B fallback).
        """
        for d in self.bulk.get("documents", []):
            yield dict(d)

    def has_source(self):
        """Return (:DocumentMeta)-[:HAS_SOURCE]->(:Source) edges as ``{document_id, source_id}``."""
        return list(self.bulk.get("has_source", []))

    def counts(self):
        """Return record counts per bulk stream (for stats/logging)."""
        b = self.bulk
        return {k: len(b.get(k, [])) for k in
                ("concepts", "sources", "instances", "evidence", "relationships",
                 "vocabulary", "ontologies", "scoped_by", "anchored_by",
                 "documents", "has_source")}

    def external_concept_ids(self):
        """Concept ids referenced by edges/evidence but absent from this backup.

        These are cross-ontology dependencies (partial/adjacent backups). On restore
        they create dangling edges unless the referenced concepts already exist in
        the target — the signal the stitch/prune tooling acts on.
        """
        local = {c.get("concept_id") for c in self.concepts()}
        external = {
            endpoint
            for rel in self.relationships()
            for endpoint in (rel.get("from"), rel.get("to"))
            if endpoint and endpoint not in local
        }
        external |= {
            ev.get("concept_id") for ev in self.bulk.get("evidence", [])
            if ev.get("concept_id") and ev.get("concept_id") not in local
        }
        return external
