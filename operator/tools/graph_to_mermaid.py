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
from api.api.lib.age_client import AGEClient


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


def get_concept_graph(neo4j_client: AGEClient, concept_id: str, depth: int = 2) -> Dict[str, Any]:
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
    # Get all nodes within depth, then get all relationships between those nodes
    query = f"""
    // Get starting node and all nodes within depth
    MATCH (start:Concept {{concept_id: $concept_id}})
    OPTIONAL MATCH (start)-[*1..{depth}]-(related:Concept)
    WITH start, collect(DISTINCT related) as related_nodes

    // Combine start node with related nodes
    WITH [start] + related_nodes as all_nodes

    // Get all relationships between these nodes
    UNWIND all_nodes as n1
    MATCH (n1)-[r]-(n2:Concept)
    WHERE n2 IN all_nodes
    RETURN DISTINCT
        n1.concept_id as from_id,
        n1.label as from_label,
        n2.concept_id as to_id,
        n2.label as to_label,
        type(r) as rel_type,
        startNode(r).concept_id as rel_start,
        endNode(r).concept_id as rel_end
    """

    nodes = {}
    relationships = set()  # Use set to deduplicate

    with neo4j_client.driver.session() as session:
        result = session.run(query, concept_id=concept_id)

        for record in result:
            # Add nodes
            nodes[record["from_id"]] = record["from_label"]
            nodes[record["to_id"]] = record["to_label"]

            # Add relationship with proper direction
            rel_tuple = (
                record["rel_start"],
                record["rel_end"],
                record["rel_type"]
            )
            relationships.add(rel_tuple)

    return {
        "nodes": [{"id": k, "label": v} for k, v in nodes.items()],
        "relationships": [
            {"from": r[0], "to": r[1], "type": r[2]}
            for r in relationships
        ]
    }


def get_search_results_graph(neo4j_client: AGEClient, concept_ids: List[str]) -> Dict[str, Any]:
    """
    Fetch multiple concepts and their interconnections.

    Args:
        neo4j_client: Neo4j client instance
        concept_ids: List of concept IDs to include

    Returns:
        Dict with nodes and relationships
    """
    query = """
    // Get specified concepts
    MATCH (c:Concept)
    WHERE c.concept_id IN $concept_ids

    // Get all relationships between these concepts
    WITH collect(c) as all_concepts
    UNWIND all_concepts as n1
    MATCH (n1)-[r]-(n2:Concept)
    WHERE n2 IN all_concepts
    RETURN DISTINCT
        n1.concept_id as n1_id,
        n1.label as n1_label,
        n2.concept_id as n2_id,
        n2.label as n2_label,
        type(r) as rel_type,
        startNode(r).concept_id as rel_start,
        endNode(r).concept_id as rel_end
    """

    nodes = {}
    relationships = set()  # Use set to deduplicate

    with neo4j_client.driver.session() as session:
        result = session.run(query, concept_ids=concept_ids)

        for record in result:
            # Add nodes
            nodes[record["n1_id"]] = record["n1_label"]
            nodes[record["n2_id"]] = record["n2_label"]

            # Add relationship with proper direction
            rel_tuple = (
                record["rel_start"],
                record["rel_end"],
                record["rel_type"]
            )
            relationships.add(rel_tuple)

    return {
        "nodes": [{"id": k, "label": v} for k, v in nodes.items()],
        "relationships": [
            {"from": r[0], "to": r[1], "type": r[2]}
            for r in relationships
        ]
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

    # Add high-contrast styling
    if diagram_type != "mindmap":
        lines.append("")
        lines.append("    %% High contrast styling")
        lines.append("    classDef concept fill:#000000,stroke:#ffffff,stroke-width:3px,color:#ffffff")
        lines.append("    class " + ",".join(seen_nodes) + " concept")
        lines.append("")
        lines.append("    %% Link styling")
        lines.append("    linkStyle default stroke:#ffffff,stroke-width:2px")

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
                neo4j_client = AGEClient()
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

        neo4j_client = AGEClient()

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
