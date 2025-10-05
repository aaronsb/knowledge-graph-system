#!/usr/bin/env python3
"""
Graph to Mermaid Diagram Generator

Converts Neo4j graph query results into Mermaid diagram syntax.
Can be used standalone or piped to visualization tools like 'mmm'.

Usage:
    # From CLI search
    python cli.py search "linear thinking" --format json | python graph_to_mermaid.py

    # From concept details
    python cli.py details concept_005 --format json | python graph_to_mermaid.py

    # Pipe to mmm for rendering
    python graph_to_mermaid.py --concept concept_005 | mmm
"""

import sys
import json
import argparse
from typing import Dict, List, Any, Set, Tuple
from ingest.neo4j_client import Neo4jClient


def sanitize_id(text: str) -> str:
    """Sanitize text for use as Mermaid node ID."""
    # Remove special characters, replace spaces with underscores
    return text.replace(" ", "_").replace("-", "_").replace("'", "").replace('"', '')


def sanitize_label(text: str, max_length: int = 40) -> str:
    """Sanitize text for display in Mermaid node label."""
    # Escape special characters and truncate if needed
    text = text.replace('"', "'").replace('\n', ' ')
    if len(text) > max_length:
        text = text[:max_length-3] + "..."
    return text


def get_concept_graph(neo4j_client: Neo4jClient, concept_id: str, depth: int = 2) -> Dict[str, Any]:
    """
    Fetch a concept and its related concepts from Neo4j.

    Args:
        neo4j_client: Neo4j client instance
        concept_id: Starting concept ID
        depth: How many hops to traverse (default 2)

    Returns:
        Dict with nodes and relationships
    """
    # Build query with depth literal (Cypher doesn't allow parameters for relationship depth)
    query = f"""
    MATCH path = (start:Concept {{concept_id: $concept_id}})-[r*1..{depth}]-(related:Concept)
    WITH start, related, relationships(path) as rels
    RETURN DISTINCT
        start.concept_id as start_id,
        start.label as start_label,
        related.concept_id as related_id,
        related.label as related_label,
        [rel in rels | {{type: type(rel), from: startNode(rel).concept_id, to: endNode(rel).concept_id}}] as path_rels
    """

    nodes = {}
    relationships = []

    with neo4j_client.driver.session() as session:
        result = session.run(query, concept_id=concept_id, depth=depth)

        for record in result:
            # Add start node
            nodes[record["start_id"]] = record["start_label"]
            # Add related node
            nodes[record["related_id"]] = record["related_label"]

            # Add relationships from path
            for rel in record["path_rels"]:
                relationships.append({
                    "from": rel["from"],
                    "to": rel["to"],
                    "type": rel["type"]
                })

    return {
        "nodes": [{"id": k, "label": v} for k, v in nodes.items()],
        "relationships": relationships
    }


def get_search_results_graph(neo4j_client: Neo4jClient, concept_ids: List[str]) -> Dict[str, Any]:
    """
    Fetch multiple concepts and their interconnections.

    Args:
        neo4j_client: Neo4j client instance
        concept_ids: List of concept IDs to include

    Returns:
        Dict with nodes and relationships
    """
    query = """
    MATCH (c:Concept)
    WHERE c.concept_id IN $concept_ids
    OPTIONAL MATCH (c)-[r]-(related:Concept)
    WHERE related.concept_id IN $concept_ids
    RETURN DISTINCT
        c.concept_id as id,
        c.label as label,
        type(r) as rel_type,
        startNode(r).concept_id as from_id,
        endNode(r).concept_id as to_id
    """

    nodes = {}
    relationships = []

    with neo4j_client.driver.session() as session:
        result = session.run(query, concept_ids=concept_ids)

        for record in result:
            nodes[record["id"]] = record["label"]

            if record["rel_type"]:
                relationships.append({
                    "from": record["from_id"],
                    "to": record["to_id"],
                    "type": record["rel_type"]
                })

    return {
        "nodes": [{"id": k, "label": v} for k, v in nodes.items()],
        "relationships": relationships
    }


