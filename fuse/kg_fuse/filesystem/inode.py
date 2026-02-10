"""
InodeMixin — Inode table management and attribute resolution.

Handles getattr, inode allocation/recycling, all _get_or_create_* helpers,
cache invalidation, and the _sanitize_filename utility.
"""

import errno
import logging
import os
import stat
import time
from typing import Optional

import pyfuse3

from ..models import InodeEntry

log = logging.getLogger(__name__)


class InodeMixin:
    """Inode table management and attribute resolution."""

    async def getattr(self, inode: int, ctx: pyfuse3.RequestContext) -> pyfuse3.EntryAttributes:
        """Get file/directory attributes."""
        if inode not in self._inodes:
            raise pyfuse3.FUSEError(errno.ENOENT)

        entry = self._inodes[inode]
        is_dir = self._is_dir_type(entry.entry_type)
        size = entry.size

        # Symlinks need special handling
        if entry.entry_type == "symlink":
            attr = pyfuse3.EntryAttributes()
            attr.st_ino = inode
            attr.st_mode = stat.S_IFLNK | 0o777
            attr.st_nlink = 1
            attr.st_size = len(entry.symlink_target.encode("utf-8")) if entry.symlink_target else 0
            attr.st_atime_ns = int(time.time() * 1e9)
            attr.st_mtime_ns = int(time.time() * 1e9)
            attr.st_ctime_ns = int(time.time() * 1e9)
            attr.st_uid = os.getuid()
            attr.st_gid = os.getgid()
            return attr

        # Writable directories: root (global queries), ontology_root (create ontologies),
        # ontology (scoped queries), ingest_dir (file drop box), query (nested)
        # documents_dir: writable only if document deletion is enabled (so rm can call unlink)
        writable = entry.entry_type in ("root", "ontology_root", "ontology", "ingest_dir", "query")
        if entry.entry_type in ("documents_dir", "document", "image_document") and self.write_protect.allow_document_delete:
            writable = True

        # Meta files need special handling for size and permissions
        if entry.entry_type == "meta_file":
            content = self._render_meta_file(entry)
            size = len(content.encode("utf-8"))
            # query.toml is read-only, others are read-write
            if entry.meta_key == "query.toml":
                return self._make_attr(inode, is_dir=False, size=size, writable=False)
            else:
                # Writable meta file - use special mode
                attr = pyfuse3.EntryAttributes()
                attr.st_ino = inode
                attr.st_mode = stat.S_IFREG | 0o644  # Read-write for owner
                attr.st_nlink = 1
                attr.st_size = size
                attr.st_atime_ns = int(time.time() * 1e9)
                attr.st_mtime_ns = int(time.time() * 1e9)
                attr.st_ctime_ns = int(time.time() * 1e9)
                attr.st_uid = os.getuid()
                attr.st_gid = os.getgid()
                return attr

        # Ingestion files are writable temporary files
        if entry.entry_type == "ingestion_file":
            attr = pyfuse3.EntryAttributes()
            attr.st_ino = inode
            attr.st_mode = stat.S_IFREG | 0o644  # Read-write for owner
            attr.st_nlink = 1
            attr.st_size = entry.size
            attr.st_atime_ns = int(time.time() * 1e9)
            attr.st_mtime_ns = int(time.time() * 1e9)
            attr.st_ctime_ns = int(time.time() * 1e9)
            attr.st_uid = os.getuid()
            attr.st_gid = os.getgid()
            return attr

        return self._make_attr(inode, is_dir=is_dir, size=size, writable=writable)

    def _allocate_inode(self) -> int:
        """Allocate a new inode, reusing freed ones when available."""
        if self._free_inodes:
            return self._free_inodes.pop()
        inode = self._next_inode
        self._next_inode += 1
        return inode

    def _free_inode(self, inode: int) -> None:
        """Return an inode to the free list for reuse."""
        if inode >= 100:  # Don't recycle reserved inodes
            self._free_inodes.append(inode)

    def _invalidate_cache(self, inode: int):
        """Invalidate cache for an inode."""
        self._cache.invalidate_dir(inode)
        self._cache.invalidate_content(inode)

    def _invalidate_query_cache(self, ontology: Optional[str], query_path: str):
        """Invalidate cache for a query directory when its parameters change."""
        # Find the query inode and invalidate its cache
        for inode, entry in self._inodes.items():
            if (entry.entry_type == "query" and
                entry.ontology == ontology and
                entry.query_path == query_path):
                self._invalidate_cache(inode)
                break

    def _sanitize_filename(self, name: str) -> str:
        """Convert concept name to safe filename."""
        # Replace problematic characters
        safe = name.replace("/", "-").replace("\\", "-").replace(":", "-")
        safe = safe.replace("<", "").replace(">", "").replace('"', "")
        safe = safe.replace("|", "-").replace("?", "").replace("*", "")
        # Limit length
        if len(safe) > 100:
            safe = safe[:100]
        return safe or "unnamed"

    # ── Inode creation helpers ─────────────────────────────────────────

    def _get_or_create_info_inode(self, name: str, parent_inode: int, ontology: str) -> int:
        """Get or create a virtual info dotfile inode (.ontology, .documents, .ingest)."""
        for inode, entry in self._inodes.items():
            if entry.parent == parent_inode and entry.name == name:
                return inode
        inode = self._allocate_inode()
        self._inodes[inode] = InodeEntry(
            name=name,
            entry_type="info_file",
            parent=parent_inode,
            ontology=ontology,
            size=0,
        )
        return inode

    def _get_or_create_ontology_inode(self, name: str) -> int:
        """Get or create inode for an ontology directory."""
        for inode, entry in self._inodes.items():
            if entry.entry_type == "ontology" and entry.name == name:
                return inode

        inode = self._allocate_inode()
        self._inodes[inode] = InodeEntry(
            name=name,
            entry_type="ontology",
            parent=self.ONTOLOGY_ROOT_INODE,  # Parent is /ontology/, not root
            ontology=name,
        )
        return inode

    def _get_or_create_documents_dir_inode(self, ontology: str, parent: int) -> int:
        """Get or create inode for the documents/ directory inside an ontology."""
        for inode, entry in self._inodes.items():
            if entry.entry_type == "documents_dir" and entry.ontology == ontology:
                return inode

        inode = self._allocate_inode()
        self._inodes[inode] = InodeEntry(
            name="documents",
            entry_type="documents_dir",
            parent=parent,
            ontology=ontology,
        )
        return inode

    def _get_or_create_ingest_dir_inode(self, ontology: str, parent: int) -> int:
        """Get or create inode for the ingest/ drop box inside an ontology."""
        for inode, entry in self._inodes.items():
            if entry.entry_type == "ingest_dir" and entry.ontology == ontology:
                return inode

        inode = self._allocate_inode()
        self._inodes[inode] = InodeEntry(
            name="ingest",
            entry_type="ingest_dir",
            parent=parent,
            ontology=ontology,
        )
        return inode

    def _find_ingest_dir_inode(self, ontology: str) -> Optional[int]:
        """Find the ingest_dir inode for an ontology, if it exists."""
        for inode, entry in self._inodes.items():
            if entry.entry_type == "ingest_dir" and entry.ontology == ontology:
                return inode
        return None

    def _find_documents_dir_inode(self, ontology: str) -> Optional[int]:
        """Find the documents_dir inode for an ontology, if it exists."""
        for inode, entry in self._inodes.items():
            if entry.entry_type == "documents_dir" and entry.ontology == ontology:
                return inode
        return None

    def _get_or_create_document_inode(self, name: str, parent: int, ontology: str, document_id: str) -> int:
        """Get or create inode for a document file."""
        for inode, entry in self._inodes.items():
            if entry.entry_type == "document" and entry.name == name and entry.parent == parent:
                return inode

        inode = self._allocate_inode()
        self._inodes[inode] = InodeEntry(
            name=name,
            entry_type="document",
            parent=parent,
            ontology=ontology,
            document_id=document_id,
            size=4096,  # Placeholder size
        )
        return inode

    def _get_or_create_job_inode(self, name: str, parent: int, ontology: str, job_id: str) -> int:
        """Get or create inode for a job virtual file."""
        for inode, entry in self._inodes.items():
            if entry.entry_type == "job_file" and entry.job_id == job_id and entry.parent == parent:
                return inode

        inode = self._allocate_inode()
        self._inodes[inode] = InodeEntry(
            name=name,
            entry_type="job_file",
            parent=parent,
            ontology=ontology,
            job_id=job_id,
            size=4096,  # Placeholder size, actual content fetched on read
        )
        return inode

    def _get_or_create_query_inode(self, ontology: str, query_path: str, parent: int) -> int:
        """Get or create inode for a query directory."""
        name = query_path.split("/")[-1]  # Last component is the directory name

        for inode, entry in self._inodes.items():
            if (entry.entry_type == "query" and
                entry.ontology == ontology and
                entry.query_path == query_path):
                return inode

        inode = self._allocate_inode()
        self._inodes[inode] = InodeEntry(
            name=name,
            entry_type="query",
            parent=parent,
            ontology=ontology,
            query_path=query_path,
        )
        return inode

    def _get_or_create_concept_inode(self, name: str, parent: int, ontology: Optional[str], query_path: str, concept_id: str) -> int:
        """Get or create inode for a concept file."""
        for inode, entry in self._inodes.items():
            if entry.entry_type == "concept" and entry.concept_id == concept_id and entry.parent == parent:
                return inode

        inode = self._allocate_inode()
        self._inodes[inode] = InodeEntry(
            name=name,
            entry_type="concept",
            parent=parent,
            ontology=ontology,
            query_path=query_path,
            concept_id=concept_id,
            size=4096,  # Placeholder size
        )
        return inode

    def _get_or_create_meta_dir_inode(self, ontology: Optional[str], query_path: str, parent: int) -> int:
        """Get or create inode for the .meta directory inside a query."""
        for inode, entry in self._inodes.items():
            if (entry.entry_type == "meta_dir" and
                entry.ontology == ontology and
                entry.query_path == query_path):
                return inode

        inode = self._allocate_inode()
        self._inodes[inode] = InodeEntry(
            name=".meta",
            entry_type="meta_dir",
            parent=parent,
            ontology=ontology,
            query_path=query_path,
        )
        return inode

    def _get_or_create_meta_file_inode(self, meta_key: str, ontology: Optional[str], query_path: str, parent: int) -> int:
        """Get or create inode for a virtual file inside .meta."""
        for inode, entry in self._inodes.items():
            if (entry.entry_type == "meta_file" and
                entry.meta_key == meta_key and
                entry.ontology == ontology and
                entry.query_path == query_path):
                return inode

        inode = self._allocate_inode()
        self._inodes[inode] = InodeEntry(
            name=meta_key,
            entry_type="meta_file",
            parent=parent,
            ontology=ontology,
            query_path=query_path,
            meta_key=meta_key,
        )
        return inode

    def _get_or_create_symlink_inode(self, name: str, ontology: str, query_path: str, target: str, parent: int) -> int:
        """Get or create inode for a symlink."""
        for inode, entry in self._inodes.items():
            if (entry.entry_type == "symlink" and
                entry.name == name and
                entry.parent == parent):
                return inode

        inode = self._allocate_inode()
        self._inodes[inode] = InodeEntry(
            name=name,
            entry_type="symlink",
            parent=parent,
            ontology=ontology,
            query_path=query_path,
            symlink_target=target,
        )
        return inode
