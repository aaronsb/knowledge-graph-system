"""
Data serialization - Export and import operations for backup/restore

Handles conversion between Neo4j graph data and portable JSON format,
preserving embeddings (1536-dim vectors), full text, and relationships.
"""

import json
from typing import Dict, Any, List, Optional
from datetime import datetime
from neo4j import Session

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
    def export_concepts(session: Session, ontology: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Export concepts with embeddings

        Args:
            session: Neo4j session
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
            result = session.run(query, ontology=ontology)
        else:
            query = """
                MATCH (c:Concept)
                RETURN c.concept_id as concept_id,
                       c.label as label,
                       c.search_terms as search_terms,
                       c.embedding as embedding
                ORDER BY c.concept_id
            """
            result = session.run(query)

        concepts = []
        for record in result:
            concepts.append({
                "concept_id": record["concept_id"],
                "label": record["label"],
                "search_terms": record["search_terms"],
                "embedding": record["embedding"]  # Full 1536-dim array
            })

        return concepts

    @staticmethod
    def export_sources(session: Session, ontology: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Export source nodes with full text

        Args:
            session: Neo4j session
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
            result = session.run(query, ontology=ontology)
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
            result = session.run(query)

        sources = []
        for record in result:
            sources.append({
                "source_id": record["source_id"],
                "document": record["document"],
                "file_path": record["file_path"],
                "paragraph": record["paragraph"],
                "full_text": record["full_text"]
            })

        return sources

    @staticmethod
    def export_instances(session: Session, ontology: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Export instance nodes (evidence quotes)

        Args:
            session: Neo4j session
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
            result = session.run(query, ontology=ontology)
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
            result = session.run(query)

        instances = []
        for record in result:
            instances.append({
                "instance_id": record["instance_id"],
                "quote": record["quote"],
                "concept_id": record["concept_id"],
                "source_id": record["source_id"]
            })

        return instances

    @staticmethod
    def export_relationships(session: Session, ontology: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Export concept relationships

        Args:
            session: Neo4j session
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
            result = session.run(query, ontology=ontology)
        else:
            query = """
                MATCH (c1:Concept)-[r]->(c2:Concept)
                RETURN c1.concept_id as from_concept,
                       c2.concept_id as to_concept,
                       type(r) as relationship_type,
                       properties(r) as properties
                ORDER BY c1.concept_id, c2.concept_id
            """
            result = session.run(query)

        relationships = []
        for record in result:
            relationships.append({
                "from": record["from_concept"],
                "to": record["to_concept"],
                "type": record["relationship_type"],
                "properties": dict(record["properties"]) if record["properties"] else {}
            })

        return relationships

    @staticmethod
    def export_full_backup(session: Session) -> Dict[str, Any]:
        """
        Export entire database

        Args:
            session: Neo4j session

        Returns:
            Full backup dictionary
        """
        Console.info("Exporting concepts...")
        concepts = DataExporter.export_concepts(session)

        Console.info("Exporting sources...")
        sources = DataExporter.export_sources(session)

        Console.info("Exporting instances...")
        instances = DataExporter.export_instances(session)

        Console.info("Exporting relationships...")
        relationships = DataExporter.export_relationships(session)

        return {
            **BackupFormat.create_metadata(BackupFormat.FULL_BACKUP),
            "statistics": {
                "concepts": len(concepts),
                "sources": len(sources),
                "instances": len(instances),
                "relationships": len(relationships)
            },
            "data": {
                "concepts": concepts,
                "sources": sources,
                "instances": instances,
                "relationships": relationships
            }
        }

    @staticmethod
    def export_ontology_backup(session: Session, ontology: str) -> Dict[str, Any]:
        """
        Export specific ontology

        Args:
            session: Neo4j session
            ontology: Ontology name

        Returns:
            Ontology backup dictionary
        """
        Console.info(f"Exporting ontology: {ontology}")

        Console.info("  - Concepts...")
        concepts = DataExporter.export_concepts(session, ontology)

        Console.info("  - Sources...")
        sources = DataExporter.export_sources(session, ontology)

        Console.info("  - Instances...")
        instances = DataExporter.export_instances(session, ontology)

        Console.info("  - Relationships...")
        relationships = DataExporter.export_relationships(session, ontology)

        return {
            **BackupFormat.create_metadata(BackupFormat.ONTOLOGY_BACKUP, ontology),
            "statistics": {
                "concepts": len(concepts),
                "sources": len(sources),
                "instances": len(instances),
                "relationships": len(relationships)
            },
            "data": {
                "concepts": concepts,
                "sources": sources,
                "instances": instances,
                "relationships": relationships
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
    def import_backup(session: Session, backup_data: Dict[str, Any],
                     overwrite_existing: bool = False) -> Dict[str, int]:
        """
        Import backup data into database

        Args:
            session: Neo4j session
            backup_data: Parsed backup JSON
            overwrite_existing: If True, update existing nodes; if False, skip duplicates

        Returns:
            Dictionary with import statistics
        """
        DataImporter.validate_backup(backup_data)

        data = backup_data["data"]
        stats = {
            "concepts_created": 0,
            "sources_created": 0,
            "instances_created": 0,
            "relationships_created": 0
        }

        # Import concepts
        Console.info("Importing concepts...")
        for i, concept in enumerate(data["concepts"]):
            Console.progress(i + 1, len(data["concepts"]), "Concepts")

            merge_query = """
                MERGE (c:Concept {concept_id: $concept_id})
                ON CREATE SET c.label = $label,
                             c.search_terms = $search_terms,
                             c.embedding = $embedding
            """
            if overwrite_existing:
                merge_query += """
                    ON MATCH SET c.label = $label,
                                c.search_terms = $search_terms,
                                c.embedding = $embedding
                """

            session.run(merge_query, **concept)
            stats["concepts_created"] += 1

        # Import sources
        Console.info("Importing sources...")
        for i, source in enumerate(data["sources"]):
            Console.progress(i + 1, len(data["sources"]), "Sources")

            merge_query = """
                MERGE (s:Source {source_id: $source_id})
                ON CREATE SET s.document = $document,
                             s.file_path = $file_path,
                             s.paragraph = $paragraph,
                             s.full_text = $full_text
            """
            if overwrite_existing:
                merge_query += """
                    ON MATCH SET s.document = $document,
                                s.file_path = $file_path,
                                s.paragraph = $paragraph,
                                s.full_text = $full_text
                """

            session.run(merge_query, **source)
            stats["sources_created"] += 1

        # Import instances
        Console.info("Importing instances...")
        for i, instance in enumerate(data["instances"]):
            Console.progress(i + 1, len(data["instances"]), "Instances")

            merge_query = """
                MERGE (i:Instance {instance_id: $instance_id})
                ON CREATE SET i.quote = $quote
            """
            if overwrite_existing:
                merge_query += " ON MATCH SET i.quote = $quote"

            merge_query += """
                WITH i
                MATCH (c:Concept {concept_id: $concept_id})
                MATCH (s:Source {source_id: $source_id})
                MERGE (c)-[:EVIDENCED_BY]->(i)
                MERGE (i)-[:FROM_SOURCE]->(s)
            """

            session.run(merge_query, **instance)
            stats["instances_created"] += 1

        # Import concept-concept relationships
        Console.info("Importing relationships...")
        for i, rel in enumerate(data["relationships"]):
            Console.progress(i + 1, len(data["relationships"]), "Relationships")

            # Dynamic relationship type (IMPLIES, SUPPORTS, etc.)
            query = f"""
                MATCH (c1:Concept {{concept_id: $from}})
                MATCH (c2:Concept {{concept_id: $to}})
                MERGE (c1)-[r:{rel['type']}]->(c2)
                SET r = $properties
            """

            session.run(query, from_concept=rel["from"], to_concept=rel["to"], properties=rel["properties"])
            stats["relationships_created"] += 1

        return stats
