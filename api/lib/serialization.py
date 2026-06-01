"""
Data serialization - Export and import operations for backup/restore

Handles conversion between Apache AGE graph data and portable JSON format,
preserving embeddings (1536-dim vectors), full text, and relationships.
"""

import json
import re
from typing import Dict, Any, List, Optional
from datetime import datetime
import sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

# Add parent directory to path for AGEClient import
sys.path.insert(0, str(Path(__file__).parent.parent))
from api.app.lib.age_client import AGEClient

from .console import Console, Colors

# kg-backup/2 format version emitted by build_kg_backup_v2 (BACKUP_OBJECT_SPEC).
KG_BACKUP_FORMAT_VERSION = "kg-backup/2"


def _parse_nullable_int(raw: Any) -> Optional[int]:
    """Parse a nullable integer from an AGE agtype scalar.

    AGE returns scalars as agtype; absent/NULL properties surface as ``None`` or
    the literal string ``"null"``. Returns the int value, or ``None`` when the
    value is absent/null/unparseable (e.g. a pre-epoch concept with no
    created_at_epoch).
    """
    if raw is None:
        return None
    s = str(raw).strip().strip('"')
    if s == "" or s.lower() == "null":
        return None
    try:
        return int(s)
    except (ValueError, TypeError):
        return None


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


