"""
Data serialization - Export and import operations for backup/restore

Handles conversion between Apache AGE graph data and portable JSON format,
preserving embeddings (1536-dim vectors), full text, and relationships.
"""

import json
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
    """Backup data format specification"""

    VERSION = "1.0"

    FULL_BACKUP = "full_backup"
    ONTOLOGY_BACKUP = "ontology_backup"

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

    @staticmethod
    def create_metadata(backup_type: str, ontology: Optional[str] = None, client: AGEClient = None) -> Dict[str, Any]:
        """
        Create backup metadata with schema versioning

        Args:
            backup_type: Type of backup (full_backup or ontology_backup)
            ontology: Optional ontology name
            client: AGEClient instance (needed for schema version)

        Returns:
            Metadata dictionary with version, schema_version, type, timestamp, ontology
        """
        metadata = {
            "version": BackupFormat.VERSION,
            "type": backup_type,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "ontology": ontology
        }

        # Add schema version if client provided (ADR-015: Schema Versioning)
        if client:
            metadata["schema_version"] = BackupFormat.get_schema_version(client)

        return metadata


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

    @staticmethod
    def export_full_backup(client: AGEClient) -> Dict[str, Any]:
        """
        Export entire database

        Args:
            client: AGEClient instance

        Returns:
            Full backup dictionary
        """
        Console.info("Exporting concepts...")
        concepts = DataExporter.export_concepts(client)

        Console.info("Exporting sources...")
        sources = DataExporter.export_sources(client)

        Console.info("Exporting instances...")
        instances = DataExporter.export_instances(client)

        Console.info("Exporting relationships...")
        relationships = DataExporter.export_relationships(client)

        Console.info("Exporting vocabulary...")
        vocabulary = DataExporter.export_vocabulary(client)

        # Calculate vocabulary statistics (ADR-032)
        DataExporter._log_vocabulary_summary(relationships, vocabulary)

        return {
            **BackupFormat.create_metadata(BackupFormat.FULL_BACKUP, client=client),  # Fixed: pass client for schema_version
            "statistics": {
                "concepts": len(concepts),
                "sources": len(sources),
                "instances": len(instances),
                "relationships": len(relationships),
                "vocabulary": len(vocabulary)
            },
            "data": {
                "concepts": concepts,
                "sources": sources,
                "instances": instances,
                "relationships": relationships,
                "vocabulary": vocabulary
            }
        }

    @staticmethod
    def export_ontology_backup(client: AGEClient, ontology: str) -> Dict[str, Any]:
        """
        Export specific ontology

        Args:
            client: AGEClient instance
            ontology: Ontology name

        Returns:
            Ontology backup dictionary
        """
        Console.info(f"Exporting ontology: {ontology}")

        Console.info("  - Concepts...")
        concepts = DataExporter.export_concepts(client, ontology)

        Console.info("  - Sources...")
        sources = DataExporter.export_sources(client, ontology)

        Console.info("  - Instances...")
        instances = DataExporter.export_instances(client, ontology)

        Console.info("  - Relationships...")
        relationships = DataExporter.export_relationships(client, ontology)

        Console.info("  - Vocabulary...")
        # NOTE: Vocabulary is global state, export entire vocabulary table
        # even for ontology backups to preserve extended vocabulary (ADR-032)
        vocabulary = DataExporter.export_vocabulary(client)

        # Calculate vocabulary statistics (ADR-032)
        DataExporter._log_vocabulary_summary(relationships, vocabulary)

        return {
            **BackupFormat.create_metadata(BackupFormat.ONTOLOGY_BACKUP, ontology, client=client),  # Fixed: pass client for schema_version
            "statistics": {
                "concepts": len(concepts),
                "sources": len(sources),
                "instances": len(instances),
                "relationships": len(relationships),
                "vocabulary": len(vocabulary)
            },
            "data": {
                "concepts": concepts,
                "sources": sources,
                "instances": instances,
                "relationships": relationships,
                "vocabulary": vocabulary
            }
        }

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