def generate_mermaid(graph_data: Dict[str, Any], diagram_type: str = "graph") -> str:
    """
    Generate Mermaid diagram syntax from graph data.

    Args:
        graph_data: Dict with 'nodes' and 'relationships' keys
        diagram_type: 'graph', 'flowchart', or 'mindmap'

    Returns:
        Mermaid diagram as markdown string
    """
    lines = ["```mermaid"]

    if diagram_type == "flowchart":
        lines.append("flowchart TD")
    elif diagram_type == "mindmap":
        lines.append("mindmap")
        lines.append("  root((Knowledge Graph))")
    else:
        lines.append("graph TD")

    # Add nodes
    seen_nodes: Set[str] = set()
    for node in graph_data["nodes"]:
        node_id = sanitize_id(node["id"])
        node_label = sanitize_label(node["label"])

        if diagram_type == "mindmap":
            lines.append(f"    {node_id}[{node_label}]")
        else:
            lines.append(f"    {node_id}[\"{node_label}\"]")

        seen_nodes.add(node_id)

    # Add relationships (skip for mindmap)
    if diagram_type != "mindmap":
        relationship_arrows = {
            "IMPLIES": "-->|implies|",
            "SUPPORTS": "-->|supports|",
            "CONTRADICTS": "-.->|contradicts|",
            "PART_OF": "-->|part of|",
            "APPEARS_IN": "-->|appears in|",
            "EVIDENCED_BY": "-->|evidenced by|",
        }

        seen_relationships: Set[Tuple[str, str, str]] = set()
        for rel in graph_data["relationships"]:
            from_id = sanitize_id(rel["from"])
            to_id = sanitize_id(rel["to"])
            rel_type = rel["type"]

            # Skip if nodes not in graph
            if from_id not in seen_nodes or to_id not in seen_nodes:
                continue

            # Deduplicate
            rel_key = (from_id, to_id, rel_type)
            if rel_key in seen_relationships:
                continue
            seen_relationships.add(rel_key)

            arrow = relationship_arrows.get(rel_type, "-->")
            lines.append(f"    {from_id} {arrow} {to_id}")

    # Add styling
    if diagram_type != "mindmap":
        lines.append("")
        lines.append("    classDef concept fill:#e1f5fe,stroke:#01579b,stroke-width:2px")
        lines.append("    class " + ",".join(seen_nodes) + " concept")

    lines.append("```")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Convert graph data to Mermaid diagram syntax"
    )
    parser.add_argument(
        "--concept",
        help="Concept ID to visualize with related concepts"
    )
    parser.add_argument(
        "--concepts",
        nargs="+",
        help="Multiple concept IDs to visualize together"
    )
    parser.add_argument(
        "--depth",
        type=int,
        default=2,
        help="Relationship depth to traverse (default: 2)"
    )
    parser.add_argument(
        "--type",
        choices=["graph", "flowchart", "mindmap"],
        default="graph",
        help="Diagram type (default: graph)"
    )
    parser.add_argument(
        "--input",
        choices=["json", "neo4j"],
        default="neo4j",
        help="Input source: 'json' from stdin or 'neo4j' direct query"
    )

    args = parser.parse_args()

    # Read from stdin if JSON input
    if args.input == "json":
        try:
            data = json.load(sys.stdin)
            # Handle CLI output format
            if "concepts" in data:
                # Search results format
                concept_ids = [c["concept_id"] for c in data["concepts"]]
                neo4j_client = Neo4jClient()
                with neo4j_client:
                    graph_data = get_search_results_graph(neo4j_client, concept_ids)
            else:
                # Assume direct graph format
                graph_data = data
        except json.JSONDecodeError:
            print("Error: Invalid JSON input", file=sys.stderr)
            sys.exit(1)

    # Query Neo4j directly
    else:
        if not args.concept and not args.concepts:
            print("Error: --concept or --concepts required for neo4j input", file=sys.stderr)
            sys.exit(1)

        neo4j_client = Neo4jClient()

        try:
            with neo4j_client:
                if args.concept:
                    graph_data = get_concept_graph(neo4j_client, args.concept, args.depth)
                else:
                    graph_data = get_search_results_graph(neo4j_client, args.concepts)
        except Exception as e:
            print(f"Error querying Neo4j: {e}", file=sys.stderr)
            sys.exit(1)

    # Generate and output Mermaid diagram
    mermaid = generate_mermaid(graph_data, args.type)
    print(mermaid)


if __name__ == "__main__":
    main()