class DataExporter:
    """Export graph data to JSON format"""

    @staticmethod
    def export_concepts(client: AGEClient, ontology: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Export concepts with embeddings

        Args:
            client: AGEClient instance
            ontology: Optional ontology filter (None = all concepts)

        Returns:
            List of concept dictionaries with full embeddings
        """
        if ontology:
            query = """
                MATCH (c:Concept)-[:APPEARS]->(s:Source {document: $ontology})
                WITH DISTINCT c
                RETURN c.concept_id as concept_id,
                       c.label as label,
                       c.search_terms as search_terms,
                       c.embedding as embedding,
                       c.created_at_epoch as created_at_epoch,
                       c.last_seen_epoch as last_seen_epoch
                ORDER BY c.concept_id
            """
            result = client._execute_cypher(query, params={"ontology": ontology})
        else:
            query = """
                MATCH (c:Concept)
                RETURN c.concept_id as concept_id,
                       c.label as label,
                       c.search_terms as search_terms,
                       c.embedding as embedding,
                       c.created_at_epoch as created_at_epoch,
                       c.last_seen_epoch as last_seen_epoch
                ORDER BY c.concept_id
            """
            result = client._execute_cypher(query)

        concepts = []
        for record in result:
            # Parse agtype values - strip quotes and parse JSON for arrays
            concept_id = str(record.get("concept_id", "")).strip('"')
            label = str(record.get("label", "")).strip('"')

            # Parse search_terms (array)
            search_terms_raw = str(record.get("search_terms", "[]"))
            try:
                search_terms = json.loads(search_terms_raw)
            except json.JSONDecodeError:
                search_terms = []

            # Parse embedding (array of floats)
            embedding_raw = str(record.get("embedding", "[]"))
            try:
                embedding = json.loads(embedding_raw)
            except json.JSONDecodeError:
                embedding = []

            concepts.append({
                "concept_id": concept_id,
                "label": label,
                "search_terms": search_terms,
                "embedding": embedding,  # Full 1536-dim array
                # ADR-102 §3: epoch stamps (nullable for pre-epoch concepts).
                "created_at_epoch": _parse_nullable_int(record.get("created_at_epoch")),
                "last_seen_epoch": _parse_nullable_int(record.get("last_seen_epoch")),
            })

        return concepts

    @staticmethod
    def export_sources(client: AGEClient, ontology: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Export source nodes with full text and Garage references

        Args:
            client: AGEClient instance
            ontology: Optional ontology filter

        Returns:
            List of source dictionaries including garage_key and content_type
        """
        if ontology:
            query = """
                MATCH (s:Source {document: $ontology})
                RETURN s.source_id as source_id,
                       s.document as document,
                       s.file_path as file_path,
                       s.paragraph as paragraph,
                       s.full_text as full_text,
                       s.garage_key as garage_key,
                       s.content_type as content_type,
                       s.storage_key as storage_key
                ORDER BY s.paragraph
            """
            result = client._execute_cypher(query, params={"ontology": ontology})
        else:
            query = """
                MATCH (s:Source)
                RETURN s.source_id as source_id,
                       s.document as document,
                       s.file_path as file_path,
                       s.paragraph as paragraph,
                       s.full_text as full_text,
                       s.garage_key as garage_key,
                       s.content_type as content_type,
                       s.storage_key as storage_key
                ORDER BY s.document, s.paragraph
            """
            result = client._execute_cypher(query)

        sources = []
        seen_ids = set()
        for record in result:
            source_id = str(record.get("source_id", "")).strip('"')

            # Defense-in-depth (ADR-102): a duplicate source_id is a graph integrity
            # issue (suspected ingest race — tracked separately for a runtime
            # integrity-check expansion). Drop the dup from the backup so it stays
            # restorable, but WARN — do not silently mask it.
            if source_id in seen_ids:
                Console.warning(
                    f"Duplicate source_id {source_id!r} in graph — dropping the "
                    f"duplicate from the backup (defense-in-depth; investigate the "
                    f"graph integrity issue)"
                )
                continue
            seen_ids.add(source_id)

            # Parse agtype values
            garage_key = str(record.get("garage_key", "")).strip('"')
            content_type = str(record.get("content_type", "")).strip('"')
            storage_key = str(record.get("storage_key", "")).strip('"')

            source = {
                "source_id": source_id,
                "document": str(record.get("document", "")).strip('"'),
                "file_path": str(record.get("file_path", "")).strip('"'),
                "paragraph": int(str(record.get("paragraph", 0))),
                "full_text": str(record.get("full_text", "")).strip('"'),
            }

            # Add Garage fields if present (sources may predate ADR-081)
            if garage_key and garage_key != "None":
                source["garage_key"] = garage_key
            if content_type and content_type != "None":
                source["content_type"] = content_type
            if storage_key and storage_key != "None":
                source["storage_key"] = storage_key  # For images

            sources.append(source)

        return sources

    @staticmethod
    def export_instances(client: AGEClient, ontology: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Export instance nodes (evidence quotes)

        Args:
            client: AGEClient instance
            ontology: Optional ontology filter

        Returns:
            List of instance dictionaries
        """
        # ADR-102: instances are normalized — UNIQUE per instance node, with no
        # concept_id. An instance evidences M concepts (M:N via EVIDENCED_BY); those
        # links live in the separate evidence stream (see export_evidence). This
        # avoids repeating the full quote once per evidenced concept.
        if ontology:
            query = """
                MATCH (i:Instance)-[:FROM_SOURCE]->(s:Source {document: $ontology})
                RETURN DISTINCT i.instance_id as instance_id,
                       i.quote as quote,
                       s.source_id as source_id,
                       i.created_at_event_id as created_at_event_id
                ORDER BY i.instance_id
            """
            result = client._execute_cypher(query, params={"ontology": ontology})
        else:
            query = """
                MATCH (i:Instance)-[:FROM_SOURCE]->(s:Source)
                RETURN DISTINCT i.instance_id as instance_id,
                       i.quote as quote,
                       s.source_id as source_id,
                       i.created_at_event_id as created_at_event_id
                ORDER BY i.instance_id
            """
            result = client._execute_cypher(query)

        instances = []
        for record in result:
            instances.append({
                "instance_id": str(record.get("instance_id", "")).strip('"'),
                "quote": str(record.get("quote", "")).strip('"'),
                "source_id": str(record.get("source_id", "")).strip('"'),
                # ADR-102 §3: FK to graph_epochs.event_id (nullable, pre-ADR-203).
                "created_at_event_id": _parse_nullable_int(record.get("created_at_event_id")),
            })

        return instances

    @staticmethod
    def export_evidence(client: AGEClient, ontology: Optional[str] = None) -> List[Dict[str, Any]]:
        """Export EVIDENCED_BY links as {concept_id, instance_id} (ADR-102, normalized).

        The Concept→Instance evidence relationship is M:N. Carrying it as a separate
        link stream keeps instance records unique (quote stored once) and lets the
        restore reconstruct EVIDENCED_BY edges. Filtered by the instance's source
        ontology when ``ontology`` is given.
        """
        if ontology:
            query = """
                MATCH (c:Concept)-[:EVIDENCED_BY]->(i:Instance)-[:FROM_SOURCE]->(s:Source {document: $ontology})
                RETURN c.concept_id as concept_id, i.instance_id as instance_id
                ORDER BY c.concept_id, i.instance_id
            """
            result = client._execute_cypher(query, params={"ontology": ontology})
        else:
            query = """
                MATCH (c:Concept)-[:EVIDENCED_BY]->(i:Instance)
                RETURN c.concept_id as concept_id, i.instance_id as instance_id
                ORDER BY c.concept_id, i.instance_id
            """
            result = client._execute_cypher(query)

        return [
            {
                "concept_id": str(r.get("concept_id", "")).strip('"'),
                "instance_id": str(r.get("instance_id", "")).strip('"'),
            }
            for r in result
        ]

    @staticmethod
    def export_relationships(client: AGEClient, ontology: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Export concept relationships

        Args:
            client: AGEClient instance
            ontology: Optional ontology filter

        Returns:
            List of relationship dictionaries
        """
        if ontology:
            # Apache AGE: Can't use path patterns in WHERE clause
            # Instead, MATCH concepts via their source relationships first
            query = """
                MATCH (c1:Concept)-[:APPEARS]->(s:Source {document: $ontology})
                MATCH (c1)-[r]->(c2:Concept)
                RETURN c1.concept_id as from_concept,
                       c2.concept_id as to_concept,
                       type(r) as relationship_type,
                       properties(r) as properties
                ORDER BY c1.concept_id, c2.concept_id
            """
            result = client._execute_cypher(query, params={"ontology": ontology})
        else:
            query = """
                MATCH (c1:Concept)-[r]->(c2:Concept)
                RETURN c1.concept_id as from_concept,
                       c2.concept_id as to_concept,
                       type(r) as relationship_type,
                       properties(r) as properties
                ORDER BY c1.concept_id, c2.concept_id
            """
            result = client._execute_cypher(query)

        relationships = []
        for record in result:
            # Parse properties (JSON object)
            properties_raw = record.get("properties", "{}")
            try:
                properties = json.loads(str(properties_raw)) if properties_raw else {}
            except json.JSONDecodeError:
                properties = {}

            relationships.append({
                "from": str(record.get("from_concept", "")).strip('"'),
                "to": str(record.get("to_concept", "")).strip('"'),
                "type": str(record.get("relationship_type", "")).strip('"'),
                "properties": properties
            })

        return relationships

    @staticmethod
    def export_vocabulary(client: AGEClient) -> List[Dict[str, Any]]:
        """
        Export relationship vocabulary table (ADR-032)

        Exports all edge types from kg_api.relationship_vocabulary table,
        including builtin types and extended vocabulary discovered during ingestion.
        This preserves vocabulary state across backup/restore cycles.

        Args:
            client: AGEClient instance

        Returns:
            List of vocabulary entry dictionaries
        """
        # Query vocabulary table directly (PostgreSQL, not Cypher)
        conn = client.pool.getconn()
        try:
            import psycopg2.extras
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("""
                    SELECT relationship_type, description, category, added_by,
                           added_at, usage_count, is_active, is_builtin,
                           synonyms, deprecation_reason, embedding_model,
                           embedding_generated_at, embedding
                    FROM kg_api.relationship_vocabulary
                    ORDER BY relationship_type
                """)
                results = cur.fetchall()

                vocabulary = []
                for row in results:
                    # Convert row to dict and handle type conversions
                    entry = dict(row)

                    # Handle synonyms field (VARCHAR[] array, not JSONB)
                    # PostgreSQL returns arrays as Python lists
                    if entry.get('synonyms'):
                        # Already a list from psycopg2, keep as-is
                        entry['synonyms'] = list(entry['synonyms']) if entry['synonyms'] else None
                    else:
                        entry['synonyms'] = None

                    # Handle embedding field (JSONB)
                    if entry.get('embedding'):
                        try:
                            entry['embedding'] = json.loads(entry['embedding']) if isinstance(entry['embedding'], str) else entry['embedding']
                        except (json.JSONDecodeError, TypeError):
                            entry['embedding'] = None

                    # Convert datetime to ISO string
                    if entry.get('added_at'):
                        entry['added_at'] = entry['added_at'].isoformat() if hasattr(entry['added_at'], 'isoformat') else str(entry['added_at'])

                    if entry.get('embedding_generated_at'):
                        entry['embedding_generated_at'] = entry['embedding_generated_at'].isoformat() if hasattr(entry['embedding_generated_at'], 'isoformat') else str(entry['embedding_generated_at'])

                    vocabulary.append(entry)

                return vocabulary

        finally:
            conn.commit()
            client.pool.putconn(conn)

    @staticmethod
    def _log_vocabulary_summary(relationships: List[Dict[str, Any]], vocabulary: List[Dict[str, Any]]):
        """
        Log vocabulary-aware summary of backed up relationships (ADR-032)

        Instead of logging every relationship, provide a high-level view of
        edge type distribution similar to kg db stats.

        Args:
            relationships: List of relationship dictionaries
            vocabulary: List of vocabulary entry dictionaries
        """
        from collections import Counter
        import logging

        logger = logging.getLogger(__name__)

        # Count edge types in relationships
        edge_type_counts = Counter(rel["type"] for rel in relationships)
        unique_types = len(edge_type_counts)

        # Categorize edge types
        builtin_types = set(v["relationship_type"] for v in vocabulary if v.get("is_builtin", False))

        builtin_count = 0
        custom_count = 0
        builtin_edges = 0
        custom_edges = 0

        for edge_type, count in edge_type_counts.items():
            if edge_type in builtin_types:
                builtin_count += 1
                builtin_edges += count
            else:
                custom_count += 1
                custom_edges += count

        # Get top 5 edge types
        top_types = edge_type_counts.most_common(5)

        # Log as structured info messages (appears in API logs)
        logger.info(f"Relationships: {len(relationships)} edges across {unique_types} types ({builtin_count} builtin, {custom_count} custom)")

        if top_types:
            top_list = ", ".join(f"{t}({c})" for t, c in top_types)
            logger.info(f"Top edge types: {top_list}")

    # ------------------------------------------------------------------
    # kg-backup/2 export (ADR-102 §5; docs/reference/BACKUP_OBJECT_SPEC.md).
    # The pure build_kg_backup_v2() assembles the self-describing object from
    # already-fetched lists so it is unit-testable WITHOUT a database;
    # export_kg_backup_v2() is the thin DB-fetching wrapper.
    # ------------------------------------------------------------------

    @staticmethod
    def export_embedding_profiles(client: AGEClient) -> List[Dict[str, Any]]:
        """Fetch embedding profiles as portable header descriptors (spec §3.2).

        Returns profile dicts: identity ``{provider}:{model}@{dims}``, vector_space,
        image_vector_space, name, multimodal — active profile first (index 0).
        Returns [] if kg_api.embedding_profile is absent (pre-migration-055).
        """
        conn = client.pool.getconn()
        try:
            import psycopg2.extras
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("SELECT to_regclass('kg_api.embedding_profile') IS NOT NULL AS present")
                if not cur.fetchone()["present"]:
                    return []
                cur.execute("""
                    SELECT text_provider, text_model_name, text_dimensions,
                           vector_space, image_vector_space, name, multimodal
                    FROM kg_api.embedding_profile
                    ORDER BY active DESC, name
                """)
                profiles = []
                for row in cur.fetchall():
                    profiles.append({
                        "identity": f"{row['text_provider']}:{row['text_model_name']}@{row['text_dimensions']}",
                        "vector_space": row.get("vector_space"),
                        "image_vector_space": row.get("image_vector_space"),
                        "name": row.get("name"),
                        "multimodal": bool(row.get("multimodal")),
                    })
                return profiles
        finally:
            conn.commit()
            client.pool.putconn(conn)

    @staticmethod
    def export_epoch_kinds(client: AGEClient) -> List[Dict[str, Any]]:
        """Fetch the kg_api.graph_epoch_kinds lookup rows (migration 064)."""
        conn = client.pool.getconn()
        try:
            import psycopg2.extras
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("SELECT to_regclass('kg_api.graph_epoch_kinds') IS NOT NULL AS present")
                if not cur.fetchone()["present"]:
                    return []
                cur.execute("""
                    SELECT kind, semantic_wallclock, description
                    FROM kg_api.graph_epoch_kinds ORDER BY kind
                """)
                return [dict(r) for r in cur.fetchall()]
        finally:
            conn.commit()
            client.pool.putconn(conn)

    @staticmethod
    def export_graph_epochs(client: AGEClient) -> List[Dict[str, Any]]:
        """Fetch the kg_api.graph_epochs event log (migrations 063/076).

        The epoch log is PRIMARY history — it cannot be recomputed from the final
        graph — so it is ALWAYS exported. Restore decides whether to replay it
        (faithful) or collapse to a single restore event (simple) — ADR-102 §3.
        """
        conn = client.pool.getconn()
        try:
            import psycopg2.extras
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("SELECT to_regclass('kg_api.graph_epochs') IS NOT NULL AS present")
                if not cur.fetchone()["present"]:
                    return []
                cur.execute("""
                    SELECT event_id, occurred_at, kind, actor, counter_after, metadata
                    FROM kg_api.graph_epochs ORDER BY event_id
                """)
                rows = []
                for r in cur.fetchall():
                    d = dict(r)
                    occ = d.get("occurred_at")
                    if occ is not None and hasattr(occ, "isoformat"):
                        d["occurred_at"] = occ.isoformat()
                    rows.append(d)
                return rows
        finally:
            conn.commit()
            client.pool.putconn(conn)

    @staticmethod
    def build_kg_backup_v2(
        *,
        concepts: List[Dict[str, Any]],
        sources: List[Dict[str, Any]],
        instances: List[Dict[str, Any]],
        evidence: List[Dict[str, Any]],
        relationships: List[Dict[str, Any]],
        vocabulary: List[Dict[str, Any]],
        embedding_profiles: List[Dict[str, Any]],
        epoch_kinds: List[Dict[str, Any]],
        graph_epochs: List[Dict[str, Any]],
        schema_version: int,
        source_platform: str = "knowledge-graph-system",
        source_version: str = "unknown",
        exported_at: Optional[str] = None,
        ontology: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Assemble a kg-backup/2 object from already-fetched lists — PURE (no I/O).

        Builds the declarative header (interned dictionaries) and the bulk region
        (references by index), per docs/reference/BACKUP_OBJECT_SPEC.md. Separated
        from DB fetching so it is unit-testable against the offline validator.

        - Relationship types / content types / epoch kinds / actors are interned
          into header dictionaries; bulk records cite them by integer index.
        - Concepts use the record→backup cascade (no ontology tier, ADR-102 P2):
          with one active profile, concepts carry no per-record profile ref and
          inherit ``header.default_embedding_profile``.
        - Derived products are not present (caller must not pass them).
        """
        exported_at = exported_at or (datetime.utcnow().isoformat() + "Z")

        # relationship-type dictionary: vocab types, plus any dynamic edge type
        # actually used that is missing from the vocabulary table (so every edge
        # `type` index resolves in the header).
        header_vocab = list(vocabulary)
        rel_type_index: Dict[str, int] = {}
        for i, v in enumerate(header_vocab):
            rt = v.get("relationship_type")
            if rt is not None:
                rel_type_index.setdefault(rt, i)
        for r in relationships:
            t = r.get("type")
            if t is not None and t not in rel_type_index:
                rel_type_index[t] = len(header_vocab)
                header_vocab.append({"relationship_type": t})

        # content-type dictionary (distinct, first-seen order)
        content_types: List[str] = []
        ct_index: Dict[str, int] = {}
        for s in sources:
            ct = s.get("content_type")
            if isinstance(ct, str) and ct not in ct_index:
                ct_index[ct] = len(content_types)
                content_types.append(ct)

        # epoch-kind dictionary (lookup rows + any kind present only in the log)
        epoch_kinds = list(epoch_kinds)
        kind_index: Dict[str, int] = {}
        for i, k in enumerate(epoch_kinds):
            if k.get("kind") is not None:
                kind_index.setdefault(k["kind"], i)
        # actor dictionary (distinct, from the epoch log)
        actors: List[str] = []
        actor_index: Dict[str, int] = {}
        for ep in graph_epochs:
            k = ep.get("kind")
            if k is not None and k not in kind_index:
                kind_index[k] = len(epoch_kinds)
                epoch_kinds.append({"kind": k})
            a = ep.get("actor")
            if a is not None and a not in actor_index:
                actor_index[a] = len(actors)
                actors.append(a)

        # ontologies (with their default profile index = active profile)
        if ontology:
            ontologies = [{"name": ontology, "default_embedding_profile": 0}]
        else:
            seen: List[str] = []
            for s in sources:
                doc = s.get("document")
                if doc and doc not in seen:
                    seen.append(doc)
            ontologies = [{"name": d, "default_embedding_profile": 0} for d in seen]

        header = {
            "format_version": KG_BACKUP_FORMAT_VERSION,
            "source": {"platform": source_platform, "version": source_version},
            "exported_at": exported_at,
            "schema_version": schema_version,
            "embedding_profiles": embedding_profiles,
            "default_embedding_profile": 0 if embedding_profiles else None,
            "relationship_vocabulary": header_vocab,
            "epoch_kinds": epoch_kinds,
            "actors": actors,
            "content_types": content_types,
            "ontologies": ontologies,
        }

        # bulk: intern references by index
        bulk_sources = []
        for s in sources:
            s2 = dict(s)
            ct = s2.get("content_type")
            if isinstance(ct, str):
                s2["content_type"] = ct_index[ct]
            bulk_sources.append(s2)

        bulk_rels = []
        for r in relationships:
            r2 = dict(r)
            t = r2.get("type")
            if t is not None:
                r2["type"] = rel_type_index[t]
            bulk_rels.append(r2)

        bulk_epochs = []
        for ep in graph_epochs:
            e2 = dict(ep)
            k = e2.get("kind")
            if k is not None:
                e2["kind"] = kind_index[k]
            a = e2.get("actor")
            e2["actor"] = actor_index[a] if a is not None else None
            bulk_epochs.append(e2)

        return {
            "header": header,
            "bulk": {
                "concepts": concepts,
                "sources": bulk_sources,
                "instances": instances,
                "evidence": evidence,
                "relationships": bulk_rels,
                "vocabulary": vocabulary,
                "graph_epochs": bulk_epochs,
            },
        }

    @staticmethod
    def export_kg_backup_v2(client: AGEClient, ontology: Optional[str] = None) -> Dict[str, Any]:
        """Export the graph as a kg-backup/2 object (ADR-102 §5).

        Thin DB wrapper: fetches every primary-input stream + the header
        dictionaries, then delegates to the pure build_kg_backup_v2(). Derived
        products (projections, artifacts/scores) are intentionally excluded
        (ADR-102 §4) — they regenerate post-restore.
        """
        Console.info("Exporting graph as kg-backup/2...")
        concepts = DataExporter.export_concepts(client, ontology)
        sources = DataExporter.export_sources(client, ontology)
        instances = DataExporter.export_instances(client, ontology)
        evidence = DataExporter.export_evidence(client, ontology)
        relationships = DataExporter.export_relationships(client, ontology)
        vocabulary = DataExporter.export_vocabulary(client)
        embedding_profiles = DataExporter.export_embedding_profiles(client)
        epoch_kinds = DataExporter.export_epoch_kinds(client)
        graph_epochs = DataExporter.export_graph_epochs(client)
        DataExporter._log_vocabulary_summary(relationships, vocabulary)

        return DataExporter.build_kg_backup_v2(
            concepts=concepts, sources=sources, instances=instances,
            evidence=evidence, relationships=relationships, vocabulary=vocabulary,
            embedding_profiles=embedding_profiles, epoch_kinds=epoch_kinds,
            graph_epochs=graph_epochs,
            schema_version=BackupFormat.get_schema_version(client),
            ontology=ontology,
        )


def _execute_with_age_retry(client, query, params=None, *, fetch_one=False, max_retries=5):
    """Execute a Cypher statement with AGE's first-use + MVCC retry backoff.

    Apache AGE lazily creates the backing table the first time a label/edge-type
    is used; concurrent worker threads racing that creation surface as
    ``relation "..." already exists``. Concurrent MERGEs on the same node/edge
    surface as ``Entity failed to be updated`` (MVCC). Both are transient — retry
    with linear backoff. Lifted from the legacy importer so the single kg-backup/2
    clone writer shares the same proven path (ADR-102 P3).
    """
    import time
    import re
    for attempt in range(max_retries + 1):
        try:
            return client._execute_cypher(query, params=params, fetch_one=fetch_one)
        except Exception as e:
            es = str(e)
            # Only genuinely transient AGE conditions are retried: first-use label
            # table creation racing across threads, and MVCC write conflicts. A
            # malformed SET is deterministic and must surface, not be masked.
            transient = (
                "already exists" in es
                or "Entity failed to be updated" in es
            )
            if transient and attempt < max_retries:
                m = re.search(r'relation "(\w+)" already exists', es)
                if m:
                    Console.info(f"  Initializing AGE label: {m.group(1)}")
                time.sleep(0.1 * (attempt + 1))
                continue
            raise


def _progress(progress_callback, stage, current, total, every=10):
    """Emit console + job progress for an import stage every ``every`` items."""
    if total and (current % every == 0 or current == total):
        Console.progress(current, total, stage.capitalize())
        if progress_callback:
            progress_callback(stage, current, total, (current / total) * 100)


def _run_parallel(items, fn, max_workers):
    """Submit ``fn(item)`` for every item to a thread pool; raise the first error."""
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(fn, it) for it in items]
        for future in as_completed(futures):
            future.result()


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

    def counts(self):
        """Return record counts per bulk stream (for stats/logging)."""
        b = self.bulk
        return {k: len(b.get(k, [])) for k in
                ("concepts", "sources", "instances", "evidence", "relationships", "vocabulary")}

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


class DataImporter:
    """Import a kg-backup/2 object into the graph (ADR-102 P3).

    Single-path: consumes the one backup model via :class:`KgBackupV2Reader`. The
    clone writer (:meth:`_import_kg_backup_v2`) preserves app-assigned ids 1:1, which
    is correct for an empty target. Adjacent-mode ID remapping and the merge modes
    (idempotent / adjacent / integration) are added in P4.
    """

    _INSTANCE_Q = """
        MATCH (s:Source {source_id: $source_id})
        MERGE (i:Instance {instance_id: $instance_id})
        SET i.quote = $quote,
            i.created_at_event_id = $created_at_event_id
        MERGE (i)-[:FROM_SOURCE]->(s)
    """

    # Reconstruct the M:N EVIDENCED_BY edge and the derived APPEARS edge by joining
    # the concept to the instance's already-created source (ADR-102 §5.3.1).
    _EVIDENCE_Q = """
        MATCH (c:Concept {concept_id: $concept_id})
        MATCH (i:Instance {instance_id: $instance_id})-[:FROM_SOURCE]->(s:Source)
        MERGE (c)-[:EVIDENCED_BY]->(i)
        MERGE (c)-[:APPEARS]->(s)
    """

    @staticmethod
    def validate_backup(backup_data: Dict[str, Any]) -> bool:
        """Validate that ``backup_data`` is a readable kg-backup object.

        Constructs a :class:`KgBackupV2Reader`, which negotiates the format and
        refuses anything that is not ``kg-backup/<=2``. Raises ``ValueError`` on
        failure; returns ``True`` when readable. The thorough field-level oracle
        lives in the offline validator (``scripts/development/lint/lint_backup.py``).
        """
        KgBackupV2Reader(backup_data)
        return True

    @staticmethod
    def import_backup(client: AGEClient, backup_data: Dict[str, Any],
                      overwrite_existing: bool = False,
                      progress_callback: Optional[callable] = None,
                      max_workers: int = 2,
                      epoch_restamp: Optional[Dict[str, int]] = None,
                      event_id_map: Optional[Dict[int, int]] = None) -> Dict[str, int]:
        """Import a kg-backup/2 object — the single backup model's front-door.

        Args:
            client: AGEClient instance
            backup_data: Parsed kg-backup/2 object (``{header, bulk}``)
            overwrite_existing: If True, update existing nodes; if False, preserve them
            progress_callback: Optional callback(stage, current, total, percent)
            max_workers: Parallel workers for instances/evidence/relationships
            epoch_restamp: ADR-102 P5 epoch-simple restamp. When provided,
                ``{"event_id": int, "concept_epoch": int}`` overrides the carried
                per-record epoch stamps so every restored node points at LOCAL
                clocks: instances' ``created_at_event_id`` → the one restore
                ``event_id`` (a real ``graph_epochs`` row in this target — carried
                ids would dangle), and concepts' ``created_at_epoch`` /
                ``last_seen_epoch`` → the target's current ``concept_epoch``
                (a separate counter; carrying a foreign value future-dates concept
                vitality). When None the carried stamps are preserved verbatim
                (faithful — used by checkpoint rollback and P5-faithful replay).
            event_id_map: ADR-102 P5-faithful replay. When provided, each
                instance's carried ``created_at_event_id`` is remapped through this
                ``{old_event_id: new_event_id}`` table (the freshly-minted local
                epoch ids from the faithful replay). Mutually exclusive with
                ``epoch_restamp`` (simple collapses to one id; faithful preserves
                the per-event structure). Concepts are NOT remapped here — faithful
                carries their original epochs and the worker sets the counter.

        Returns:
            Stats: vocabulary_imported, concepts_created, sources_created,
            instances_created, relationships_created.
        """
        reader = KgBackupV2Reader(backup_data)
        return DataImporter._import_kg_backup_v2(
            client, reader,
            overwrite_existing=overwrite_existing,
            progress_callback=progress_callback,
            max_workers=max_workers,
            epoch_restamp=epoch_restamp,
            event_id_map=event_id_map,
        )

    @staticmethod
    def _import_kg_backup_v2(client: AGEClient, reader: "KgBackupV2Reader", *,
                             overwrite_existing: bool = False,
                             progress_callback: Optional[callable] = None,
                             max_workers: int = 2,
                             epoch_restamp: Optional[Dict[str, int]] = None,
                             event_id_map: Optional[Dict[int, int]] = None) -> Dict[str, int]:
        """Clone-path writer: import normalized records, preserving ids 1:1.

        Order matters: vocabulary (before relationships, ADR-032) → concepts →
        sources → instances (+FROM_SOURCE) → evidence (EVIDENCED_BY + derived
        APPEARS) → relationships. Clone preserves ids, so edge ``learned_id`` needs
        no remap here (that is P4 adjacent mode).

        ``epoch_restamp`` (P5 epoch-simple) / ``event_id_map`` (P5-faithful) control
        instance epoch stamping — see ``import_backup`` for the contract.
        """
        restamp_event_id = epoch_restamp.get("event_id") if epoch_restamp else None
        restamp_concept_epoch = epoch_restamp.get("concept_epoch") if epoch_restamp else None
        stats = {
            "vocabulary_imported": 0,
            "concepts_created": 0,
            "sources_created": 0,
            "instances_created": 0,
            "relationships_created": 0,
        }

        vocab = reader.vocabulary()
        if vocab:
            Console.info("Importing vocabulary...")
            DataImporter._import_vocabulary(client, vocab, progress_callback)
            stats["vocabulary_imported"] = len(vocab)

        concepts = list(reader.concepts())
        Console.info("Importing concepts...")
        DataImporter._import_concepts(client, concepts, overwrite_existing, progress_callback,
                                      restamp_epoch=restamp_concept_epoch)
        stats["concepts_created"] = len(concepts)

        sources = list(reader.sources())
        Console.info("Importing sources...")
        DataImporter._import_sources(client, sources, progress_callback)
        stats["sources_created"] = len(sources)

        instances = list(reader.instances())
        Console.info("Importing instances...")
        DataImporter._import_instances(client, instances, progress_callback, max_workers,
                                       restamp_event_id=restamp_event_id,
                                       event_id_map=event_id_map)
        stats["instances_created"] = len(instances)

        evidence_map = reader.evidence_by_instance()
        pairs = [(cid, iid) for iid, cids in evidence_map.items() for cid in cids]
        if pairs:
            Console.info(f"Reconstructing {len(pairs)} evidence links (EVIDENCED_BY + APPEARS)...")
            DataImporter._import_evidence(client, pairs, max_workers)

        rels = list(reader.relationships())
        Console.info("Importing relationships...")
        stats["relationships_created"] = DataImporter._import_relationships(
            client, rels, progress_callback, max_workers
        )

        return stats

    @staticmethod
    def _import_vocabulary(client: AGEClient, vocabulary: List[Dict[str, Any]],
                           progress_callback: Optional[callable] = None) -> None:
        """Import relationship vocabulary: SQL rows + :VocabType graph nodes.

        Ported from the original importer (ADR-032 / ADR-048): upserts
        kg_api.relationship_vocabulary, then MERGEs the :VocabType / :VocabCategory
        nodes. Shared by the single import path.
        """
        total_vocab = len(vocabulary)
        conn = client.pool.getconn()
        try:
            with conn.cursor() as cur:
                for i, entry in enumerate(vocabulary):
                    current = i + 1
                    Console.progress(current, total_vocab, "Vocabulary")
                    if progress_callback and current % 10 == 0:
                        progress_callback("vocabulary", current, total_vocab,
                                          (current / total_vocab) * 100)

                    synonyms_array = entry.get('synonyms') if entry.get('synonyms') else None
                    embedding_json = json.dumps(entry.get('embedding')) if entry.get('embedding') else None

                    cur.execute("""
                        INSERT INTO kg_api.relationship_vocabulary
                            (relationship_type, description, category, added_by, added_at,
                             usage_count, is_active, is_builtin, synonyms, deprecation_reason,
                             embedding_model, embedding_generated_at, embedding)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                        ON CONFLICT (relationship_type) DO UPDATE SET
                            description = EXCLUDED.description,
                            category = EXCLUDED.category,
                            added_by = EXCLUDED.added_by,
                            added_at = EXCLUDED.added_at,
                            usage_count = EXCLUDED.usage_count,
                            is_active = EXCLUDED.is_active,
                            is_builtin = EXCLUDED.is_builtin,
                            synonyms = EXCLUDED.synonyms,
                            deprecation_reason = EXCLUDED.deprecation_reason,
                            embedding_model = EXCLUDED.embedding_model,
                            embedding_generated_at = EXCLUDED.embedding_generated_at,
                            embedding = EXCLUDED.embedding
                    """, (
                        entry.get('relationship_type'),
                        entry.get('description'),
                        entry.get('category'),
                        entry.get('added_by'),
                        entry.get('added_at'),
                        entry.get('usage_count', 0),
                        entry.get('is_active', True),
                        entry.get('is_builtin', False),
                        synonyms_array,
                        entry.get('deprecation_reason'),
                        entry.get('embedding_model'),
                        entry.get('embedding_generated_at'),
                        embedding_json
                    ))
            conn.commit()
        finally:
            client.pool.putconn(conn)

        # Create :VocabType graph nodes (ADR-048) after the SQL import.
        Console.info("  Creating vocabulary graph nodes...")
        for i, entry in enumerate(vocabulary):
            relationship_type = entry.get('relationship_type')
            try:
                vocab_query = """
                    MERGE (v:VocabType {name: $name})
                    SET v.description = $description,
                        v.is_builtin = $is_builtin,
                        v.is_active = $is_active,
                        v.added_by = $added_by,
                        v.usage_count = $usage_count,
                        v.direction_semantics = $direction_semantics
                    WITH v
                    MERGE (c:VocabCategory {name: $category})
                    MERGE (v)-[:IN_CATEGORY]->(c)
                    RETURN v.name as name
                """
                params = {
                    "name": relationship_type,
                    "category": entry.get('category', 'unknown'),
                    "description": entry.get('description', ''),
                    "is_builtin": 't' if entry.get('is_builtin', False) else 'f',
                    "is_active": 't' if entry.get('is_active', True) else 'f',
                    "added_by": entry.get('added_by', 'system'),
                    "usage_count": entry.get('usage_count', 0),
                    "direction_semantics": entry.get('direction_semantics'),
                }
                client._execute_cypher(vocab_query, params)
                if (i + 1) % 10 == 0:
                    Console.progress(i + 1, total_vocab, "Graph nodes")
            except Exception as e:
                # SQL data is already imported — log but don't fail the restore.
                Console.warning(f"  Failed to create graph node for '{relationship_type}': {e}")

        if progress_callback and total_vocab > 0:
            progress_callback("vocabulary", total_vocab, total_vocab, 100.0)

    @staticmethod
    def _import_concepts(client: AGEClient, concepts: List[Dict[str, Any]],
                         overwrite_existing: bool, progress_callback,
                         restamp_epoch: Optional[int] = None) -> None:
        """MERGE concepts, carrying the ADR-102 §3 epoch stamps.

        ``restamp_epoch`` (ADR-102 P5 epoch-simple): when set, override the carried
        ``created_at_epoch`` / ``last_seen_epoch`` with this target-local concept
        epoch (a value in the ``document_ingestion_counter`` space). Carried foreign
        values future-date concept vitality, so a restore into any non-pristine
        target restamps to "now".
        """
        total = len(concepts)
        if overwrite_existing:
            query = """
                MERGE (c:Concept {concept_id: $concept_id})
                SET c.label = $label,
                    c.search_terms = $search_terms,
                    c.embedding = $embedding,
                    c.created_at_epoch = $created_at_epoch,
                    c.last_seen_epoch = $last_seen_epoch
            """
        else:
            # Preserve an existing concept's properties (AGE has no ON CREATE SET).
            query = """
                OPTIONAL MATCH (existing:Concept {concept_id: $concept_id})
                WITH existing
                MERGE (c:Concept {concept_id: $concept_id})
                SET c.label = CASE WHEN existing IS NULL THEN $label ELSE c.label END,
                    c.search_terms = CASE WHEN existing IS NULL THEN $search_terms ELSE c.search_terms END,
                    c.embedding = CASE WHEN existing IS NULL THEN $embedding ELSE c.embedding END,
                    c.created_at_epoch = CASE WHEN existing IS NULL THEN $created_at_epoch ELSE c.created_at_epoch END,
                    c.last_seen_epoch = CASE WHEN existing IS NULL THEN $last_seen_epoch ELSE c.last_seen_epoch END
            """
        for i, c in enumerate(concepts):
            params = {
                "concept_id": c["concept_id"],
                "label": c.get("label"),
                "search_terms": c.get("search_terms", []),
                "embedding": c.get("embedding", []),
                "created_at_epoch": c.get("created_at_epoch"),
                "last_seen_epoch": c.get("last_seen_epoch"),
            }
            if restamp_epoch is not None:
                params["created_at_epoch"] = restamp_epoch
                params["last_seen_epoch"] = restamp_epoch
            _execute_with_age_retry(client, query, params)
            _progress(progress_callback, "concepts", i + 1, total)

    @staticmethod
    def _import_sources(client: AGEClient, sources: List[Dict[str, Any]],
                        progress_callback) -> None:
        """MERGE sources, including optional Garage/media keys when present (ADR-081)."""
        total = len(sources)
        for i, s in enumerate(sources):
            query = """
                MERGE (s:Source {source_id: $source_id})
                SET s.document = $document,
                    s.file_path = $file_path,
                    s.paragraph = $paragraph,
                    s.full_text = $full_text
            """
            params = {
                "source_id": s["source_id"],
                "document": s.get("document"),
                "file_path": s.get("file_path"),
                "paragraph": s.get("paragraph"),
                "full_text": s.get("full_text"),
            }
            if s.get("garage_key"):
                query = query.rstrip() + ",\n                    s.garage_key = $garage_key"
                params["garage_key"] = s["garage_key"]
            if s.get("content_type"):
                query = query.rstrip() + ",\n                    s.content_type = $content_type"
                params["content_type"] = s["content_type"]
            if s.get("storage_key"):
                query = query.rstrip() + ",\n                    s.storage_key = $storage_key"
                params["storage_key"] = s["storage_key"]
            _execute_with_age_retry(client, query, params)
            _progress(progress_callback, "sources", i + 1, total, every=1)

    @staticmethod
    def _import_instances(client: AGEClient, instances: List[Dict[str, Any]],
                          progress_callback, max_workers: int,
                          restamp_event_id: Optional[int] = None,
                          event_id_map: Optional[Dict[int, int]] = None) -> None:
        """MERGE instances and their FROM_SOURCE edges in parallel.

        Instance ``created_at_event_id`` resolution (mutually exclusive):
        - ``event_id_map`` (P5-faithful): remap the carried id through the
          {old: new} faithful-replay table (``.get(old, old)`` — an unmapped or
          null carried id passes through).
        - ``restamp_event_id`` (P5 epoch-simple): override every instance with this
          one restore event id (carried ids would dangle — the simple path does not
          replay ``graph_epochs``).
        - neither: carry verbatim (checkpoint rollback).
        """
        total = len(instances)
        lock = threading.Lock()
        done = {"n": 0}

        def _event_id(inst):
            carried = inst.get("created_at_event_id")
            if event_id_map is not None:
                return event_id_map.get(carried, carried)
            if restamp_event_id is not None:
                return restamp_event_id
            return carried

        def work(inst):
            params = {
                "instance_id": inst["instance_id"],
                "quote": inst.get("quote", ""),
                "source_id": inst["source_id"],
                "created_at_event_id": _event_id(inst),
            }
            _execute_with_age_retry(client, DataImporter._INSTANCE_Q, params)
            with lock:
                done["n"] += 1
                _progress(progress_callback, "instances", done["n"], total)

        _run_parallel(instances, work, max_workers)

    @staticmethod
    def _import_evidence(client: AGEClient, pairs: List, max_workers: int) -> None:
        """Reconstruct EVIDENCED_BY + derived APPEARS edges from the evidence stream."""
        total = len(pairs)
        lock = threading.Lock()
        done = {"n": 0}

        def work(pair):
            concept_id, instance_id = pair
            _execute_with_age_retry(
                client, DataImporter._EVIDENCE_Q,
                {"concept_id": concept_id, "instance_id": instance_id},
            )
            with lock:
                done["n"] += 1
                if done["n"] % 50 == 0 or done["n"] == total:
                    Console.progress(done["n"], total, "Evidence")

        _run_parallel(pairs, work, max_workers)

    @staticmethod
    def _import_relationships(client: AGEClient, rels: List[Dict[str, Any]],
                              progress_callback, max_workers: int) -> int:
        """MERGE concept-concept relationships in parallel; return created count."""
        total = len(rels)
        lock = threading.Lock()
        done = {"n": 0, "created": 0}

        def work(rel):
            created = DataImporter._merge_relationship(client, rel)
            with lock:
                done["n"] += 1
                done["created"] += created
                _progress(progress_callback, "relationships", done["n"], total)

        _run_parallel(rels, work, max_workers)
        return done["created"]

    # Edge-property keys are simple identifiers (e.g. learned_id, confidence). AGE
    # rejects a whole-map parameter (`SET r = $props` → "SET clause expects a map"),
    # so each property is set individually with a scalar param — mirroring how the
    # ingestion path writes edge properties.
    _PROP_KEY = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

    @staticmethod
    def _merge_relationship(client: AGEClient, rel: Dict[str, Any]) -> int:
        """MERGE a single concept relationship (dynamic edge label). Returns 1 if created/matched.

        The edge label is interpolated into the Cypher text (AGE has no parameterized
        edge labels), so a backup — an untrusted-input boundary in adjacent mode — must
        not inject through ``type``. Labels are identifiers; reject anything else.
        """
        rel_type = rel["type"]  # de-interned label string
        if not isinstance(rel_type, str) or not DataImporter._PROP_KEY.match(rel_type):
            Console.warning(f"  Skipping relationship with unsafe edge type: {rel_type!r}")
            return 0
        query = f"""
            OPTIONAL MATCH (c1:Concept {{concept_id: $from_id}})
            OPTIONAL MATCH (c2:Concept {{concept_id: $to_id}})
            WITH c1, c2
            WHERE c1 IS NOT NULL AND c2 IS NOT NULL
            MERGE (c1)-[r:{rel_type}]->(c2)
        """
        params = {"from_id": rel["from"], "to_id": rel["to"]}

        set_items = []
        for idx, (key, value) in enumerate((rel.get("properties") or {}).items()):
            if not DataImporter._PROP_KEY.match(str(key)):
                Console.warning(f"  Skipping edge property with unsafe key: {key!r}")
                continue
            pkey = f"p_{idx}"
            set_items.append(f"r.{key} = ${pkey}")
            params[pkey] = value
        if set_items:
            query += "                SET " + ", ".join(set_items) + "\n"
        query += "                RETURN count(r) as created"

        result = _execute_with_age_retry(client, query, params, fetch_one=True)
        if result and int(str(result.get("created", 0))) > 0:
            return 1
        return 0

    # ------------------------------------------------------------------
    # P5-faithful epoch replay (ADR-102) — clone-only. The worker gates this
    # to an empty target + idempotent mode and orchestrates the order:
    #   _ensure_epoch_kinds -> _replay_graph_epochs(in_progress) -> import(map)
    #   -> _resolve_replayed_epochs(completed) -> _set_ingestion_counter.
    # ------------------------------------------------------------------

    @staticmethod
    def _ensure_epoch_kinds(client: AGEClient, reader: "KgBackupV2Reader") -> None:
        """Upsert the backup's epoch kinds into kg_api.graph_epoch_kinds.

        Faithful replay inserts graph_epochs rows whose ``kind`` is FK-constrained
        (migration 064) to this lookup, so any carried kind not already present must
        exist first. ON CONFLICT DO NOTHING preserves the target's own definition
        for kinds that already exist.
        """
        kinds = reader.header.get("epoch_kinds", [])
        if not kinds:
            return
        conn = client.pool.getconn()
        try:
            with conn.cursor() as cur:
                for k in kinds:
                    name = k.get("kind") if isinstance(k, dict) else k
                    if not name:
                        continue
                    wallclock = bool(k.get("semantic_wallclock", False)) if isinstance(k, dict) else False
                    desc = (k.get("description") if isinstance(k, dict) else None) or ""
                    cur.execute(
                        "INSERT INTO kg_api.graph_epoch_kinds (kind, semantic_wallclock, description) "
                        "VALUES (%s, %s, %s) ON CONFLICT (kind) DO NOTHING",
                        (name, wallclock, desc),
                    )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            client.pool.putconn(conn)

    @staticmethod
    def _replay_graph_epochs(client: AGEClient, reader: "KgBackupV2Reader",
                             status: str = "in_progress") -> Dict[int, int]:
        """Replay carried graph_epochs as NEW local events (P5-faithful).

        Inserts each carried event in original-id order, letting BIGSERIAL mint a
        fresh local event_id while carrying occurred_at/kind/actor/counter_after/
        metadata — so the replayed history's structure (count, order, node→event
        groupings, wallclock) is faithful even though the ids are new (new ids never
        collide; no sequence surgery). Returns {old_event_id: new_event_id} for
        remapping Instance.created_at_event_id.

        Inserted with ``status`` (default 'in_progress') so the committed watermark
        sits below the lowest new id and the graph reads STALE during the import;
        the worker resolves them to 'completed' once the import lands.
        """
        old_to_new: Dict[int, int] = {}
        conn = client.pool.getconn()
        try:
            with conn.cursor() as cur:
                for ep in reader.graph_epochs():
                    old_id = ep.get("event_id")
                    cur.execute(
                        "INSERT INTO kg_api.graph_epochs "
                        "(occurred_at, kind, actor, counter_after, metadata, status) "
                        "VALUES (%s::timestamptz, %s, %s, %s, %s::jsonb, %s) RETURNING event_id",
                        (
                            ep.get("occurred_at"),
                            ep.get("kind"),
                            ep.get("actor"),
                            ep.get("counter_after"),
                            json.dumps(ep.get("metadata") or {}),
                            status,
                        ),
                    )
                    new_id = cur.fetchone()[0]
                    if old_id is not None:
                        old_to_new[old_id] = new_id
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            client.pool.putconn(conn)
        return old_to_new

    @staticmethod
    def _resolve_replayed_epochs(client: AGEClient, new_event_ids: List[int],
                                 status: str = "completed") -> None:
        """Resolve replayed epoch rows to a terminal status (P5-faithful).

        Called after the import lands ('completed') or fails ('failed'). Both count
        toward the committed watermark (migration 076); completing advances the
        freshness clock to the max replayed id, failing keeps the graph stale.
        """
        if not new_event_ids:
            return
        conn = client.pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE kg_api.graph_epochs SET status = %s WHERE event_id = ANY(%s)",
                    (status, list(new_event_ids)),
                )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            client.pool.putconn(conn)

    @staticmethod
    def _set_ingestion_counter(client: AGEClient, value: int) -> None:
        """Advance document_ingestion_counter to at least ``value`` (P5-faithful).

        Faithful carries concepts' original created_at/last_seen epochs; the counter
        must be >= the max carried epoch or restored concepts read as 'from the
        future' against a lower counter (the P5 hazard) and future ingestion would
        reissue colliding epoch numbers. GREATEST keeps it monotonic.
        """
        if value is None:
            return
        conn = client.pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE graph_metrics SET counter = GREATEST(counter, %s), updated_at = NOW() "
                    "WHERE metric_name = 'document_ingestion_counter'",
                    (value,),
                )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            client.pool.putconn(conn)
