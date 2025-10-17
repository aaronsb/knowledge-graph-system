"""
GEXF (Graph Exchange XML Format) Exporter

Converts knowledge graph data to Gephi-compatible GEXF format for visualization.

## What is GEXF?

GEXF is an XML-based file format for describing complex network structures, their
associated data, and dynamics. It's the native format for Gephi, a popular open-source
graph visualization and analysis tool.

**Official Specification:**
- GEXF 1.3 Primer: https://gexf.net/1.3/primer.html
- GEXF Schema: https://gexf.net/schema.html
- Gephi Documentation: https://gephi.org/users/supported-graph-formats/gexf-format/

## Format Features

Our GEXF export includes:

**Nodes (Concepts):**
- `id`: concept_id
- `label`: concept label
- Attributes:
  - `ontology`: which ontology the concept belongs to
  - `search_terms`: comma-separated alternative terms
  - `instance_count`: number of evidence instances
- Visual properties:
  - `color`: RGB color based on ontology (consistent hashing)
  - `size`: logarithmic scale based on instance count (10-50)

**Edges (Relationships):**
- `source`: from_concept_id
- `target`: to_concept_id
- `label`: relationship_type (IMPLIES, SUPPORTS, etc.)
- `type`: directed (all relationships are directed)
- Attributes:
  - `category`: relationship category (logical, evidential, structural)
  - `confidence`: confidence score (0.0-1.0)
- Visual properties:
  - `color`: RGB color based on relationship type
  - `thickness`: edge thickness based on confidence (1.0-3.0)

## XML Structure

```xml
<?xml version="1.0" encoding="UTF-8"?>
<gexf xmlns="http://gexf.net/1.3" version="1.3">
  <meta lastmodifieddate="2025-10-16">
    <creator>Knowledge Graph System</creator>
    <description>Knowledge graph export - ontology (N concepts, M relationships)</description>
  </meta>
  <graph defaultedgetype="directed" mode="static">
    <attributes class="node">
      <attribute id="0" title="ontology" type="string"/>
      <attribute id="1" title="search_terms" type="string"/>
      <attribute id="2" title="instance_count" type="integer"/>
    </attributes>
    <attributes class="edge">
      <attribute id="0" title="category" type="string"/>
      <attribute id="1" title="confidence" type="float"/>
    </attributes>
    <nodes>
      <node id="concept_123" label="Machine Learning">
        <attvalues>
          <attvalue for="0" value="AI Research"/>
          <attvalue for="1" value="ML, statistical learning"/>
          <attvalue for="2" value="42"/>
        </attvalues>
        <viz:color r="59" g="130" b="246"/>
        <viz:size value="25.3"/>
      </node>
    </nodes>
    <edges>
      <edge id="0" source="concept_123" target="concept_456" label="IMPLIES">
        <attvalues>
          <attvalue for="0" value="logical"/>
          <attvalue for="1" value="0.89"/>
        </attvalues>
        <viz:color r="59" g="130" b="246"/>
        <viz:thickness value="2.67"/>
      </edge>
    </edges>
  </graph>
</gexf>
```

## Usage with Gephi

1. Export graph: `kg admin backup --ontology="My Ontology" --format=gexf`
2. Open Gephi
3. File → Open → Select .gexf file
4. Gephi will auto-detect node/edge attributes and visual properties
5. Use Layout algorithms (Force Atlas 2, Fruchterman Reingold, etc.)
6. Apply built-in statistics (PageRank, Betweenness Centrality, etc.)
7. Export visualizations or run analysis

## Limitations

- **No embeddings**: GEXF doesn't include vector embeddings (use JSON for full backup)
- **No sources**: Evidence sources and instances are not included
- **Static only**: Our export uses static mode (no temporal data yet)
- **One-way**: GEXF export is for visualization only, NOT restorable to database

## Color Schemes

**Node Colors (by Ontology):**
- Consistent MD5 hash-based RGB colors
- Same ontology = same color across exports

**Edge Colors (by Relationship Type):**
- IMPLIES: Blue (rgb(59,130,246)) - logical implication
- SUPPORTS: Green (rgb(34,197,94)) - supporting evidence
- CONTRADICTS: Red (rgb(239,68,68)) - contradiction
- PART_OF: Purple (rgb(168,85,247)) - hierarchical
- RELATED_TO: Gray (rgb(156,163,175)) - general relation
- EVIDENCED_BY: Yellow (rgb(251,191,36)) - evidence
- APPEARS_IN: Teal (rgb(20,184,166)) - source reference
- Unknown: Gray (rgb(100,100,100))

## References

- GEXF Specification: https://gexf.net/
- Gephi: https://gephi.org/
- NetworkX GEXF Support: https://networkx.org/documentation/stable/reference/readwrite/gexf.html
"""

