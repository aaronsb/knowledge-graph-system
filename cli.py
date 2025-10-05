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
    python cli.py list-documents
    python cli.py stats
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

    def search_concepts(self, query: str, limit: int = 10, min_similarity: float = 0.7):
        """Search for concepts using semantic similarity"""
        print(f"{Colors.HEADER}Searching for: {Colors.BOLD}{query}{Colors.ENDC}\n")

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

            results = list(result)

            if not results:
                print(f"{Colors.WARNING}No concepts found matching '{query}'{Colors.ENDC}")
                return

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

    def list_documents(self):
        """List all documents in the graph"""
        print(f"{Colors.HEADER}Documents in Knowledge Graph{Colors.ENDC}\n")

        with self.driver.session() as session:
            result = session.run("""
                MATCH (s:Source)
                WITH DISTINCT s.document as document
                MATCH (src:Source {document: document})
                WITH document, count(src) as paragraph_count
                OPTIONAL MATCH (c:Concept)-[:APPEARS_IN]->(s:Source {document: document})
                WITH document, paragraph_count, count(DISTINCT c) as concept_count
                RETURN document, paragraph_count, concept_count
                ORDER BY document
            """)

            results = list(result)

            if not results:
                print(f"{Colors.WARNING}No documents found{Colors.ENDC}")
                return

            print(f"{Colors.OKGREEN}Found {len(results)} documents:{Colors.ENDC}\n")

            for doc in results:
                print(f"{Colors.BOLD}{doc['document']}{Colors.ENDC}")
                print(f"  Paragraphs: {doc['paragraph_count']}")
                print(f"  Concepts: {doc['concept_count']}")
                print()

    def show_stats(self):
        """Show database statistics"""
        print(f"{Colors.HEADER}Knowledge Graph Statistics{Colors.ENDC}\n")

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

            print(f"{Colors.BOLD}Nodes:{Colors.ENDC}")
            print(f"  Concepts: {Colors.OKGREEN}{stats['Concept']}{Colors.ENDC}")
            print(f"  Sources: {Colors.OKGREEN}{stats['Source']}{Colors.ENDC}")
            print(f"  Instances: {Colors.OKGREEN}{stats['Instance']}{Colors.ENDC}")

            print(f"\n{Colors.BOLD}Relationships:{Colors.ENDC}")
            print(f"  Total: {Colors.OKGREEN}{stats['Relationships']}{Colors.ENDC}")

            rel_type_list = list(rel_types)
            if rel_type_list:
                print(f"\n{Colors.BOLD}Concept Relationships:{Colors.ENDC}")
                for rel in rel_type_list:
                    print(f"  {rel['rel_type']}: {Colors.OKGREEN}{rel['count']}{Colors.ENDC}")

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
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s search "linear thinking" --limit 5
  %(prog)s details linear-scanning-system
  %(prog)s related intelligence-limitation --depth 3
  %(prog)s connect linear-scanning-system genetic-intervention
  %(prog)s list-documents
  %(prog)s stats
        """
    )

    subparsers = parser.add_subparsers(dest='command', help='Command to execute')

    # Search command
    search_parser = subparsers.add_parser('search', help='Search for concepts using semantic similarity')
    search_parser.add_argument('query', help='Search query')
    search_parser.add_argument('--limit', type=int, default=10, help='Maximum number of results (default: 10)')
    search_parser.add_argument('--min-similarity', type=float, default=0.7, help='Minimum similarity score (default: 0.7)')

    # Details command
    details_parser = subparsers.add_parser('details', help='Get detailed information about a concept')
    details_parser.add_argument('concept_id', help='Concept ID')

    # Related command
    related_parser = subparsers.add_parser('related', help='Find related concepts through graph traversal')
    related_parser.add_argument('concept_id', help='Starting concept ID')
    related_parser.add_argument('--types', nargs='+', help='Filter by relationship types')
    related_parser.add_argument('--depth', type=int, default=2, help='Maximum traversal depth (default: 2)')

    # Connect command
    connect_parser = subparsers.add_parser('connect', help='Find shortest path between two concepts')
    connect_parser.add_argument('from_id', help='Starting concept ID')
    connect_parser.add_argument('to_id', help='Target concept ID')
    connect_parser.add_argument('--max-hops', type=int, default=5, help='Maximum number of hops (default: 5)')

    # List documents command
    subparsers.add_parser('list-documents', help='List all documents in the graph')

    # Stats command
    subparsers.add_parser('stats', help='Show database statistics')

    # Visualize command
    viz_parser = subparsers.add_parser('visualize', help='Generate Mermaid diagram for concept(s)')
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
            cli.search_concepts(args.query, args.limit, args.min_similarity)
        elif args.command == 'details':
            cli.get_concept_details(args.concept_id)
        elif args.command == 'related':
            cli.find_related_concepts(args.concept_id, args.types, args.depth)
        elif args.command == 'connect':
            cli.find_connection(args.from_id, args.to_id, args.max_hops)
        elif args.command == 'list-documents':
            cli.list_documents()
        elif args.command == 'stats':
            cli.show_stats()
        elif args.command == 'visualize':
            cli.visualize(args.concept_ids, args.depth, args.type)
    except Exception as e:
        print(f"{Colors.FAIL}Error: {e}{Colors.ENDC}", file=sys.stderr)
        sys.exit(1)
    finally:
        cli.close()


if __name__ == '__main__':
    main()
