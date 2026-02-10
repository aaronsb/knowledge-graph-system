"""
Knowledge Graph FUSE Filesystem — mixin composition.

Hierarchy:
- /                              - Mount root (ontology/ + user global queries)
- /ontology/                     - Fixed, system-managed ontology listing
- /ontology/{name}/              - Ontology directories (from graph)
- /ontology/{name}/documents/    - Source documents (read-only)
- /ontology/{name}/documents/{doc}.md  - Text document content
- /ontology/{name}/documents/{img}.png - Image: raw bytes from Garage S3
- /ontology/{name}/documents/{img}.png.md - Image companion: prose + link
- /ontology/{name}/ingest/       - Drop box for ingestion (write-only)
- /ontology/{name}/{query}/      - User query scoped to ontology
- /{user-query}/                 - User global query (all ontologies)
- /{path}/*.concept.md           - Concept search results
- /{path}/images/                - Image evidence from query concepts
- /{query}/.meta/                - Query control plane (virtual)

Query Control Plane (.meta):
- .meta/limit      - Max results (default: 50)
- .meta/threshold  - Min similarity 0.0-1.0 (default: 0.7)
- .meta/exclude    - Terms to exclude (NOT)
- .meta/union      - Terms to broaden (OR)
- .meta/query.toml - Full query state (read-only)

Filtering Model:
- Hierarchy = AND (nesting narrows results)
- Symlinks = OR (add sources)
- .meta/exclude = NOT (removes matches)
- .meta/union = OR (adds matches)
"""

from .base import BaseMixin
from .directory import DirectoryMixin
from .ingestion import (
    IngestionMixin,
    MAX_INGESTION_SIZE,
    WRITE_BACK_DELAY,
    IMAGE_EXTENSIONS,
    _is_image_file,
)
from .inode import InodeMixin
from .read import ReadMixin
from .write import WriteMixin


class KnowledgeGraphFS(
    WriteMixin,        # create, write, release, rename, unlink, mkdir, rmdir, symlink
    ReadMixin,         # open, read, _fetch_content, _render_*, _format_*
    IngestionMixin,    # write-back queue, flush, _ingest_and_notify, _ingest_document
    DirectoryMixin,    # readdir, lookup, _list_*, _execute_search
    InodeMixin,        # getattr, inode allocation, all _get_or_create_* helpers
    BaseMixin,         # __init__, destroy, config, access, statfs (MUST be last)
):
    """Knowledge Graph FUSE Filesystem.

    Composed from domain-specific mixins. BaseMixin must be last in MRO
    so its __init__ runs first and sets up all shared state.
    """
    pass


__all__ = [
    "KnowledgeGraphFS",
    "WRITE_BACK_DELAY",
    "MAX_INGESTION_SIZE",
    "IMAGE_EXTENSIONS",
    "_is_image_file",
]
