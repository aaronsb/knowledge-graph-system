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
    - query: User-created query directory
    - concept: Concept result file
    - symlink: Symlink to ontology (for multi-ontology queries)
    - meta_dir: The .meta/ control plane directory inside a query
    - meta_file: Virtual file inside .meta/ (limit, threshold, exclude, union, query.toml)
    - ingestion_file: Temporary file being written for ingestion
    """
    name: str
    entry_type: str
    parent: Optional[int]
    ontology: Optional[str] = None  # Which ontology this belongs to
    query_path: Optional[str] = None  # For query dirs and meta: path under ontology
    document_id: Optional[str] = None  # For documents
    concept_id: Optional[str] = None  # For concepts
    symlink_target: Optional[str] = None  # For symlinks
    meta_key: Optional[str] = None  # For meta_file: which setting (limit, threshold, etc.)
    job_id: Optional[str] = None  # For job_file: ingestion job ID
    size: int = 0


# Directory entry types
DIR_TYPES = frozenset({"root", "ontology_root", "ontology", "documents_dir", "query", "meta_dir"})


def is_dir_type(entry_type: str) -> bool:
    """Check if entry type is a directory.

    Non-directory types include: document, concept, meta_file, ingestion_file,
    symlink, job_file
    """
    return entry_type in DIR_TYPES