import xml.etree.ElementTree as ET
from xml.dom import minidom
from datetime import datetime
from typing import Dict, Any, List
import hashlib


def _prettify_xml(elem: ET.Element) -> str:
    """
    Return pretty-printed XML string

    Args:
        elem: XML element tree

    Returns:
        Formatted XML string with indentation
    """
    rough_string = ET.tostring(elem, encoding='unicode')
    reparsed = minidom.parseString(rough_string)
    return reparsed.toprettyxml(indent="  ")


def _sanitize_xml(text: str) -> str:
    """
    Sanitize text for XML output

    Args:
        text: Raw text

    Returns:
        XML-safe text
    """
    if not text:
        return ""

    # Replace XML special characters
    text = str(text)
    text = text.replace("&", "&amp;")
    text = text.replace("<", "&lt;")
    text = text.replace(">", "&gt;")
    text = text.replace('"', "&quot;")
    text = text.replace("'", "&apos;")

    return text


def _ontology_to_color(ontology: str) -> str:
    """
    Generate consistent color for ontology using hash

    Args:
        ontology: Ontology name

    Returns:
        RGB color string (e.g., "rgb(255,128,64)")
    """
    # Hash ontology name to get consistent color
    hash_val = int(hashlib.md5(ontology.encode()).hexdigest()[:6], 16)

    r = (hash_val >> 16) & 0xFF
    g = (hash_val >> 8) & 0xFF
    b = hash_val & 0xFF

    return f"rgb({r},{g},{b})"


def _relationship_type_to_color(rel_type: str) -> str:
    """
    Map relationship types to semantic colors

    Args:
        rel_type: Relationship type (IMPLIES, SUPPORTS, etc.)

    Returns:
        RGB color string
    """
    colors = {
        "IMPLIES": "rgb(59,130,246)",      # Blue - logical implication
        "SUPPORTS": "rgb(34,197,94)",      # Green - supporting evidence
        "CONTRADICTS": "rgb(239,68,68)",   # Red - contradiction
        "PART_OF": "rgb(168,85,247)",      # Purple - hierarchical
        "RELATED_TO": "rgb(156,163,175)",  # Gray - general relation
        "EVIDENCED_BY": "rgb(251,191,36)", # Yellow - evidence
        "APPEARS_IN": "rgb(20,184,166)",   # Teal - source reference
    }

    return colors.get(rel_type, "rgb(100,100,100)")  # Default gray


