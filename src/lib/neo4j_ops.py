"""
Neo4j operations - Connection management and common database queries

Provides reusable Neo4j connection handling and common graph operations.
"""

from typing import Optional, Dict, Any, List
from neo4j import GraphDatabase, Session, Driver
from openai import OpenAI

from .config import Config
from .console import Console


class Neo4jConnection:
    """Neo4j database connection manager"""

    def __init__(self, uri: Optional[str] = None, user: Optional[str] = None, password: Optional[str] = None):
        """
        Initialize Neo4j connection

        Args:
            uri: Neo4j URI (default: from config)
            user: Neo4j username (default: from config)
            password: Neo4j password (default: from config)
        """
        self.uri = uri or Config.neo4j_uri()
        self.user = user or Config.neo4j_user()
        self.password = password or Config.neo4j_password()

        self.driver: Optional[Driver] = None
        self.openai: Optional[OpenAI] = None

    def connect(self):
        """Establish connection to Neo4j"""
        if not self.driver:
            self.driver = GraphDatabase.driver(self.uri, auth=(self.user, self.password))

        # Initialize OpenAI for embeddings if available
        openai_key = Config.openai_api_key()
        if openai_key and not self.openai:
            self.openai = OpenAI(api_key=openai_key)

    def close(self):
        """Close database connection"""
        if self.driver:
            self.driver.close()
            self.driver = None

    def session(self) -> Session:
        """Get database session"""
        if not self.driver:
            self.connect()
        return self.driver.session()

    def test_connection(self) -> bool:
        """Test database connectivity"""
        try:
            with self.session() as session:
                result = session.run("RETURN 1 as ping")
                return result.single()["ping"] == 1
        except Exception:
            return False

    def generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding for text using OpenAI

        Args:
            text: Text to embed

        Returns:
            List of embedding values (1536 dimensions for text-embedding-3-small)
        """
        if not self.openai:
            openai_key = Config.openai_api_key()
            if not openai_key:
                raise ValueError("OPENAI_API_KEY not set - required for embeddings")
            self.openai = OpenAI(api_key=openai_key)

        embedding_model = Config.openai_embedding_model()
        response = self.openai.embeddings.create(
            model=embedding_model,
            input=text
        )
        return response.data[0].embedding

    def __enter__(self):
        """Context manager entry"""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()


class Neo4jQueries:
    """Common Neo4j query operations"""

    @staticmethod
    def get_database_stats(session: Session) -> Dict[str, Any]:
        """Get database statistics (node/relationship counts)"""
        stats = {
            "nodes": {},
            "relationships": {}
        }

        # Count nodes by label
        result = session.run("""
            MATCH (n)
            RETURN labels(n)[0] as label, count(*) as count
            ORDER BY count DESC
        """)
        for record in result:
            label = record["label"] or "unlabeled"
            stats["nodes"][label.lower() + "s"] = record["count"]

        # Count relationships by type
        result = session.run("""
            MATCH ()-[r]->()
            RETURN type(r) as type, count(*) as count
            ORDER BY count DESC
        """)
        for record in result:
            stats["relationships"][record["type"].lower()] = record["count"]

        # Total relationships
        result = session.run("MATCH ()-[r]->() RETURN count(r) as total")
        stats["relationships"]["total"] = result.single()["total"]

        return stats

    @staticmethod
    def get_ontology_list(session: Session) -> List[Dict[str, Any]]:
        """List all ontologies with statistics"""
        result = session.run("""
            MATCH (s:Source)
            WITH DISTINCT s.document as ontology
            MATCH (src:Source {document: ontology})
            WITH ontology,
                 count(DISTINCT src) as source_count,
                 count(DISTINCT src.file_path) as file_count
            OPTIONAL MATCH (c:Concept)-[:APPEARS_IN]->(s:Source {document: ontology})
            WITH ontology, source_count, file_count, count(DISTINCT c) as concept_count
            OPTIONAL MATCH (i:Instance)-[:FROM_SOURCE]->(s:Source {document: ontology})
            WITH ontology, source_count, file_count, concept_count, count(DISTINCT i) as instance_count
            RETURN ontology, source_count, file_count, concept_count, instance_count
            ORDER BY ontology
        """)
        return [dict(record) for record in result]

    @staticmethod
    def get_ontology_info(session: Session, ontology_name: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about a specific ontology"""
        result = session.run("""
            MATCH (s:Source {document: $ontology})
            WITH s.document as ontology, collect(DISTINCT s.file_path) as files
            MATCH (src:Source {document: $ontology})
            WITH ontology, files, count(DISTINCT src) as source_count
            OPTIONAL MATCH (c:Concept)-[:APPEARS_IN]->(s:Source {document: $ontology})
            WITH ontology, files, source_count, count(DISTINCT c) as concept_count
            OPTIONAL MATCH (i:Instance)-[:FROM_SOURCE]->(s:Source {document: $ontology})
            WITH ontology, files, source_count, concept_count, count(DISTINCT i) as instance_count
            RETURN {
                ontology: ontology,
                files: files,
                statistics: {
                    source_count: source_count,
                    file_count: size(files),
                    concept_count: concept_count,
                    instance_count: instance_count
                }
            } as info
        """, ontology=ontology_name)

        record = result.single()
        return dict(record["info"]) if record else None

    @staticmethod
    def delete_ontology(session: Session, ontology_name: str) -> Dict[str, int]:
        """Delete an ontology and all its data"""
        # This returns counts of deleted nodes/relationships
        result = session.run("""
            MATCH (s:Source {document: $ontology})
            OPTIONAL MATCH (s)<-[:FROM_SOURCE]-(i:Instance)
            OPTIONAL MATCH (s)<-[:APPEARS_IN]-(c:Concept)
            WHERE NOT EXISTS {
                MATCH (c)-[:APPEARS_IN]->(other:Source)
                WHERE other.document <> $ontology
            }
            WITH s, i, c
            DETACH DELETE s, i, c
            RETURN count(DISTINCT s) as sources_deleted,
                   count(DISTINCT i) as instances_deleted,
                   count(DISTINCT c) as concepts_deleted
        """, ontology=ontology_name)

        record = result.single()
        return dict(record) if record else {"sources_deleted": 0, "instances_deleted": 0, "concepts_deleted": 0}
