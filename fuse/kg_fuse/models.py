"""Data models for the FUSE filesystem."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class InodeEntry:
    """Metadata for an inode.

    Entry types:
    - root: Mount root (shows ontology/ + global user queries)
    - ontology_root: The /ontology/ directory (lists ontologies)
    - ontology: Individual ontology directory
    - documents_dir: The documents/ directory inside an ontology
    - document: Source document file
    - image_document: Raw image bytes file (e.g., diagram.png)
    - image_prose: Companion markdown for an image (e.g., diagram.png.md)
    - image_evidence: Image file inside a query's images/ directory
    - query: User-created query directory
    - concept: Concept result file
    - symlink: Symlink to ontology (for multi-ontology queries)
    - meta_dir: The .meta/ control plane directory inside a query
    - meta_file: Virtual file inside .meta/ (limit, threshold, exclude, union, query.toml)
    - images_dir: The images/ directory inside a query (lazy-loaded image evidence)
    - ingestion_file: Temporary file being written for ingestion
    """
    name: str
    entry_type: str
    parent: Optional[int]
    ontology: Optional[str] = None  # Which ontology this belongs to
    query_path: Optional[str] = None  # For query dirs and meta: path under ontology
    document_id: Optional[str] = None  # For documents and image documents
    concept_id: Optional[str] = None  # For concepts
    source_id: Optional[str] = None  # For image_evidence entries (source node ID)
    symlink_target: Optional[str] = None  # For symlinks
    meta_key: Optional[str] = None  # For meta_file: which setting (limit, threshold, etc.)
    job_id: Optional[str] = None  # For job_file: ingestion job ID
    content_type: Optional[str] = None  # "document" or "image" (from API)
    size: int = 0


# Directory entry types
DIR_TYPES = frozenset({"root", "ontology_root", "ontology", "documents_dir", "query", "meta_dir", "images_dir"})


def is_dir_type(entry_type: str) -> bool:
    """Check if entry type is a directory.

    Non-directory types include: document, image_document, image_prose,
    image_evidence, concept, meta_file, ingestion_file, symlink, job_file
    """
    return entry_type in DIR_TYPES
