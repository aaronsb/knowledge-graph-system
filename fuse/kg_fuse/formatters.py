"""Formatters for rendering documents and concepts as markdown."""

from typing import Optional

from .config import TagsConfig
from .query_store import Query


def format_document(data: dict, concepts: list = None, tags_config: TagsConfig = None) -> str:
    """Format document data as markdown with optional YAML frontmatter."""
    concepts = concepts or []
    tags_config = tags_config or TagsConfig()
    lines = []

    # Add YAML frontmatter if tags are enabled and we have concepts
    if tags_config.enabled and concepts:
        lines.append("---")
        lines.append(f"document_id: {data.get('document_id', 'unknown')}")
        lines.append(f"ontology: {data.get('ontology', 'unknown')}")

        # Add concept tags
        tags = []
        for concept in concepts:
            name = concept.get("name", "")
            if name:
                # Sanitize name for tag
                tag = name.replace(" ", "-").replace("/", "-")
                tags.append(f"concept/{tag}")
        if tags:
            lines.append("tags:")
            for tag in sorted(set(tags)):
                lines.append(f"  - {tag}")

        lines.append("---")
        lines.append("")

    lines.append(f"# {data.get('filename', 'Document')}\n")
    lines.append(f"**Ontology:** {data.get('ontology', 'unknown')}\n")
    lines.append(f"**Document ID:** {data.get('document_id', 'unknown')}\n")
    lines.append("")

    # Include chunks if present
    chunks = data.get("chunks", [])
    if chunks:
        lines.append("## Content\n")
        for chunk in chunks:
            text = chunk.get("full_text", "")
            lines.append(text)
            lines.append("")

    return "\n".join(lines)


def format_image_prose(data: dict, image_filename: str, tags_config: TagsConfig = None) -> str:
    """Format image companion markdown with frontmatter, relative image link, and prose.

    Args:
        data: Document content response from GET /documents/{id}/content
        image_filename: Original image filename (e.g., "diagram.png")
        tags_config: Tag configuration for optional concept tags
    """
    tags_config = tags_config or TagsConfig()
    content = data.get("content", {})
    lines = []

    # YAML frontmatter
    lines.append("---")
    lines.append(f"document_id: {data.get('document_id', 'unknown')}")
    lines.append("content_type: image")
    ontology = data.get("ontology")
    if ontology:
        lines.append(f"ontology: {ontology}")
    lines.append("---")
    lines.append("")

    # Header
    lines.append(f"# {image_filename}")
    lines.append("")

    # Relative image link (sibling file in same directory)
    lines.append(f"![{image_filename}]({image_filename})")
    lines.append("")

    # Prose description from vision AI
    prose = content.get("prose", "")
    if prose:
        lines.append("## Description")
        lines.append("")
        lines.append(prose)
        lines.append("")

    # Source chunks (for grounding context)
    chunks = data.get("chunks", [])
    if chunks:
        lines.append("## Source Chunks")
        lines.append("")
        for chunk in chunks:
            text = chunk.get("full_text", "")
            if text:
                lines.append(f"> {text[:500]}{'...' if len(text) > 500 else ''}")
                lines.append("")

    return "\n".join(lines)


def format_concept(data: dict, tags_config: TagsConfig = None) -> str:
    """Format concept data as markdown with YAML frontmatter."""
    tags_config = tags_config or TagsConfig()
    lines = []

    # YAML frontmatter
    lines.append("---")
    lines.append(f"id: {data.get('concept_id', 'unknown')}")
    lines.append(f"label: {data.get('label', 'Unknown')}")

    # Aliases from search terms (Obsidian indexes these as alternative names)
    search_terms = data.get("search_terms", [])
    if search_terms:
        lines.append("aliases:")
        for term in search_terms:
            lines.append(f"  - {term}")

    # Grounding
    grounding = data.get("grounding_strength")
    if grounding is not None:
        lines.append(f"grounding: {grounding:.2f}")
        if data.get("grounding_display"):
            lines.append(f"grounding_display: {data.get('grounding_display')}")

    # Diversity
    diversity = data.get("diversity_score")
    if diversity is not None:
        lines.append(f"diversity: {diversity:.2f}")

    # Documents (ontologies this concept appears in)
    documents = data.get("documents", [])
    if documents:
        lines.append("documents:")
        for doc in documents:
            lines.append(f"  - {doc}")

    # Source documents (actual filenames from evidence, fallback to ontology name)
    instances = data.get("instances", [])
    source_docs = sorted(set(
        inst.get("filename") or inst.get("document", "")
        for inst in instances
        if inst.get("filename") or inst.get("document")
    ))
    if source_docs:
        lines.append("sources:")
        for src in source_docs:
            lines.append(f"  - {src}")

    # Relationships in frontmatter
    relationships = data.get("relationships", [])
    if relationships:
        lines.append("relationships:")
        for rel in relationships:
            rel_type = rel.get("rel_type", "RELATED_TO")
            target_label = rel.get("to_label", rel.get("to_id", "unknown"))
            target_id = rel.get("to_id", "unknown")
            lines.append(f"  - type: {rel_type}")
            lines.append(f'    target: "[[{target_label}.concept]]"')
            lines.append(f"    target_id: {target_id}")

    # Tags for tool integration (Obsidian, Logseq, etc.)
    if tags_config.enabled:
        tags = []
        # Add related concepts as tags
        for rel in relationships:
            target_label = rel.get("to_label", "")
            if target_label:
                # Sanitize label for tag: replace spaces with hyphens, remove special chars
                tag = target_label.replace(" ", "-").replace("/", "-")
                tags.append(f"concept/{tag}")
        # Add ontology/document sources as tags
        for doc in documents:
            tag = doc.replace(" ", "-").replace("/", "-")
            tags.append(f"ontology/{tag}")
        if tags:
            lines.append("tags:")
            for tag in sorted(set(tags)):
                lines.append(f"  - {tag}")

    lines.append("---")
    lines.append("")

    # Header
    name = data.get("label", "Unknown Concept")
    lines.append(f"# {name}\n")

    # Description
    description = data.get("description", "")
    if description:
        lines.append(description)
        lines.append("")

    # Evidence (instances)
    if instances:
        lines.append("## Evidence\n")
        for i, inst in enumerate(instances, 1):
            text = inst.get("full_text", inst.get("text", ""))
            para = inst.get("paragraph_number", inst.get("paragraph", "?"))
            # Prefer filename over document (ontology name)
            doc = inst.get("filename") or inst.get("document", "")
            if doc:
                lines.append(f"### Instance {i} from {doc} (para {para})\n")
            else:
                lines.append(f"### Instance {i} (para {para})\n")

            # Image evidence reference
            if inst.get("has_image"):
                img_name = inst.get("filename") or f"{inst.get('source_id', 'image')}.jpg"
                safe_name = img_name.replace("/", "-")
                lines.append(f"![{safe_name}](./images/{safe_name})\n")

            lines.append(f"> {text[:500]}{'...' if len(text) > 500 else ''}\n")
            lines.append("")

    # Relationships as readable list
    if relationships:
        lines.append("## Relationships\n")
        for rel in relationships:
            rel_type = rel.get("rel_type", "RELATED_TO")
            target = rel.get("to_label", rel.get("to_id", "unknown"))
            lines.append(f"- **{rel_type}** → [[{target}.concept]]")
        lines.append("")

    return "\n".join(lines)


