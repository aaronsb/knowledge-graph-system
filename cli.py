#!/usr/bin/env python3
"""
Knowledge Graph CLI - Standalone tool for querying the graph database

This CLI provides the same functionality as the MCP server, allowing you to:
- Search for concepts using semantic similarity
- Get detailed concept information with evidence
- Find related concepts through graph traversal
- Explore connections between concepts
- Visualize concepts as Mermaid diagrams

Usage:
    python cli.py search "linear thinking"
    python cli.py details linear-scanning-system
    python cli.py related linear-scanning-system --depth 2
    python cli.py connect linear-scanning-system genetic-intervention
    python cli.py ontology list
    python cli.py ontology info "My Ontology"
    python cli.py ontology files "My Ontology"
    python cli.py ontology delete "My Ontology"
    python cli.py database stats
    python cli.py database info
    python cli.py database health
    python cli.py visualize concept_005 --depth 1 | mmm
"""

import argparse
import json
import sys
import os
from typing import List, Dict, Optional
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from neo4j import GraphDatabase
from openai import OpenAI
from dotenv import load_dotenv
from graph_to_mermaid import get_concept_graph, get_search_results_graph, generate_mermaid

# Load environment variables
load_dotenv()

# Configuration
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# ANSI color codes for output
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


class KnowledgeGraphCLI:
    """CLI interface to the knowledge graph"""

    def __init__(self):
        self.driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
        self.openai = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

    def close(self):
        self.driver.close()

    def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for text using OpenAI"""
        if not self.openai:
            raise ValueError("OPENAI_API_KEY not set")

        response = self.openai.embeddings.create(
            model="text-embedding-3-small",
            input=text
        )
        return response.data[0].embedding

    def search_concepts(self, query: str, limit: int = 10, min_similarity: float = 0.7, json_output: bool = False):
        """Search for concepts using semantic similarity"""
        # Generate embedding
        embedding = self.generate_embedding(query)

        # Vector similarity search
        with self.driver.session() as session:
            result = session.run("""
                CALL db.index.vector.queryNodes('concept-embeddings', $limit, $embedding)
                YIELD node, score
                WHERE score > $min_similarity
                WITH node, score
                MATCH (node)-[:APPEARS_IN]->(s:Source)
                WITH node, score, collect(DISTINCT s.document) as documents
                OPTIONAL MATCH (node)-[:EVIDENCED_BY]->(i:Instance)
                WITH node, score, documents, count(DISTINCT i) as evidence_count
                RETURN
                    node.concept_id as concept_id,
                    node.label as label,
                    score,
                    documents,
                    evidence_count
                ORDER BY score DESC
            """, embedding=embedding, limit=limit, min_similarity=min_similarity)

            results = [dict(record) for record in result]

            if json_output:
                print(json.dumps({
                    "query": query,
                    "count": len(results),
                    "results": results
                }, indent=2))
                return

            if not results:
                print(f"{Colors.WARNING}No concepts found matching '{query}'{Colors.ENDC}")
                return

            print(f"{Colors.HEADER}Searching for: {Colors.BOLD}{query}{Colors.ENDC}\n")
            print(f"{Colors.OKGREEN}Found {len(results)} concepts:{Colors.ENDC}\n")

            for i, record in enumerate(results, 1):
                print(f"{Colors.BOLD}{i}. {record['label']}{Colors.ENDC}")
                print(f"   ID: {Colors.OKCYAN}{record['concept_id']}{Colors.ENDC}")
                print(f"   Similarity: {Colors.OKGREEN}{record['score']:.3f}{Colors.ENDC}")
                print(f"   Documents: {', '.join(record['documents'])}")
                print(f"   Evidence: {record['evidence_count']} instances")
                print()

    def get_concept_details(self, concept_id: str):
        """Get detailed information about a concept"""
        print(f"{Colors.HEADER}Concept Details: {Colors.BOLD}{concept_id}{Colors.ENDC}\n")

        with self.driver.session() as session:
            # Get concept info
            concept_result = session.run("""
                MATCH (c:Concept {concept_id: $concept_id})
                OPTIONAL MATCH (c)-[:APPEARS_IN]->(s:Source)
                WITH c, collect(DISTINCT s.document) as documents
                RETURN c, documents
            """, concept_id=concept_id)

            concept_record = concept_result.single()

            if not concept_record:
                print(f"{Colors.FAIL}Concept '{concept_id}' not found{Colors.ENDC}")
                return

            concept = concept_record['c']
            documents = concept_record['documents']

            print(f"{Colors.BOLD}Label:{Colors.ENDC} {concept['label']}")
            print(f"{Colors.BOLD}ID:{Colors.ENDC} {concept['concept_id']}")
            print(f"{Colors.BOLD}Search Terms:{Colors.ENDC} {', '.join(concept.get('search_terms', []))}")
            print(f"{Colors.BOLD}Documents:{Colors.ENDC} {', '.join(documents)}")

            # Get instances (evidence)
            instances_result = session.run("""
                MATCH (c:Concept {concept_id: $concept_id})-[:EVIDENCED_BY]->(i:Instance)
                MATCH (i)-[:FROM_SOURCE]->(s:Source)
                RETURN i.quote as quote, s.document as document, s.paragraph as paragraph, s.source_id as source_id
                ORDER BY s.document, s.paragraph
            """, concept_id=concept_id)

            instances = list(instances_result)

            print(f"\n{Colors.OKGREEN}Evidence ({len(instances)} instances):{Colors.ENDC}")
            for i, inst in enumerate(instances, 1):
                print(f"\n{Colors.BOLD}{i}. {inst['document']} (para {inst['paragraph']}):{Colors.ENDC}")
                print(f"   \"{inst['quote']}\"")

            # Get relationships
            rel_result = session.run("""
                MATCH (c:Concept {concept_id: $concept_id})-[r]->(related:Concept)
                RETURN
                    related.concept_id as to_id,
                    related.label as to_label,
                    type(r) as rel_type,
                    properties(r) as props
            """, concept_id=concept_id)

            relationships = list(rel_result)

            if relationships:
                print(f"\n{Colors.OKBLUE}Relationships ({len(relationships)}):{Colors.ENDC}")
                for rel in relationships:
                    confidence = rel['props'].get('confidence', 'N/A')
                    print(f"  → {Colors.BOLD}{rel['rel_type']}{Colors.ENDC} → {rel['to_label']} ({rel['to_id']}) [confidence: {confidence}]")
            else:
                print(f"\n{Colors.WARNING}No outgoing relationships{Colors.ENDC}")

    def find_related_concepts(self, concept_id: str, relationship_types: List[str] = None, max_depth: int = 2):
        """Find concepts related through graph traversal"""
        print(f"{Colors.HEADER}Related Concepts from: {Colors.BOLD}{concept_id}{Colors.ENDC}")
        print(f"Max depth: {max_depth}\n")

        # Build relationship type filter
        rel_filter = ""
        if relationship_types:
            rel_types = "|".join(relationship_types)
            rel_filter = f":{rel_types}"

        with self.driver.session() as session:
            result = session.run(f"""
                MATCH path = (start:Concept {{concept_id: $concept_id}})-[r{rel_filter}*1..{max_depth}]-(related:Concept)
                WHERE start <> related
                WITH related,
                     min(length(path)) as min_distance,
                     [rel in relationships(path) | type(rel)] as path_types
                RETURN DISTINCT
                    related.concept_id as concept_id,
                    related.label as label,
                    min_distance as distance,
                    path_types
                ORDER BY min_distance, label
            """, concept_id=concept_id)

            results = list(result)

            if not results:
                print(f"{Colors.WARNING}No related concepts found{Colors.ENDC}")
                return

            print(f"{Colors.OKGREEN}Found {len(results)} related concepts:{Colors.ENDC}\n")

            current_distance = None
            for record in results:
                if record['distance'] != current_distance:
                    current_distance = record['distance']
                    print(f"{Colors.BOLD}Distance {current_distance}:{Colors.ENDC}")

                path_str = " → ".join(record['path_types'])
                print(f"  • {record['label']} ({Colors.OKCYAN}{record['concept_id']}{Colors.ENDC})")
                print(f"    Path: {path_str}")

    def find_connection(self, from_id: str, to_id: str, max_hops: int = 5):
        """Find shortest paths between two concepts"""
        print(f"{Colors.HEADER}Finding connection:{Colors.ENDC}")
        print(f"  From: {Colors.BOLD}{from_id}{Colors.ENDC}")
        print(f"  To: {Colors.BOLD}{to_id}{Colors.ENDC}")
        print(f"  Max hops: {max_hops}\n")

        with self.driver.session() as session:
            result = session.run("""
                MATCH path = shortestPath(
                    (from:Concept {concept_id: $from_id})-[*..%d]-(to:Concept {concept_id: $to_id})
                )
                WITH path, [rel in relationships(path) | type(rel)] as rel_types
                RETURN
                    [node in nodes(path) | {id: node.concept_id, label: node.label}] as path_nodes,
                    rel_types,
                    length(path) as hops
                LIMIT 5
            """ % max_hops, from_id=from_id, to_id=to_id)

            paths = list(result)

            if not paths:
                print(f"{Colors.WARNING}No connection found within {max_hops} hops{Colors.ENDC}")
                return

            print(f"{Colors.OKGREEN}Found {len(paths)} path(s):{Colors.ENDC}\n")

            for i, path in enumerate(paths, 1):
                print(f"{Colors.BOLD}Path {i} ({path['hops']} hops):{Colors.ENDC}")
                nodes = path['path_nodes']
                rels = path['rel_types']

                for j, node in enumerate(nodes):
                    print(f"  {node['label']} ({Colors.OKCYAN}{node['id']}{Colors.ENDC})")
                    if j < len(rels):
                        print(f"    ↓ {Colors.OKBLUE}{rels[j]}{Colors.ENDC}")
                print()

    def ontology_list(self, json_output: bool = False):
        """List all ontologies in the graph"""
        with self.driver.session() as session:
            result = session.run("""
                MATCH (s:Source)
                WITH DISTINCT s.document as ontology
                MATCH (src:Source {document: ontology})
                WITH ontology,
                     count(DISTINCT src) as source_count,
                     count(DISTINCT src.file_path) as file_count
                OPTIONAL MATCH (c:Concept)-[:APPEARS_IN]->(s:Source {document: ontology})
                WITH ontology, source_count, file_count, count(DISTINCT c) as concept_count
                RETURN ontology, source_count, file_count, concept_count
                ORDER BY ontology
            """)

            results = [dict(record) for record in result]

            if json_output:
                print(json.dumps({
                    "count": len(results),
                    "ontologies": results
                }, indent=2))
                return

            if not results:
                print(f"{Colors.WARNING}No ontologies found{Colors.ENDC}")
                return

            print(f"{Colors.HEADER}Ontologies in Knowledge Graph{Colors.ENDC}\n")
            print(f"{Colors.OKGREEN}Found {len(results)} ontologies:{Colors.ENDC}\n")

            for ont in results:
                print(f"{Colors.BOLD}{ont['ontology']}{Colors.ENDC}")
                print(f"  Files: {ont['file_count']}")
                print(f"  Chunks: {ont['source_count']}")
                print(f"  Concepts: {ont['concept_count']}")
                print()

    def ontology_info(self, ontology_name: str, json_output: bool = False):
        """Get detailed information about a specific ontology"""
        with self.driver.session() as session:
            # Check if ontology exists
            exists = session.run("""
                MATCH (s:Source {document: $ontology})
                RETURN count(s) > 0 as exists
            """, ontology=ontology_name)

            if not exists.single()['exists']:
                if json_output:
                    print(json.dumps({"error": f"Ontology '{ontology_name}' not found"}))
                else:
                    print(f"{Colors.FAIL}Ontology '{ontology_name}' not found{Colors.ENDC}")
                return

            # Get statistics
            stats = session.run("""
                MATCH (s:Source {document: $ontology})
                WITH count(DISTINCT s) as source_count,
                     count(DISTINCT s.file_path) as file_count,
                     collect(DISTINCT s.file_path) as files
                OPTIONAL MATCH (c:Concept)-[:APPEARS_IN]->(src:Source {document: $ontology})
                WITH source_count, file_count, files, count(DISTINCT c) as concept_count
                OPTIONAL MATCH (i:Instance)-[:FROM_SOURCE]->(src:Source {document: $ontology})
                WITH source_count, file_count, files, concept_count, count(DISTINCT i) as instance_count
                OPTIONAL MATCH (c1:Concept)-[r]->(c2:Concept)
                WHERE (c1)-[:APPEARS_IN]->(:Source {document: $ontology})
                   OR (c2)-[:APPEARS_IN]->(:Source {document: $ontology})
                RETURN source_count, file_count, files, concept_count, instance_count, count(r) as relationship_count
            """, ontology=ontology_name).single()

            data = dict(stats)

            if json_output:
                print(json.dumps({
                    "ontology": ontology_name,
                    "statistics": data
                }, indent=2))
                return

            print(f"{Colors.HEADER}Ontology: {Colors.BOLD}{ontology_name}{Colors.ENDC}\n")
            print(f"{Colors.BOLD}Statistics:{Colors.ENDC}")
            print(f"  Files: {Colors.OKGREEN}{data['file_count']}{Colors.ENDC}")
            print(f"  Chunks: {Colors.OKGREEN}{data['source_count']}{Colors.ENDC}")
            print(f"  Concepts: {Colors.OKGREEN}{data['concept_count']}{Colors.ENDC}")
            print(f"  Evidence: {Colors.OKGREEN}{data['instance_count']}{Colors.ENDC}")
            print(f"  Relationships: {Colors.OKGREEN}{data['relationship_count']}{Colors.ENDC}")

            print(f"\n{Colors.BOLD}Files:{Colors.ENDC}")
            for file_path in data['files']:
                if file_path:
                    print(f"  • {file_path}")

    def ontology_files(self, ontology_name: str, json_output: bool = False):
        """List all files in a specific ontology with their statistics"""
        with self.driver.session() as session:
            result = session.run("""
                MATCH (s:Source {document: $ontology})
                WITH DISTINCT s.file_path as file_path
                WHERE file_path IS NOT NULL
                MATCH (src:Source {document: $ontology, file_path: file_path})
                WITH file_path, count(src) as chunk_count
                OPTIONAL MATCH (c:Concept)-[:APPEARS_IN]->(s:Source {document: $ontology, file_path: file_path})
                WITH file_path, chunk_count, count(DISTINCT c) as concept_count
                RETURN file_path, chunk_count, concept_count
                ORDER BY file_path
            """, ontology=ontology_name)

            results = [dict(record) for record in result]

            if json_output:
                print(json.dumps({
                    "ontology": ontology_name,
                    "count": len(results),
                    "files": results
                }, indent=2))
                return

            if not results:
                print(f"{Colors.WARNING}No files found in ontology '{ontology_name}'{Colors.ENDC}")
                return

            print(f"{Colors.HEADER}Files in: {Colors.BOLD}{ontology_name}{Colors.ENDC}\n")
            print(f"{Colors.OKGREEN}Found {len(results)} files:{Colors.ENDC}\n")

            for file_info in results:
                print(f"{Colors.BOLD}{file_info['file_path']}{Colors.ENDC}")
                print(f"  Chunks: {file_info['chunk_count']}")
                print(f"  Concepts: {file_info['concept_count']}")
                print()

    def ontology_delete(self, ontology_name: str, force: bool = False, json_output: bool = False):
        """Delete an ontology and all its data"""
        with self.driver.session() as session:
            # Check if ontology exists and get stats
            check = session.run("""
                MATCH (s:Source {document: $ontology})
                WITH count(s) as source_count
                OPTIONAL MATCH (c:Concept)-[:APPEARS_IN]->(s:Source {document: $ontology})
                RETURN source_count, count(DISTINCT c) as concept_count
            """, ontology=ontology_name).single()

            if check['source_count'] == 0:
                if json_output:
                    print(json.dumps({"error": f"Ontology '{ontology_name}' not found", "deleted": False}))
                else:
                    print(f"{Colors.FAIL}Ontology '{ontology_name}' not found{Colors.ENDC}")
                return

            if not json_output:
                print(f"{Colors.HEADER}Delete Ontology: {Colors.BOLD}{ontology_name}{Colors.ENDC}\n")
                print(f"{Colors.WARNING}This will delete:{Colors.ENDC}")
                print(f"  • {check['source_count']} source chunks")
                print(f"  • {check['concept_count']} concept associations")
                print(f"  • All related instances and evidence")

            # Confirm deletion
            if not force:
                if json_output:
                    print(json.dumps({"error": "Cannot delete in JSON mode without --yes flag", "deleted": False}))
                    return
                print(f"\n{Colors.FAIL}WARNING: This action cannot be undone!{Colors.ENDC}")
                response = input(f"Type '{ontology_name}' to confirm deletion: ")
                if response != ontology_name:
                    print(f"{Colors.WARNING}Deletion cancelled{Colors.ENDC}")
                    return

            if not json_output:
                print(f"\n{Colors.OKCYAN}Deleting ontology data...{Colors.ENDC}")

            # Delete instances linked to sources in this ontology
            session.run("""
                MATCH (i:Instance)-[:FROM_SOURCE]->(s:Source {document: $ontology})
                DETACH DELETE i
            """, ontology=ontology_name)

            # Delete sources
            result = session.run("""
                MATCH (s:Source {document: $ontology})
                DETACH DELETE s
                RETURN count(s) as deleted_count
            """, ontology=ontology_name)

            deleted = result.single()['deleted_count']

            # Clean up orphaned concepts (concepts with no sources)
            orphaned = session.run("""
                MATCH (c:Concept)
                WHERE NOT (c)-[:APPEARS_IN]->(:Source)
                DETACH DELETE c
                RETURN count(c) as orphaned_count
            """).single()['orphaned_count']

            if json_output:
                print(json.dumps({
                    "ontology": ontology_name,
                    "deleted": True,
                    "sources_deleted": deleted,
                    "orphaned_concepts_deleted": orphaned
                }, indent=2))
            else:
                print(f"{Colors.OKGREEN}✓ Deleted {deleted} sources{Colors.ENDC}")
                if orphaned > 0:
                    print(f"{Colors.OKGREEN}✓ Cleaned up {orphaned} orphaned concepts{Colors.ENDC}")
                print(f"\n{Colors.OKGREEN}Ontology '{ontology_name}' successfully deleted{Colors.ENDC}")

    def database_stats(self, json_output: bool = False):
        """Show database statistics"""
        with self.driver.session() as session:
            # Node counts
            stats = {}
            for label in ['Concept', 'Source', 'Instance']:
                result = session.run(f"MATCH (n:{label}) RETURN count(n) as count")
                stats[label] = result.single()['count']

            # Relationship count
            rel_result = session.run("MATCH ()-[r]->() RETURN count(r) as count")
            stats['Relationships'] = rel_result.single()['count']

            # Concept relationship breakdown
            rel_types = session.run("""
                MATCH (c1:Concept)-[r]->(c2:Concept)
                RETURN type(r) as rel_type, count(*) as count
                ORDER BY count DESC
            """)

            rel_type_list = [dict(record) for record in rel_types]

            if json_output:
                print(json.dumps({
                    "nodes": {
                        "concepts": stats['Concept'],
                        "sources": stats['Source'],
                        "instances": stats['Instance']
                    },
                    "relationships": {
                        "total": stats['Relationships'],
                        "by_type": rel_type_list
                    }
                }, indent=2))
                return

            print(f"{Colors.HEADER}Knowledge Graph Statistics{Colors.ENDC}\n")
            print(f"{Colors.BOLD}Nodes:{Colors.ENDC}")
            print(f"  Concepts: {Colors.OKGREEN}{stats['Concept']}{Colors.ENDC}")
            print(f"  Sources: {Colors.OKGREEN}{stats['Source']}{Colors.ENDC}")
            print(f"  Instances: {Colors.OKGREEN}{stats['Instance']}{Colors.ENDC}")

            print(f"\n{Colors.BOLD}Relationships:{Colors.ENDC}")
            print(f"  Total: {Colors.OKGREEN}{stats['Relationships']}{Colors.ENDC}")

            if rel_type_list:
                print(f"\n{Colors.BOLD}Concept Relationships:{Colors.ENDC}")
                for rel in rel_type_list:
                    print(f"  {rel['rel_type']}: {Colors.OKGREEN}{rel['count']}{Colors.ENDC}")

    def database_info(self, json_output: bool = False):
        """Show database connection information"""
        info = {
            "uri": NEO4J_URI,
            "user": NEO4J_USER,
            "connected": False,
            "version": None
        }

        try:
            with self.driver.session() as session:
                result = session.run("CALL dbms.components() YIELD name, versions, edition")
                component = result.single()
                if component:
                    info["connected"] = True
                    info["version"] = component["versions"][0] if component["versions"] else None
                    info["edition"] = component["edition"]
        except Exception as e:
            info["error"] = str(e)

        if json_output:
            print(json.dumps(info, indent=2))
            return

        print(f"{Colors.HEADER}Database Connection Info{Colors.ENDC}\n")
        print(f"{Colors.BOLD}URI:{Colors.ENDC} {info['uri']}")
        print(f"{Colors.BOLD}User:{Colors.ENDC} {info['user']}")

        if info["connected"]:
            print(f"{Colors.BOLD}Status:{Colors.ENDC} {Colors.OKGREEN}Connected{Colors.ENDC}")
            if info.get("version"):
                print(f"{Colors.BOLD}Version:{Colors.ENDC} {info['version']}")
            if info.get("edition"):
                print(f"{Colors.BOLD}Edition:{Colors.ENDC} {info['edition']}")
        else:
            print(f"{Colors.BOLD}Status:{Colors.ENDC} {Colors.FAIL}Disconnected{Colors.ENDC}")
            if info.get("error"):
                print(f"{Colors.FAIL}Error:{Colors.ENDC} {info['error']}")

    def database_health(self, json_output: bool = False):
        """Check database health and connectivity"""
        health = {
            "status": "unknown",
            "responsive": False,
            "checks": {}
        }

        try:
            with self.driver.session() as session:
                # Check basic connectivity
                result = session.run("RETURN 1 as ping")
                if result.single()["ping"] == 1:
                    health["responsive"] = True
                    health["checks"]["connectivity"] = "ok"

                # Check indexes
                indexes = session.run("SHOW INDEXES")
                index_count = len(list(indexes))
                health["checks"]["indexes"] = {"count": index_count, "status": "ok" if index_count > 0 else "warning"}

                # Check constraints
                constraints = session.run("SHOW CONSTRAINTS")
                constraint_count = len(list(constraints))
                health["checks"]["constraints"] = {"count": constraint_count, "status": "ok" if constraint_count > 0 else "warning"}

                # Overall status
                if health["responsive"] and index_count > 0:
                    health["status"] = "healthy"
                elif health["responsive"]:
                    health["status"] = "degraded"
                else:
                    health["status"] = "unhealthy"

        except Exception as e:
            health["status"] = "unhealthy"
            health["error"] = str(e)

        if json_output:
            print(json.dumps(health, indent=2))
            return

        print(f"{Colors.HEADER}Database Health Check{Colors.ENDC}\n")

        status_color = Colors.OKGREEN if health["status"] == "healthy" else Colors.WARNING if health["status"] == "degraded" else Colors.FAIL
        print(f"{Colors.BOLD}Status:{Colors.ENDC} {status_color}{health['status'].upper()}{Colors.ENDC}")

        if health["responsive"]:
            print(f"{Colors.BOLD}Responsive:{Colors.ENDC} {Colors.OKGREEN}Yes{Colors.ENDC}")
        else:
            print(f"{Colors.BOLD}Responsive:{Colors.ENDC} {Colors.FAIL}No{Colors.ENDC}")

        if health.get("checks"):
            print(f"\n{Colors.BOLD}Checks:{Colors.ENDC}")
            for check_name, check_data in health["checks"].items():
                if isinstance(check_data, dict):
                    check_status = check_data.get("status", "unknown")
                    check_color = Colors.OKGREEN if check_status == "ok" else Colors.WARNING
                    print(f"  {check_name}: {check_color}{check_status}{Colors.ENDC}", end="")
                    if check_data.get("count") is not None:
                        print(f" ({check_data['count']})")
                    else:
                        print()
                else:
                    print(f"  {check_name}: {Colors.OKGREEN}{check_data}{Colors.ENDC}")

        if health.get("error"):
            print(f"\n{Colors.FAIL}Error:{Colors.ENDC} {health['error']}")

    def visualize(self, concept_ids: List[str], depth: int = 1, diagram_type: str = 'graph'):
        """Generate Mermaid diagram for concept(s)"""
        from ingest.neo4j_client import Neo4jClient

        # Create Neo4j client for graph queries
        neo4j_client = Neo4jClient()

        try:
            with neo4j_client:
                if len(concept_ids) == 1:
                    graph_data = get_concept_graph(neo4j_client, concept_ids[0], depth)
                else:
                    graph_data = get_search_results_graph(neo4j_client, concept_ids)

                # Generate and output mermaid (suitable for piping to mmm)
                mermaid = generate_mermaid(graph_data, diagram_type)
                print(mermaid)
        finally:
            neo4j_client.close()


def main():
    parser = argparse.ArgumentParser(
        description='Knowledge Graph CLI - Query and explore the graph database',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    # Global flags
    parser.add_argument('--yes', '-y', action='store_true',
                       help='Auto-confirm all prompts (for create/update/delete operations)')
    parser.add_argument('--json', action='store_true',
                       help='Output results as JSON (for tool integration)')

    subparsers = parser.add_subparsers(dest='command', help='Command to execute')

    # Search command
    search_parser = subparsers.add_parser('search',
        help='Search for concepts using semantic similarity',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s "linear thinking"
  %(prog)s "machine learning" --limit 5
  %(prog)s "consciousness" --min-similarity 0.8
  %(prog)s --json "agility" --limit 3
        """)
    search_parser.add_argument('query', help='Search query')
    search_parser.add_argument('--limit', type=int, default=10, help='Maximum number of results (default: 10)')
    search_parser.add_argument('--min-similarity', type=float, default=0.7, help='Minimum similarity score (default: 0.7)')

    # Details command
    details_parser = subparsers.add_parser('details',
        help='Get detailed information about a concept',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s linear-scanning-system
  %(prog)s concept_005
        """)
    details_parser.add_argument('concept_id', help='Concept ID')

    # Related command
    related_parser = subparsers.add_parser('related',
        help='Find related concepts through graph traversal',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s intelligence-limitation
  %(prog)s linear-scanning-system --depth 3
  %(prog)s concept_005 --types SUPPORTS IMPLIES
        """)
    related_parser.add_argument('concept_id', help='Starting concept ID')
    related_parser.add_argument('--types', nargs='+', help='Filter by relationship types')
    related_parser.add_argument('--depth', type=int, default=2, help='Maximum traversal depth (default: 2)')

    # Connect command
    connect_parser = subparsers.add_parser('connect',
        help='Find shortest path between two concepts',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s linear-scanning-system genetic-intervention
  %(prog)s concept_001 concept_010 --max-hops 3
        """)
    connect_parser.add_argument('from_id', help='Starting concept ID')
    connect_parser.add_argument('to_id', help='Target concept ID')
    connect_parser.add_argument('--max-hops', type=int, default=5, help='Maximum number of hops (default: 5)')

    # Ontology command group
    ontology_parser = subparsers.add_parser('ontology',
        help='Manage ontologies (CRUD operations)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s list
  %(prog)s info "My Ontology"
  %(prog)s files "My Ontology"
  %(prog)s delete "My Ontology"
  %(prog)s --yes delete "My Ontology"
  %(prog)s --json list
        """)
    ontology_subparsers = ontology_parser.add_subparsers(dest='ontology_command', help='Ontology operations')

    # ontology list
    ontology_subparsers.add_parser('list',
        help='List all ontologies',
        epilog="Example: %(prog)s")

    # ontology info
    info_parser = ontology_subparsers.add_parser('info',
        help='Get detailed information about an ontology',
        epilog='Example: %(prog)s "My Ontology"')
    info_parser.add_argument('name', help='Ontology name')

    # ontology files
    files_parser = ontology_subparsers.add_parser('files',
        help='List files in an ontology',
        epilog='Example: %(prog)s "My Ontology"')
    files_parser.add_argument('name', help='Ontology name')

    # ontology delete
    delete_parser = ontology_subparsers.add_parser('delete',
        help='Delete an ontology and all its data',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s "Test Ontology"
  %(prog)s --yes "Test Ontology"  # Skip confirmation
        """)
    delete_parser.add_argument('name', help='Ontology name')

    # Database command group
    database_parser = subparsers.add_parser('database',
        help='Database operations and information',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s stats
  %(prog)s info
  %(prog)s health
  %(prog)s --json stats
        """)
    database_subparsers = database_parser.add_subparsers(dest='database_command', help='Database operations')

    # database stats
    database_subparsers.add_parser('stats',
        help='Show database statistics',
        epilog="Example: %(prog)s")

    # database info
    database_subparsers.add_parser('info',
        help='Show database connection information',
        epilog="Example: %(prog)s")

    # database health
    database_subparsers.add_parser('health',
        help='Check database health and connectivity',
        epilog="Example: %(prog)s")

    # Visualize command
    viz_parser = subparsers.add_parser('visualize',
        help='Generate Mermaid diagram for concept(s)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s concept_005
  %(prog)s concept_005 --depth 2
  %(prog)s concept_001 concept_002 concept_003
  %(prog)s concept_005 --type flowchart | mmm
        """)
    viz_parser.add_argument('concept_ids', nargs='+', help='One or more concept IDs to visualize')
    viz_parser.add_argument('--depth', type=int, default=1, help='Relationship depth (default: 1)')
    viz_parser.add_argument('--type', choices=['graph', 'flowchart'], default='graph',
                           help='Diagram type (default: graph)')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Initialize CLI
    cli = KnowledgeGraphCLI()

    try:
        if args.command == 'search':
            cli.search_concepts(args.query, args.limit, args.min_similarity, json_output=args.json)
        elif args.command == 'details':
            cli.get_concept_details(args.concept_id)
        elif args.command == 'related':
            cli.find_related_concepts(args.concept_id, args.types, args.depth)
        elif args.command == 'connect':
            cli.find_connection(args.from_id, args.to_id, args.max_hops)
        elif args.command == 'ontology':
            if not args.ontology_command:
                parser.error("ontology command requires a subcommand (list, info, files, delete)")
            if args.ontology_command == 'list':
                cli.ontology_list(json_output=args.json)
            elif args.ontology_command == 'info':
                cli.ontology_info(args.name, json_output=args.json)
            elif args.ontology_command == 'files':
                cli.ontology_files(args.name, json_output=args.json)
            elif args.ontology_command == 'delete':
                cli.ontology_delete(args.name, force=args.yes, json_output=args.json)
        elif args.command == 'database':
            if not args.database_command:
                parser.error("database command requires a subcommand (stats, info, health)")
            if args.database_command == 'stats':
                cli.database_stats(json_output=args.json)
            elif args.database_command == 'info':
                cli.database_info(json_output=args.json)
            elif args.database_command == 'health':
                cli.database_health(json_output=args.json)
        elif args.command == 'visualize':
            cli.visualize(args.concept_ids, args.depth, args.type)
    except Exception as e:
        print(f"{Colors.FAIL}Error: {e}{Colors.ENDC}", file=sys.stderr)
        sys.exit(1)
    finally:
        cli.close()


if __name__ == '__main__':
    main()