def export_to_gexf(backup_data: Dict[str, Any]) -> str:
    """
    Convert backup data to GEXF format

    Args:
        backup_data: Backup dictionary from DataExporter

    Returns:
        GEXF XML string
    """
    # Extract data from nested structure
    # Backup format: {"metadata": {...}, "data": {"concepts": [...], ...}}
    data = backup_data.get("data", {})
    concepts = data.get("concepts", [])
    relationships = data.get("relationships", [])
    instances = data.get("instances", [])

    # Metadata is at top level
    metadata = {
        "export_type": backup_data.get("type", "unknown"),
        "ontology": backup_data.get("ontology", None)
    }

    # Calculate instance counts per concept
    from collections import Counter
    instance_counts = Counter(inst.get("concept_id", "") for inst in instances)

    # Create root element
    gexf = ET.Element("gexf", {
        "xmlns": "http://gexf.net/1.3",
        "version": "1.3",
        "xmlns:viz": "http://gexf.net/1.3/viz",
        "xmlns:xsi": "http://www.w3.org/2001/XMLSchema-instance",
        "xsi:schemaLocation": "http://gexf.net/1.3 http://gexf.net/1.3/gexf.xsd"
    })

    # Add metadata
    meta = ET.SubElement(gexf, "meta")
    meta.set("lastmodifieddate", datetime.now().strftime("%Y-%m-%d"))

    ET.SubElement(meta, "creator").text = "Knowledge Graph System"
    ET.SubElement(meta, "description").text = (
        f"Knowledge graph export - {metadata.get('export_type', 'unknown')} "
        f"({len(concepts)} concepts, {len(relationships)} relationships)"
    )

    # Add keywords
    if metadata.get("ontology"):
        ET.SubElement(meta, "keywords").text = f"ontology:{metadata['ontology']}"

    # Create graph element
    graph = ET.SubElement(gexf, "graph", {
        "defaultedgetype": "directed",
        "mode": "static",
        "name": str(metadata.get("ontology") or "Knowledge Graph")
    })

    # Define node attributes
    node_attrs = ET.SubElement(graph, "attributes", {"class": "node"})

    ET.SubElement(node_attrs, "attribute", {
        "id": "0",
        "title": "ontology",
        "type": "string"
    })

    ET.SubElement(node_attrs, "attribute", {
        "id": "1",
        "title": "search_terms",
        "type": "string"
    })

    ET.SubElement(node_attrs, "attribute", {
        "id": "2",
        "title": "instance_count",
        "type": "integer"
    })

    # Define edge attributes
    edge_attrs = ET.SubElement(graph, "attributes", {"class": "edge"})

    ET.SubElement(edge_attrs, "attribute", {
        "id": "0",
        "title": "category",
        "type": "string"
    })

    ET.SubElement(edge_attrs, "attribute", {
        "id": "1",
        "title": "confidence",
        "type": "float"
    })

    # Add nodes
    nodes_elem = ET.SubElement(graph, "nodes")

    for concept in concepts:
        concept_id = concept.get("concept_id") or ""
        label = concept.get("label") or "Unlabeled"
        ontology = concept.get("ontology") or "Unknown"
        search_terms = concept.get("search_terms") or []

        # Skip concepts without IDs
        if not concept_id:
            continue

        node = ET.SubElement(nodes_elem, "node", {
            "id": str(concept_id),
            "label": _sanitize_xml(label)
        })

        # Add attributes
        attvalues = ET.SubElement(node, "attvalues")

        ET.SubElement(attvalues, "attvalue", {
            "for": "0",
            "value": _sanitize_xml(str(ontology))
        })

        ET.SubElement(attvalues, "attvalue", {
            "for": "1",
            "value": _sanitize_xml(", ".join(str(t) for t in search_terms) if search_terms else "")
        })

        # Instance count from calculated counter
        instance_count = instance_counts.get(concept_id, 0)
        ET.SubElement(attvalues, "attvalue", {
            "for": "2",
            "value": str(instance_count if instance_count is not None else 0)
        })

        # Add visual properties
        viz_elem = ET.SubElement(node, "viz:color")
        color = _ontology_to_color(str(ontology))
        # Parse RGB
        rgb_values = color[4:-1].split(",")  # Extract "255,128,64" from "rgb(255,128,64)"
        viz_elem.set("r", str(rgb_values[0]).strip())
        viz_elem.set("g", str(rgb_values[1]).strip())
        viz_elem.set("b", str(rgb_values[2]).strip())

        # Size based on instance count (log scale)
        import math
        size = max(10, min(50, 10 + math.log(instance_count + 1) * 5))
        ET.SubElement(node, "viz:size", {"value": str(size)})

    # Add edges
    edges_elem = ET.SubElement(graph, "edges")

    for idx, relationship in enumerate(relationships):
        # Backup format uses "from", "to", "type", "properties"
        from_id = relationship.get("from") or ""
        to_id = relationship.get("to") or ""
        rel_type = relationship.get("type") or "RELATED_TO"

        # Skip relationships without proper IDs
        if not from_id or not to_id:
            continue

        # Extract properties
        props = relationship.get("properties") or {}
        category = props.get("category") or "unknown"
        confidence = props.get("confidence")
        if confidence is None:
            confidence = 1.0

        edge = ET.SubElement(edges_elem, "edge", {
            "id": str(idx),
            "source": str(from_id),
            "target": str(to_id),
            "label": str(rel_type),
            "type": "directed"
        })

        # Add attributes
        attvalues = ET.SubElement(edge, "attvalues")

        ET.SubElement(attvalues, "attvalue", {
            "for": "0",
            "value": _sanitize_xml(str(category))
        })

        ET.SubElement(attvalues, "attvalue", {
            "for": "1",
            "value": str(float(confidence))
        })

        # Add edge color based on relationship type
        viz_elem = ET.SubElement(edge, "viz:color")
        color = _relationship_type_to_color(str(rel_type))
        rgb_values = color[4:-1].split(",")
        viz_elem.set("r", str(rgb_values[0]).strip())
        viz_elem.set("g", str(rgb_values[1]).strip())
        viz_elem.set("b", str(rgb_values[2]).strip())

        # Edge thickness based on confidence
        thickness = max(1.0, confidence * 3)
        ET.SubElement(edge, "viz:thickness", {"value": str(thickness)})

    # Convert to pretty XML string
    return _prettify_xml(gexf)


def get_gexf_filename(ontology_name: str = None) -> str:
    """
    Generate GEXF filename

    Args:
        ontology_name: Optional ontology name

    Returns:
        Filename string (e.g., "my_ontology_20251016_143000.gexf")
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    if ontology_name:
        safe_name = ontology_name.lower().replace(" ", "_").replace("/", "_")
        return f"{safe_name}_{timestamp}.gexf"
    else:
        return f"full_backup_{timestamp}.gexf"