def format_job(job_data: dict | None) -> str:
    """Format ingestion job data as a TOML-like readable file.

    Args:
        job_data: Job information from the API including job_id, status,
                  ontology, filename, created_at, and progress info.
                  Can be None if API returned no data.

    Returns:
        Formatted string suitable for display in a virtual file.
    """
    if job_data is None:
        return "# Job Error\n\nerror = \"No job data returned from API\"\n"

    job_id = job_data.get("job_id", "unknown")
    status = job_data.get("status", "unknown")
    ontology = job_data.get("ontology", "unknown")
    filename = job_data.get("filename", "unknown")
    created_at = job_data.get("created_at", "unknown")

    # Progress info (may not always be present)
    progress = job_data.get("progress", {})
    stage = progress.get("stage", status)
    percent = progress.get("percent", 0)
    items_processed = progress.get("items_processed", 0)

    lines = [
        f"# Ingestion Job: {job_id}",
        f"# Status: {status}",
        "",
        "[job]",
        f'job_id = "{job_id}"',
        f'status = "{status}"',
        f'ontology = "{ontology}"',
        f'filename = "{filename}"',
        f'created_at = "{created_at}"',
        "",
        "[progress]",
        f'stage = "{stage}"',
        f"percent = {percent}",
        f"items_processed = {items_processed}",
    ]

    # Include error if present (for failed jobs)
    error = job_data.get("error")
    if error:
        lines.append("")
        lines.append("[error]")
        lines.append(f'message = "{error}"')

    return "\n".join(lines) + "\n"


def render_meta_file(meta_key: str, query: Optional[Query], ontology: Optional[str]) -> str:
    """Render content for a .meta virtual file."""
    if not query:
        return "# Query not found\n"

    if meta_key == "limit":
        return f"# Maximum number of concepts to return. Default is 50.\n{query.limit}\n"

    elif meta_key == "threshold":
        return f"# Minimum similarity score (0.0-1.0). Default is 0.7.\n{query.threshold}\n"

    elif meta_key == "exclude":
        content = "# Terms to exclude from results (one per line, semantic NOT).\n"
        for term in query.exclude:
            content += f"{term}\n"
        return content

    elif meta_key == "union":
        content = "# Additional terms to include (one per line, semantic OR).\n"
        for term in query.union:
            content += f"{term}\n"
        return content

    elif meta_key == "query.toml":
        # Read-only debug view of the full query
        lines = ["# Full query state (read-only)", ""]
        lines.append(f'query_text = "{query.query_text}"')
        lines.append(f"threshold = {query.threshold}")
        lines.append(f"limit = {query.limit}")
        exclude_str = ", ".join(f'"{e}"' for e in query.exclude)
        lines.append(f"exclude = [{exclude_str}]")
        union_str = ", ".join(f'"{u}"' for u in query.union)
        lines.append(f"union = [{union_str}]")
        symlinks_str = ", ".join(f'"{s}"' for s in query.symlinks)
        lines.append(f"symlinks = [{symlinks_str}]")
        lines.append(f'created_at = "{query.created_at}"')
        if ontology:
            lines.append(f'ontology = "{ontology}"')
        else:
            lines.append("ontology = null  # Global query")
        return "\n".join(lines) + "\n"

    return "# Unknown meta file\n"
