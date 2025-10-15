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

# Add parent directory to path for AGEClient import
sys.path.insert(0, str(Path(__file__).parent.parent))
from api.lib.age_client import AGEClient

from .console import Console, Colors


class BackupFormat:
    """Backup data format specification"""

    VERSION = "1.0"

    FULL_BACKUP = "full_backup"
    ONTOLOGY_BACKUP = "ontology_backup"

    @staticmethod
    def create_metadata(backup_type: str, ontology: Optional[str] = None) -> Dict[str, Any]:
        """Create backup metadata"""
        return {
            "version": BackupFormat.VERSION,
            "type": backup_type,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "ontology": ontology
        }


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
                MATCH (c:Concept)-[:APPEARS_IN]->(s:Source {document: $ontology})
                WITH DISTINCT c
                RETURN c.concept_id as concept_id,
                       c.label as label,
                       c.search_terms as search_terms,
                       c.embedding as embedding
                ORDER BY c.concept_id
            """
            result = client._execute_cypher(query, params={"ontology": ontology})
        else:
            query = """
                MATCH (c:Concept)
                RETURN c.concept_id as concept_id,
                       c.label as label,
                       c.search_terms as search_terms,
                       c.embedding as embedding
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
                "embedding": embedding  # Full 1536-dim array
            })

        return concepts

    @staticmethod
    def export_sources(client: AGEClient, ontology: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Export source nodes with full text

        Args:
            client: AGEClient instance
            ontology: Optional ontology filter

        Returns:
            List of source dictionaries
        """
        if ontology:
            query = """
                MATCH (s:Source {document: $ontology})
                RETURN s.source_id as source_id,
                       s.document as document,
                       s.file_path as file_path,
                       s.paragraph as paragraph,
                       s.full_text as full_text
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
                       s.full_text as full_text
                ORDER BY s.document, s.paragraph
            """
            result = client._execute_cypher(query)

        sources = []
        for record in result:
            # Parse agtype values
            sources.append({
                "source_id": str(record.get("source_id", "")).strip('"'),
                "document": str(record.get("document", "")).strip('"'),
                "file_path": str(record.get("file_path", "")).strip('"'),
                "paragraph": int(str(record.get("paragraph", 0))),
                "full_text": str(record.get("full_text", "")).strip('"')
            })

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
        if ontology:
            query = """
                MATCH (i:Instance)-[:FROM_SOURCE]->(s:Source {document: $ontology})
                MATCH (i)<-[:EVIDENCED_BY]-(c:Concept)
                RETURN i.instance_id as instance_id,
                       i.quote as quote,
                       c.concept_id as concept_id,
                       s.source_id as source_id
                ORDER BY i.instance_id
            """
            result = client._execute_cypher(query, params={"ontology": ontology})
        else:
            query = """
                MATCH (i:Instance)-[:FROM_SOURCE]->(s:Source)
                MATCH (i)<-[:EVIDENCED_BY]-(c:Concept)
                RETURN i.instance_id as instance_id,
                       i.quote as quote,
                       c.concept_id as concept_id,
                       s.source_id as source_id
                ORDER BY i.instance_id
            """
            result = client._execute_cypher(query)

        instances = []
        for record in result:
            instances.append({
                "instance_id": str(record.get("instance_id", "")).strip('"'),
                "quote": str(record.get("quote", "")).strip('"'),
                "concept_id": str(record.get("concept_id", "")).strip('"'),
                "source_id": str(record.get("source_id", "")).strip('"')
            })

        return instances

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
            query = """
                MATCH (c1:Concept)-[r]->(c2:Concept)
                WHERE (c1)-[:APPEARS_IN]->(:Source {document: $ontology})
                   OR (c2)-[:APPEARS_IN]->(:Source {document: $ontology})
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
                    # Convert row to dict and handle JSON fields
                    entry = dict(row)

                    # Parse JSONB fields
                    if entry.get('synonyms'):
                        try:
                            entry['synonyms'] = json.loads(entry['synonyms']) if isinstance(entry['synonyms'], str) else entry['synonyms']
                        except (json.JSONDecodeError, TypeError):
                            entry['synonyms'] = []

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
            **BackupFormat.create_metadata(BackupFormat.FULL_BACKUP),
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
            **BackupFormat.create_metadata(BackupFormat.ONTOLOGY_BACKUP, ontology),
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
                     progress_callback: Optional[callable] = None) -> Dict[str, int]:
        """
        Import backup data into database

        Args:
            client: AGEClient instance
            backup_data: Parsed backup JSON
            overwrite_existing: If True, update existing nodes; if False, skip duplicates
            progress_callback: Optional callback(stage, current, total, percent) for progress updates

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

                        # Convert JSON fields back to JSONB strings
                        synonyms_json = json.dumps(entry.get('synonyms')) if entry.get('synonyms') else None
                        embedding_json = json.dumps(entry.get('embedding')) if entry.get('embedding') else None

                        # Insert or update vocabulary entry
                        cur.execute("""
                            INSERT INTO kg_api.relationship_vocabulary
                                (relationship_type, description, category, added_by, added_at,
                                 usage_count, is_active, is_builtin, synonyms, deprecation_reason,
                                 embedding_model, embedding_generated_at, embedding)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s, %s::jsonb)
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
                            synonyms_json,
                            entry.get('deprecation_reason'),
                            entry.get('embedding_model'),
                            entry.get('embedding_generated_at'),
                            embedding_json
                        ))
                        stats["vocabulary_imported"] += 1

                conn.commit()
            finally:
                client.pool.putconn(conn)

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
            merge_query = """
                MERGE (s:Source {source_id: $source_id})
                SET s.document = $document,
                    s.file_path = $file_path,
                    s.paragraph = $paragraph,
                    s.full_text = $full_text
            """

            client._execute_cypher(merge_query, params=source)
            stats["sources_created"] += 1

        # Final callback for sources stage
        if progress_callback and total_sources > 0:
            progress_callback("sources", total_sources, total_sources, 100.0)

        # Import instances
        Console.info("Importing instances...")
        total_instances = len(data["instances"])
        for i, instance in enumerate(data["instances"]):
            current = i + 1
            Console.progress(current, total_instances, "Instances")

            # Call progress callback every 10 items
            if progress_callback and current % 10 == 0:
                percent = (current / total_instances) * 100
                progress_callback("instances", current, total_instances, percent)

            # AGE limitation: Can't use SET with WITH/MATCH joins
            # Split into two queries: 1) create instance, 2) create relationships

            # Query 1: Create/update instance node
            instance_query = """
                MERGE (i:Instance {instance_id: $instance_id})
                SET i.quote = $quote
            """
            client._execute_cypher(instance_query, params={
                "instance_id": instance["instance_id"],
                "quote": instance["quote"]
            })

            # Query 2: Create relationships
            rel_query = """
                MATCH (i:Instance {instance_id: $instance_id})
                MATCH (c:Concept {concept_id: $concept_id})
                MATCH (s:Source {source_id: $source_id})
                MERGE (c)-[:EVIDENCED_BY]->(i)
                MERGE (i)-[:FROM_SOURCE]->(s)
                MERGE (c)-[:APPEARS_IN]->(s)
            """
            client._execute_cypher(rel_query, params=instance)
            stats["instances_created"] += 1

        # Final callback for instances stage
        if progress_callback and total_instances > 0:
            progress_callback("instances", total_instances, total_instances, 100.0)

        # Import concept-concept relationships
        Console.info("Importing relationships...")
        total_relationships = len(data["relationships"])
        for i, rel in enumerate(data["relationships"]):
            current = i + 1
            Console.progress(current, total_relationships, "Relationships")

            # Call progress callback every 10 items
            if progress_callback and current % 10 == 0:
                percent = (current / total_relationships) * 100
                progress_callback("relationships", current, total_relationships, percent)

            # Dynamic relationship type (IMPLIES, SUPPORTS, etc.)
            # Use OPTIONAL MATCH to handle missing nodes gracefully
            query = f"""
                OPTIONAL MATCH (c1:Concept {{concept_id: $from_id}})
                OPTIONAL MATCH (c2:Concept {{concept_id: $to_id}})
                WITH c1, c2
                WHERE c1 IS NOT NULL AND c2 IS NOT NULL
                MERGE (c1)-[r:{rel['type']}]->(c2)
                SET r = $properties
                RETURN count(r) as created
            """

            result = client._execute_cypher(query, params={
                "from_id": rel["from"],
                "to_id": rel["to"],
                "properties": rel["properties"]
            }, fetch_one=True)

            if result and int(str(result.get("created", 0))) > 0:
                stats["relationships_created"] += 1

        # Final callback for relationships stage
        if progress_callback and total_relationships > 0:
            progress_callback("relationships", total_relationships, total_relationships, 100.0)

        return stats
