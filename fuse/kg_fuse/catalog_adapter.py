"""Catalog facade adapter (ADR-501).

Pure transforms between the /catalog browse API and the shapes the FUSE inode
layer needs. Kept dependency-free (no pyfuse3, no httpx) so the mapping logic is
unit-testable in isolation — the directory layer wires these into readdir.

The catalog facade is the shared, deterministic projection of the
ontology -> document -> concept hierarchy (canonical :SCOPED_BY / :HAS_SOURCE /
:APPEARS edges). FUSE's stable half (the /ontology/ and documents/ levels) reads
from it so the four clients (CLI, MCP, web, FUSE) share one contract.

Impedance note: FUSE addresses ontologies by NAME (its inode model is
name-keyed), but /catalog/children traverses by node id. So we expose the
ontology name->id map from the root listing; document listing resolves the id
from that map before querying the next level down.
"""

from typing import Optional


def ontology_entries(catalog_root_response: dict) -> list[dict]:
    """Map a root /catalog/children response to ontology descriptors.

    Returns one dict per ontology: {"name", "ontology_id", "child_count"}.
    Nodes missing a name fall back to their id; nodes missing an id are skipped
    (they cannot be addressed).
    """
    out = []
    for node in (catalog_root_response or {}).get("nodes", []):
        oid = node.get("id")
        if not oid:
            continue
        out.append({
            "name": node.get("name") or oid,
            "ontology_id": oid,
            "child_count": node.get("child_count"),
        })
    return out


def ontology_name_to_id(catalog_root_response: dict) -> dict:
    """Build a {name: ontology_id} map from a root /catalog/children response.

    On duplicate names (should not happen — ontology names are unique) the
    first wins, matching how FUSE's name-keyed inodes resolve.
    """
    mapping: dict = {}
    for ont in ontology_entries(catalog_root_response):
        mapping.setdefault(ont["name"], ont["ontology_id"])
    return mapping


def document_entries(catalog_children_response: dict) -> list[dict]:
    """Map a document-level /catalog/children response to document descriptors.

    Returns one dict per document: {"filename", "document_id", "content_type"}.
    content_type defaults to "document" when absent (text). Documents without an
    id are skipped. Mirrors the shape FUSE's _list_documents previously got from
    /documents so the inode-creation path is unchanged.
    """
    out = []
    for node in (catalog_children_response or {}).get("nodes", []):
        did = node.get("id")
        if not did:
            continue
        out.append({
            "filename": node.get("name") or did,
            "document_id": did,
            "content_type": node.get("content_type") or "document",
        })
    return out


def is_image(content_type: Optional[str]) -> bool:
    """True if a document descriptor is an image (drives the raw+`.md` split)."""
    return content_type == "image"
