"""
Apache AGE operations - Connection management and common database queries

Provides reusable AGE connection handling and common graph operations.
This module mirrors neo4j_ops.py API for compatibility with existing admin tools.
"""

from typing import Optional, Dict, Any, List
from openai import OpenAI

from ..api.lib.age_client import AGEClient
from .config import Config
from .console import Console


class AGEConnection:
    """Apache AGE database connection manager (mirrors Neo4jConnection API)"""

    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        database: Optional[str] = None,
        user: Optional[str] = None,
        password: Optional[str] = None
    ):
        """
        Initialize AGE connection

        Args:
            host: PostgreSQL host (default: from config)
            port: PostgreSQL port (default: from config)
            database: Database name (default: from config)
            user: Database user (default: from config)
            password: Database password (default: from config)
        """
        self.host = host or Config.postgres_host()
        self.port = port or Config.postgres_port()
        self.database = database or Config.postgres_db()
        self.user = user or Config.postgres_user()
        self.password = password or Config.postgres_password()

        self.client: Optional[AGEClient] = None
        self.openai: Optional[OpenAI] = None

    def connect(self):
        """Establish connection to Apache AGE"""
        if not self.client:
            self.client = AGEClient(
                host=self.host,
                port=self.port,
                database=self.database,
                user=self.user,
                password=self.password
            )

        # Initialize OpenAI for embeddings if available
        openai_key = Config.openai_api_key()
        if openai_key and not self.openai:
            self.openai = OpenAI(api_key=openai_key)

    def close(self):
        """Close database connection"""
        if self.client:
            self.client.close()
            self.client = None

    def get_client(self) -> AGEClient:
        """
        Get AGEClient instance (equivalent to session() in Neo4j)

        Returns:
            AGEClient instance for executing queries
        """
        if not self.client:
            self.connect()
        return self.client

    def session(self) -> AGEClient:
        """
        Get database session (compatibility method - returns AGEClient)

        Note: AGEClient doesn't have separate sessions like Neo4j.
        This method returns the AGEClient instance for API compatibility.
        """
        return self.get_client()

    def test_connection(self) -> bool:
        """Test database connectivity"""
        try:
            client = self.get_client()
            result = client._execute_cypher("RETURN 1 as ping", fetch_one=True)
            return result is not None and result.get("ping") == 1
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


class AGEQueries:
    """Common Apache AGE query operations (mirrors Neo4jQueries API)"""

    @staticmethod
    def get_database_stats(client: AGEClient) -> Dict[str, Any]:
        """
        Get database statistics (node/relationship counts)

        Args:
            client: AGEClient instance (replaces Neo4j Session)

        Returns:
            Dictionary with nodes and relationships counts
        """
        stats = {
            "nodes": {},
            "relationships": {}
        }

        # Count nodes by label
        result = client._execute_cypher("""
            MATCH (n)
            RETURN labels(n)[0] as label, count(*) as count
            ORDER BY count DESC
        """)

        for record in result:
            # Parse agtype values
            label_agtype = record.get("label")
            count_agtype = record.get("count")

            # Extract string value (strip quotes if present)
            label = str(label_agtype).strip('"') if label_agtype else "unlabeled"
            count = int(str(count_agtype))

            stats["nodes"][label.lower() + "s"] = count

        # Count relationships by type
        result = client._execute_cypher("""
            MATCH ()-[r]->()
            RETURN type(r) as type, count(*) as count
            ORDER BY count DESC
        """)

        for record in result:
            rel_type = str(record.get("type")).strip('"')
            count = int(str(record.get("count")))
            stats["relationships"][rel_type.lower()] = count

        # Total relationships
        result = client._execute_cypher("MATCH ()-[r]->() RETURN count(r) as total", fetch_one=True)
        if result:
            stats["relationships"]["total"] = int(str(result.get("total")))

        return stats

    @staticmethod
    def get_ontology_list(client: AGEClient) -> List[Dict[str, Any]]:
        """
        List all ontologies with statistics

        Args:
            client: AGEClient instance

        Returns:
            List of ontology dictionaries with statistics
        """
        result = client._execute_cypher("""
            MATCH (s:Source)
            WITH DISTINCT s.document as ontology
            MATCH (src:Source {document: ontology})
            WITH ontology,
                 count(DISTINCT src) as source_count,
                 count(DISTINCT src.file_path) as file_count
            OPTIONAL MATCH (c:Concept)-[:APPEARS]->(s:Source {document: ontology})
            WITH ontology, source_count, file_count, count(DISTINCT c) as concept_count
            OPTIONAL MATCH (i:Instance)-[:FROM_SOURCE]->(s:Source {document: ontology})
            WITH ontology, source_count, file_count, concept_count, count(DISTINCT i) as instance_count
            RETURN ontology, source_count, file_count, concept_count, instance_count
            ORDER BY ontology
        """)

        ontologies = []
        for record in result:
            ontologies.append({
                "ontology": str(record.get("ontology", "")).strip('"'),
                "source_count": int(str(record.get("source_count", 0))),
                "file_count": int(str(record.get("file_count", 0))),
                "concept_count": int(str(record.get("concept_count", 0))),
                "instance_count": int(str(record.get("instance_count", 0)))
            })

        return ontologies

    @staticmethod
    def get_ontology_info(client: AGEClient, ontology_name: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed information about a specific ontology

        Args:
            client: AGEClient instance
            ontology_name: Name of the ontology

        Returns:
            Ontology info dictionary or None if not found
        """
        result = client._execute_cypher("""
            MATCH (s:Source {document: $ontology})
            WITH s.document as ontology, collect(DISTINCT s.file_path) as files
            MATCH (src:Source {document: $ontology})
            WITH ontology, files, count(DISTINCT src) as source_count
            OPTIONAL MATCH (c:Concept)-[:APPEARS]->(s:Source {document: $ontology})
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
        """, params={"ontology": ontology_name}, fetch_one=True)

        if not result:
            return None

        # Parse the info object from agtype
        info_agtype = result.get("info")
        if isinstance(info_agtype, dict):
            return info_agtype

        # If it's still agtype string, parse it
        import json
        try:
            return json.loads(str(info_agtype))
        except (json.JSONDecodeError, ValueError):
            return None

    @staticmethod
    def delete_ontology(client: AGEClient, ontology_name: str) -> Dict[str, int]:
        """
        Delete an ontology and all its data

        Args:
            client: AGEClient instance
            ontology_name: Name of the ontology to delete

        Returns:
            Dictionary with deletion counts
        """
        result = client._execute_cypher("""
            MATCH (s:Source {document: $ontology})
            OPTIONAL MATCH (s)<-[:FROM_SOURCE]-(i:Instance)
            OPTIONAL MATCH (s)<-[:APPEARS]-(c:Concept)
            WHERE NOT EXISTS {
                MATCH (c)-[:APPEARS]->(other:Source)
                WHERE other.document <> $ontology
            }
            WITH s, i, c
            DETACH DELETE s, i, c
            RETURN count(DISTINCT s) as sources_deleted,
                   count(DISTINCT i) as instances_deleted,
                   count(DISTINCT c) as concepts_deleted
        """, params={"ontology": ontology_name}, fetch_one=True)

        if not result:
            return {
                "sources_deleted": 0,
                "instances_deleted": 0,
                "concepts_deleted": 0
            }

        return {
            "sources_deleted": int(str(result.get("sources_deleted", 0))),
            "instances_deleted": int(str(result.get("instances_deleted", 0))),
            "concepts_deleted": int(str(result.get("concepts_deleted", 0)))
        }