class DataImporter:
    """Import graph data from JSON format"""

    @staticmethod
    def validate_backup(backup_data: Dict[str, Any]) -> bool:
        """
        Validate backup format

        Args:
            backup_data: Parsed JSON backup

        Returns:
            True if valid

        Raises:
            ValueError if invalid
        """
        if "version" not in backup_data:
            raise ValueError("Missing version field in backup")

        if backup_data["version"] != BackupFormat.VERSION:
            raise ValueError(f"Unsupported backup version: {backup_data['version']}")

        if "type" not in backup_data:
            raise ValueError("Missing type field in backup")

        if backup_data["type"] not in (BackupFormat.FULL_BACKUP, BackupFormat.ONTOLOGY_BACKUP):
            raise ValueError(f"Unknown backup type: {backup_data['type']}")

        if "data" not in backup_data:
            raise ValueError("Missing data section in backup")

        required_sections = ["concepts", "sources", "instances", "relationships"]
        for section in required_sections:
            if section not in backup_data["data"]:
                raise ValueError(f"Missing {section} in backup data")

        return True

    @staticmethod
    def import_backup(client: AGEClient, backup_data: Dict[str, Any],
                     overwrite_existing: bool = False,
                     progress_callback: Optional[callable] = None,
                     max_workers: int = 2) -> Dict[str, int]:
        """
        Import backup data into database

        Args:
            client: AGEClient instance
            backup_data: Parsed backup JSON
            overwrite_existing: If True, update existing nodes; if False, skip duplicates
            progress_callback: Optional callback(stage, current, total, percent) for progress updates
            max_workers: Maximum parallel workers for instances/relationships (default: 2)

        Returns:
            Dictionary with import statistics
        """
        DataImporter.validate_backup(backup_data)

        data = backup_data["data"]
        stats = {
            "vocabulary_imported": 0,
            "concepts_created": 0,
            "sources_created": 0,
            "instances_created": 0,
            "relationships_created": 0
        }

        # Import vocabulary first (ADR-032) - needed before relationships
        if "vocabulary" in data and len(data["vocabulary"]) > 0:
            Console.info("Importing vocabulary...")
            total_vocab = len(data["vocabulary"])

            conn = client.pool.getconn()
            try:
                import psycopg2.extras
                with conn.cursor() as cur:
                    for i, entry in enumerate(data["vocabulary"]):
                        current = i + 1
                        Console.progress(current, total_vocab, "Vocabulary")

                        if progress_callback and current % 10 == 0:
                            percent = (current / total_vocab) * 100
                            progress_callback("vocabulary", current, total_vocab, percent)

                        # Prepare field values
                        # synonyms: VARCHAR[] array (not JSONB)
                        synonyms_array = entry.get('synonyms') if entry.get('synonyms') else None

                        # embedding: JSONB field
                        embedding_json = json.dumps(entry.get('embedding')) if entry.get('embedding') else None

                        # Insert or update vocabulary entry
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
                            synonyms_array,  # Fixed: VARCHAR[] array, not JSONB
                            entry.get('deprecation_reason'),
                            entry.get('embedding_model'),
                            entry.get('embedding_generated_at'),
                            embedding_json
                        ))
                        stats["vocabulary_imported"] += 1

                conn.commit()
            finally:
                client.pool.putconn(conn)

            # Create :VocabType graph nodes (ADR-048)
            # After SQL import, sync vocabulary to graph nodes
            Console.info("  Creating vocabulary graph nodes...")
            for i, entry in enumerate(data["vocabulary"]):
                current = i + 1
                relationship_type = entry.get('relationship_type')
                category = entry.get('category', 'unknown')
                description = entry.get('description', '')
                is_builtin = entry.get('is_builtin', False)
                added_by = entry.get('added_by', 'system')
                direction_semantics = entry.get('direction_semantics')

                try:
                    # Use MERGE to be idempotent (safe for re-runs)
                    # Creates both :VocabType node and :IN_CATEGORY relationship
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
                        "category": category,
                        "description": description,
                        "is_builtin": 't' if is_builtin else 'f',
                        "is_active": 't' if entry.get('is_active', True) else 'f',
                        "added_by": added_by,
                        "usage_count": entry.get('usage_count', 0),
                        "direction_semantics": direction_semantics
                    }
                    client._execute_cypher(vocab_query, params)

                    if current % 10 == 0:
                        Console.progress(current, total_vocab, "Graph nodes")
                except Exception as e:
                    # Log but don't fail the restore - SQL data is already imported
                    Console.warning(f"  Failed to create graph node for '{relationship_type}': {e}")

            if progress_callback and total_vocab > 0:
                progress_callback("vocabulary", total_vocab, total_vocab, 100.0)

        # Import concepts
        Console.info("Importing concepts...")
        total_concepts = len(data["concepts"])
        for i, concept in enumerate(data["concepts"]):
            current = i + 1
            Console.progress(current, total_concepts, "Concepts")

            # Call progress callback every 10 items
            if progress_callback and current % 10 == 0:
                percent = (current / total_concepts) * 100
                progress_callback("concepts", current, total_concepts, percent)

            if overwrite_existing:
                # Always set properties (create or update)
                merge_query = """
                    MERGE (c:Concept {concept_id: $concept_id})
                    SET c.label = $label,
                        c.search_terms = $search_terms,
                        c.embedding = $embedding
                """
            else:
                # Only set if node doesn't exist (skip if exists)
                merge_query = """
                    MERGE (c:Concept {concept_id: $concept_id})
                    ON CREATE SET c.label = $label, c.search_terms = $search_terms, c.embedding = $embedding
                """
                # AGE workaround: Use conditional CASE in SET
                merge_query = """
                    OPTIONAL MATCH (existing:Concept {concept_id: $concept_id})
                    WITH existing
                    MERGE (c:Concept {concept_id: $concept_id})
                    SET c.label = CASE WHEN existing IS NULL THEN $label ELSE c.label END,
                        c.search_terms = CASE WHEN existing IS NULL THEN $search_terms ELSE c.search_terms END,
                        c.embedding = CASE WHEN existing IS NULL THEN $embedding ELSE c.embedding END
                """

            client._execute_cypher(merge_query, params=concept)
            stats["concepts_created"] += 1

        # Final callback for concepts stage
        if progress_callback and total_concepts > 0:
            progress_callback("concepts", total_concepts, total_concepts, 100.0)

        # Import sources
        Console.info("Importing sources...")
        total_sources = len(data["sources"])
        for i, source in enumerate(data["sources"]):
            current = i + 1
            Console.progress(current, total_sources, "Sources")

            # Call progress callback every item (sources are fewer)
            if progress_callback:
                percent = (current / total_sources) * 100
                progress_callback("sources", current, total_sources, percent)

            # AGE: MERGE + SET (works for both create and update)
            # Include garage_key, content_type, storage_key if present (ADR-081)
            merge_query = """
                MERGE (s:Source {source_id: $source_id})
                SET s.document = $document,
                    s.file_path = $file_path,
                    s.paragraph = $paragraph,
                    s.full_text = $full_text
            """

            # Add optional Garage fields to SET clause if present
            if source.get("garage_key"):
                merge_query = merge_query.rstrip() + ",\n                    s.garage_key = $garage_key"
            if source.get("content_type"):
                merge_query = merge_query.rstrip() + ",\n                    s.content_type = $content_type"
            if source.get("storage_key"):
                merge_query = merge_query.rstrip() + ",\n                    s.storage_key = $storage_key"

            client._execute_cypher(merge_query, params=source)
            stats["sources_created"] += 1

        # Final callback for sources stage
        if progress_callback and total_sources > 0:
            progress_callback("sources", total_sources, total_sources, 100.0)

        # Import instances (parallel processing for performance)
        Console.info("Importing instances...")
        total_instances = len(data["instances"])


        # Thread-safe counter and lock for progress tracking
        progress_lock = threading.Lock()
        completed = {"count": 0}

        def process_instance(instance):
            """Process single instance with optimized single-query approach"""
            # Optimized: Single query instead of two
            # MATCH dependencies first, then MERGE+SET, then create relationships
            # No WITH clause needed - all variables stay in scope
            query = """
                MATCH (c:Concept {concept_id: $concept_id})
                MATCH (s:Source {source_id: $source_id})
                MERGE (i:Instance {instance_id: $instance_id})
                SET i.quote = $quote
                MERGE (c)-[:EVIDENCED_BY]->(i)
                MERGE (i)-[:FROM_SOURCE]->(s)
                MERGE (c)-[:APPEARS]->(s)
            """

            import time
            max_retries = 5
            for attempt in range(max_retries + 1):
                try:
                    client._execute_cypher(query, params=instance)
                    break
                except Exception as e:
                    error_str = str(e)
                    if "already exists" in error_str and attempt < max_retries:
                        # AGE creates label tables on first use - parallel threads may race
                        import re
                        match = re.search(r'relation "(\w+)" already exists', error_str)
                        if match:
                            Console.info(f"  Initializing AGE label: {match.group(1)}")
                        time.sleep(0.1 * (attempt + 1))
                        continue
                    elif "Entity failed to be updated" in error_str and attempt < max_retries:
                        # AGE MVCC conflict from concurrent MERGE on same node
                        time.sleep(0.1 * (attempt + 1))
                        continue
                    else:
                        raise

            # Thread-safe progress tracking
            with progress_lock:
                completed["count"] += 1
                current = completed["count"]
                if current % 10 == 0 or current == total_instances:
                    Console.progress(current, total_instances, "Instances")
                    if progress_callback:
                        percent = (current / total_instances) * 100
                        progress_callback("instances", current, total_instances, percent)

        # Process instances in parallel (configurable workers)
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(process_instance, instance)
                      for instance in data["instances"]]

            # Wait for all to complete
            for future in as_completed(futures):
                future.result()  # Raise any exceptions

        stats["instances_created"] = total_instances

        # Final callback for instances stage
        if progress_callback and total_instances > 0:
            progress_callback("instances", total_instances, total_instances, 100.0)

        # Import concept-concept relationships (parallel processing for performance)
        Console.info("Importing relationships...")
        total_relationships = len(data["relationships"])

        # Thread-safe counter and lock for progress tracking
        rel_progress_lock = threading.Lock()
        rel_completed = {"count": 0, "created": 0}

        def process_relationship(rel):
            """Process single relationship"""
            # Dynamic relationship type (IMPLIES, SUPPORTS, etc.)
            # Use OPTIONAL MATCH to handle missing nodes gracefully
            props = rel.get("properties") or {}
            if props:
                query = f"""
                    OPTIONAL MATCH (c1:Concept {{concept_id: $from_id}})
                    OPTIONAL MATCH (c2:Concept {{concept_id: $to_id}})
                    WITH c1, c2
                    WHERE c1 IS NOT NULL AND c2 IS NOT NULL
                    MERGE (c1)-[r:{rel['type']}]->(c2)
                    SET r = $properties
                    RETURN count(r) as created
                """
                params = {
                    "from_id": rel["from"],
                    "to_id": rel["to"],
                    "properties": props
                }
            else:
                # Skip SET for empty properties — AGE rejects SET r = {} with
                # "SET clause expects a map"
                query = f"""
                    OPTIONAL MATCH (c1:Concept {{concept_id: $from_id}})
                    OPTIONAL MATCH (c2:Concept {{concept_id: $to_id}})
                    WITH c1, c2
                    WHERE c1 IS NOT NULL AND c2 IS NOT NULL
                    MERGE (c1)-[r:{rel['type']}]->(c2)
                    RETURN count(r) as created
                """
                params = {
                    "from_id": rel["from"],
                    "to_id": rel["to"],
                }

            import time
            max_retries = 5
            for attempt in range(max_retries + 1):
                try:
                    result = client._execute_cypher(query, params=params, fetch_one=True)
                    break
                except Exception as e:
                    error_str = str(e)

                    if "already exists" in error_str and attempt < max_retries:
                        # AGE creates edge type tables on first use - parallel threads may race
                        import re
                        match = re.search(r'relation "(\w+)" already exists', error_str)
                        if match:
                            Console.info(f"  Initializing edge type: {match.group(1)}")
                        time.sleep(0.1 * (attempt + 1))
                        continue
                    elif "Entity failed to be updated" in error_str and attempt < max_retries:
                        # AGE MVCC conflict from concurrent MERGE on same edge
                        time.sleep(0.1 * (attempt + 1))
                        continue
                    elif "SET clause expects a map" in error_str and attempt < max_retries:
                        time.sleep(0.1 * (attempt + 1))
                        continue
                    else:
                        raise

            created = 0
            if result and int(str(result.get("created", 0))) > 0:
                created = 1

            # Thread-safe progress tracking
            with rel_progress_lock:
                rel_completed["count"] += 1
                rel_completed["created"] += created
                current = rel_completed["count"]
                if current % 10 == 0 or current == total_relationships:
                    Console.progress(current, total_relationships, "Relationships")
                    if progress_callback:
                        percent = (current / total_relationships) * 100
                        progress_callback("relationships", current, total_relationships, percent)

        # Process relationships in parallel (configurable workers)
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(process_relationship, rel)
                      for rel in data["relationships"]]

            # Wait for all to complete
            for future in as_completed(futures):
                future.result()  # Raise any exceptions

        stats["relationships_created"] = rel_completed["created"]

        # Final callback for relationships stage
        if progress_callback and total_relationships > 0:
            progress_callback("relationships", total_relationships, total_relationships, 100.0)

        return stats
