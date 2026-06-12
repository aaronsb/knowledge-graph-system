"""
kg-backup/2 export path — :class:`DataExporter` and the kg-backup/2 builder.

Reads Apache AGE graph data into the portable kg-backup/2 object shape (interned
header + bulk records). Split out of the former monolithic
``api/lib/serialization.py`` (ADR-102 P6d).
"""

import json
from datetime import datetime
from typing import Dict, Any, List, Optional

from api.app.lib.age_client import AGEClient

from ..console import Console
from .format import BackupFormat, KG_BACKUP_FORMAT_VERSION


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


def _parse_nullable_str(raw: Any) -> Optional[str]:
    """Parse a nullable string from an AGE agtype scalar.

    Distinguishes a genuinely absent/NULL property (``None`` or the literal
    ``"null"``) from an empty string, which AGE returns as ``'""'``. Used for
    optional node properties like ``Ontology.created_by``.
    """
    if raw is None:
        return None
    s = str(raw).strip()
    if s.lower() == "null":
        return None
    return s.strip('"')


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
    def export_ontologies(client: AGEClient, ontology: Optional[str] = None) -> List[Dict[str, Any]]:
        """Export :Ontology nodes as first-class records (full fidelity).

        Ontologies are first-class graph entities in the concept embedding space,
        not derivable from sources — the ``s.document`` string is only a
        denormalized cache of membership. A backup that drops them loses the
        registry that ``kg ontology list`` / the catalog browse tree depend on,
        plus the ``lifecycle_state`` (``frozen`` ontologies would silently become
        writable on restore). Round-trips with :func:`export_scoped_by` /
        :func:`export_anchored_by` and the importer's ``_import_ontologies``.

        Args:
            client: AGEClient instance
            ontology: Optional name filter (None = all ontologies)

        Returns:
            List of ontology node dictionaries with full embeddings.
        """
        if ontology:
            query = """
                MATCH (o:Ontology {name: $ontology})
                RETURN o.ontology_id as ontology_id, o.name as name,
                       o.description as description, o.embedding as embedding,
                       o.search_terms as search_terms, o.lifecycle_state as lifecycle_state,
                       o.creation_epoch as creation_epoch, o.created_by as created_by
                ORDER BY o.name
            """
            result = client._execute_cypher(query, params={"ontology": ontology})
        else:
            query = """
                MATCH (o:Ontology)
                RETURN o.ontology_id as ontology_id, o.name as name,
                       o.description as description, o.embedding as embedding,
                       o.search_terms as search_terms, o.lifecycle_state as lifecycle_state,
                       o.creation_epoch as creation_epoch, o.created_by as created_by
                ORDER BY o.name
            """
            result = client._execute_cypher(query)

        ontologies = []
        for record in result:
            try:
                search_terms = json.loads(str(record.get("search_terms", "[]")))
            except json.JSONDecodeError:
                search_terms = []
            try:
                embedding = json.loads(str(record.get("embedding", "[]")))
            except json.JSONDecodeError:
                embedding = []
            ontologies.append({
                "ontology_id": _parse_nullable_str(record.get("ontology_id")),
                "name": str(record.get("name", "")).strip('"'),
                # description normalizes null→"" (production defaults it to "" at
                # create time; the null/empty distinction carries no meaning here).
                "description": _parse_nullable_str(record.get("description")) or "",
                "embedding": embedding,
                "search_terms": search_terms,
                "lifecycle_state": _parse_nullable_str(record.get("lifecycle_state")) or "active",
                "creation_epoch": _parse_nullable_int(record.get("creation_epoch")),
                "created_by": _parse_nullable_str(record.get("created_by")),
            })

        return ontologies

    @staticmethod
    def export_scoped_by(client: AGEClient, ontology: Optional[str] = None) -> List[Dict[str, Any]]:
        """Export (:Source)-[:SCOPED_BY]->(:Ontology) edges — ontology membership.

        ``:SCOPED_BY`` is the source of truth for which ontology a source belongs
        to (``s.document`` is the denormalized cache). Exported explicitly so the
        membership graph round-trips rather than being re-derived heuristically.
        """
        if ontology:
            query = """
                MATCH (s:Source)-[:SCOPED_BY]->(o:Ontology {name: $ontology})
                RETURN s.source_id as source_id, o.name as ontology
                ORDER BY s.source_id
            """
            result = client._execute_cypher(query, params={"ontology": ontology})
        else:
            query = """
                MATCH (s:Source)-[:SCOPED_BY]->(o:Ontology)
                RETURN s.source_id as source_id, o.name as ontology
                ORDER BY s.source_id, o.name
            """
            result = client._execute_cypher(query)

        return [
            {"source_id": str(r.get("source_id", "")).strip('"'),
             "ontology": str(r.get("ontology", "")).strip('"')}
            for r in result
        ]

    @staticmethod
    def export_anchored_by(client: AGEClient, ontology: Optional[str] = None) -> List[Dict[str, Any]]:
        """Export (:Ontology)-[:ANCHORED_BY]->(:Concept) edges — founding concepts.

        Links a promoted ontology to the concept it grew from (ADR-200). The
        concept exists independently; this edge records provenance and must
        survive a clone so promotion history is not lost.
        """
        if ontology:
            query = """
                MATCH (o:Ontology {name: $ontology})-[:ANCHORED_BY]->(c:Concept)
                RETURN o.name as ontology, c.concept_id as concept_id
                ORDER BY c.concept_id
            """
            result = client._execute_cypher(query, params={"ontology": ontology})
        else:
            query = """
                MATCH (o:Ontology)-[:ANCHORED_BY]->(c:Concept)
                RETURN o.name as ontology, c.concept_id as concept_id
                ORDER BY o.name, c.concept_id
            """
            result = client._execute_cypher(query)

        return [
            {"ontology": str(r.get("ontology", "")).strip('"'),
             "concept_id": str(r.get("concept_id", "")).strip('"')}
            for r in result
        ]

    @staticmethod
    def export_documents(client: AGEClient, ontology: Optional[str] = None) -> List[Dict[str, Any]]:
        """Export :DocumentMeta nodes as first-class records (the catalog document tier).

        The document layer is NOT reconstructable from Sources: the canonical
        identity (``document_id == content_hash == sha256(document bytes)``, the
        full 71-char ``sha256:``-prefixed digest) survives on Sources only as the
        32-char ``garage_key`` prefix, so a Source-derived DocumentMeta would have a
        truncated id that breaks drill-down and re-ingest dedup (issue #505). We
        therefore serialize the layer and carry every field verbatim — especially
        ``document_id``/``content_hash`` (with prefix) and ``garage_key`` (no prefix);
        no recomputation on either side. Round-trips with :func:`export_has_source`
        and the importer's ``_import_documents``.

        Args:
            client: AGEClient instance
            ontology: Optional name filter (None = all documents)

        Returns:
            List of DocumentMeta node dictionaries.
        """
        if ontology:
            query = """
                MATCH (d:DocumentMeta {ontology: $ontology})
                RETURN d.document_id as document_id, d.content_hash as content_hash,
                       d.ontology as ontology, d.filename as filename,
                       d.garage_key as garage_key, d.content_type as content_type,
                       d.source_count as source_count, d.ingested_at as ingested_at,
                       d.ingested_by as ingested_by, d.job_id as job_id,
                       d.file_path as file_path, d.source_type as source_type,
                       d.hostname as hostname, d.storage_key as storage_key
                ORDER BY d.document_id
            """
            result = client._execute_cypher(query, params={"ontology": ontology})
        else:
            query = """
                MATCH (d:DocumentMeta)
                RETURN d.document_id as document_id, d.content_hash as content_hash,
                       d.ontology as ontology, d.filename as filename,
                       d.garage_key as garage_key, d.content_type as content_type,
                       d.source_count as source_count, d.ingested_at as ingested_at,
                       d.ingested_by as ingested_by, d.job_id as job_id,
                       d.file_path as file_path, d.source_type as source_type,
                       d.hostname as hostname, d.storage_key as storage_key
                ORDER BY d.document_id
            """
            result = client._execute_cypher(query)

        documents = []
        for record in result:
            documents.append({
                # Canonical identity — carried verbatim (with the sha256: prefix),
                # never recomputed. This is what makes restore authoritative.
                "document_id": _parse_nullable_str(record.get("document_id")),
                "content_hash": _parse_nullable_str(record.get("content_hash")),
                "ontology": _parse_nullable_str(record.get("ontology")),
                "filename": _parse_nullable_str(record.get("filename")),
                "garage_key": _parse_nullable_str(record.get("garage_key")),
                "content_type": _parse_nullable_str(record.get("content_type")),
                "source_count": _parse_nullable_int(record.get("source_count")),
                "ingested_at": _parse_nullable_str(record.get("ingested_at")),
                "ingested_by": _parse_nullable_str(record.get("ingested_by")),
                "job_id": _parse_nullable_str(record.get("job_id")),
                "file_path": _parse_nullable_str(record.get("file_path")),
                "source_type": _parse_nullable_str(record.get("source_type")),
                "hostname": _parse_nullable_str(record.get("hostname")),
                "storage_key": _parse_nullable_str(record.get("storage_key")),
            })

        return documents

    @staticmethod
    def export_has_source(client: AGEClient, ontology: Optional[str] = None) -> List[Dict[str, Any]]:
        """Export (:DocumentMeta)-[:HAS_SOURCE]->(:Source) edges — the file→chunk grouping.

        One DocumentMeta groups all the Source chunks of a file. Exported explicitly
        (keyed on the canonical ``document_id``) so the grouping round-trips rather
        than being re-derived from ``garage_key`` heuristics (issue #505).
        """
        if ontology:
            query = """
                MATCH (d:DocumentMeta {ontology: $ontology})-[:HAS_SOURCE]->(s:Source)
                RETURN d.document_id as document_id, s.source_id as source_id
                ORDER BY d.document_id, s.source_id
            """
            result = client._execute_cypher(query, params={"ontology": ontology})
        else:
            query = """
                MATCH (d:DocumentMeta)-[:HAS_SOURCE]->(s:Source)
                RETURN d.document_id as document_id, s.source_id as source_id
                ORDER BY d.document_id, s.source_id
            """
            result = client._execute_cypher(query)

        return [
            {"document_id": str(r.get("document_id", "")).strip('"'),
             "source_id": str(r.get("source_id", "")).strip('"')}
            for r in result
        ]

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
        ontologies: Optional[List[Dict[str, Any]]] = None,
        scoped_by: Optional[List[Dict[str, Any]]] = None,
        anchored_by: Optional[List[Dict[str, Any]]] = None,
        documents: Optional[List[Dict[str, Any]]] = None,
        has_source: Optional[List[Dict[str, Any]]] = None,
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

        # header.ontologies: the per-ontology embedding-profile registry (the
        # name→active-profile map the §4.1 cascade reads). Distinct from the
        # bulk.ontologies NODE stream (the ``ontologies`` parameter) — a separate
        # local so it does not shadow that parameter.
        if ontology:
            header_ontologies = [{"name": ontology, "default_embedding_profile": 0}]
        else:
            seen: List[str] = []
            for s in sources:
                doc = s.get("document")
                if doc and doc not in seen:
                    seen.append(doc)
            header_ontologies = [{"name": d, "default_embedding_profile": 0} for d in seen]

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
            "ontologies": header_ontologies,
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
                # First-class :Ontology nodes + their membership/provenance edges.
                # Not interned (small cardinality); empty for backups taken before
                # this stream existed (the reader tolerates absence).
                "ontologies": list(ontologies or []),
                "scoped_by": list(scoped_by or []),
                "anchored_by": list(anchored_by or []),
                # :DocumentMeta nodes + their HAS_SOURCE grouping (the catalog
                # document tier). Carried verbatim — canonical document_id /
                # content_hash are unrecoverable from Sources (issue #505). Empty
                # for pre-stream backups; the reader tolerates absence.
                "documents": list(documents or []),
                "has_source": list(has_source or []),
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
        ontologies = DataExporter.export_ontologies(client, ontology)
        scoped_by = DataExporter.export_scoped_by(client, ontology)
        anchored_by = DataExporter.export_anchored_by(client, ontology)
        documents = DataExporter.export_documents(client, ontology)
        has_source = DataExporter.export_has_source(client, ontology)
        DataExporter._log_vocabulary_summary(relationships, vocabulary)

        return DataExporter.build_kg_backup_v2(
            concepts=concepts, sources=sources, instances=instances,
            evidence=evidence, relationships=relationships, vocabulary=vocabulary,
            embedding_profiles=embedding_profiles, epoch_kinds=epoch_kinds,
            graph_epochs=graph_epochs,
            ontologies=ontologies, scoped_by=scoped_by, anchored_by=anchored_by,
            documents=documents, has_source=has_source,
            schema_version=BackupFormat.get_schema_version(client),
            ontology=ontology,
        )
