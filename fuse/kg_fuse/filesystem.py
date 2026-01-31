"""
Knowledge Graph FUSE Filesystem Operations

Hierarchy:
- /                              - Mount root (ontology/ + user global queries)
- /ontology/                     - Fixed, system-managed ontology listing
- /ontology/{name}/              - Ontology directories (from graph)
- /ontology/{name}/documents/    - Source documents (read-only)
- /ontology/{name}/documents/{doc}.md  - Text document content
- /ontology/{name}/documents/{img}.png - Image: raw bytes from Garage S3
- /ontology/{name}/documents/{img}.png.md - Image companion: prose + link
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

import errno
import logging
import os
import re
import stat
import time
from typing import Optional

import pyfuse3

from .api_client import KnowledgeGraphClient
from .config import TagsConfig, JobsConfig, CacheConfig
from .epoch_cache import EpochCache
from .formatters import format_concept, format_document, format_job, render_meta_file
from .image_handler import ImageHandler
from .job_tracker import JobTracker, TERMINAL_JOB_STATUSES
from .models import InodeEntry, is_dir_type
from .query_store import QueryStore

log = logging.getLogger(__name__)

# Maximum file size for ingestion (50MB)
MAX_INGESTION_SIZE = 50 * 1024 * 1024

# Supported image extensions (matches API's _is_image_file and CLI's isImageFile)
IMAGE_EXTENSIONS = frozenset({'.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp'})


def _is_image_file(filename: str) -> bool:
    """Check if filename has a supported image extension."""
    ext = os.path.splitext(filename)[1].lower()
    return ext in IMAGE_EXTENSIONS


class KnowledgeGraphFS(pyfuse3.Operations):
    """FUSE filesystem backed by Knowledge Graph API."""

    ROOT_INODE = pyfuse3.ROOT_INODE  # 1
    ONTOLOGY_ROOT_INODE = 2  # Fixed inode for /ontology/

    def __init__(self, api_url: str, client_id: str, client_secret: str,
                 tags_config: TagsConfig = None, jobs_config: JobsConfig = None,
                 cache_config: CacheConfig = None):
        super().__init__()
        self.tags_config = tags_config or TagsConfig()
        self.jobs_config = jobs_config or JobsConfig()
        self.cache_config = cache_config or CacheConfig()

        # API client for graph operations
        self._api = KnowledgeGraphClient(api_url, client_id, client_secret)

        # Query store for user-created directories
        self.query_store = QueryStore()

        # Inode management - root and ontology_root are fixed
        self._inodes: dict[int, InodeEntry] = {
            self.ROOT_INODE: InodeEntry(name="", entry_type="root", parent=None),
            self.ONTOLOGY_ROOT_INODE: InodeEntry(
                name="ontology", entry_type="ontology_root", parent=self.ROOT_INODE
            ),
        }
        self._next_inode = 100  # Dynamic inodes start here
        self._free_inodes: list[int] = []  # Recycled inodes for reuse

        # Epoch-gated cache (directory listings + content + background refresh)
        self._cache = EpochCache(self._api, self.cache_config)

        # Write support: pending ontologies and ingestion buffers
        self._pending_ontologies: set[str] = set()  # Ontologies created but no documents yet
        self._write_buffers: dict[int, bytes] = {}  # inode -> content being written
        self._write_info: dict[int, dict] = {}  # inode -> {ontology, filename}

        # Job tracking: lazy polling with automatic cleanup
        self._job_tracker = JobTracker()

        # Image handler: reads, caches, ingests, and manages image inodes
        self._image_handler = ImageHandler(
            api=self._api,
            tags_config=self.tags_config,
            job_tracker=self._job_tracker,
            inodes=self._inodes,
            allocate_inode=self._allocate_inode,
            sanitize_filename=self._sanitize_filename,
        )

    def _make_attr(self, inode: int, is_dir: bool = False, size: int = 0, writable: bool = False) -> pyfuse3.EntryAttributes:
        """Create file attributes."""
        attr = pyfuse3.EntryAttributes()
        attr.st_ino = inode

        if is_dir:
            # Directories: writable if they can contain user-created subdirs
            attr.st_mode = stat.S_IFDIR | (0o755 if writable else 0o555)
        else:
            # Files: read-only (hologram)
            attr.st_mode = stat.S_IFREG | 0o444

        attr.st_nlink = 2 if is_dir else 1
        attr.st_size = size
        attr.st_atime_ns = int(time.time() * 1e9)
        attr.st_mtime_ns = int(time.time() * 1e9)
        attr.st_ctime_ns = int(time.time() * 1e9)
        attr.st_uid = os.getuid()
        attr.st_gid = os.getgid()
        return attr

    def _is_dir_type(self, entry_type: str) -> bool:
        """Check if entry type is a directory."""
        return is_dir_type(entry_type)

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
        # ontology (scoped queries + ingestion), query (nested)
        # Not writable: documents_dir (read-only), meta_dir (fixed structure)
        writable = entry.entry_type in ("root", "ontology_root", "ontology", "query")

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

    async def lookup(self, parent_inode: int, name: bytes, ctx: pyfuse3.RequestContext) -> pyfuse3.EntryAttributes:
        """Look up a directory entry by name."""
        name_str = name.decode("utf-8")
        log.debug(f"lookup: parent={parent_inode}, name={name_str}")

        # Check existing inodes first
        for inode, entry in self._inodes.items():
            if entry.parent == parent_inode and entry.name == name_str:
                return await self.getattr(inode, ctx)

        parent_entry = self._inodes.get(parent_inode)
        if not parent_entry:
            raise pyfuse3.FUSEError(errno.ENOENT)

        # Root level: "ontology" (fixed) + global user queries
        if parent_entry.entry_type == "root":
            if name_str == "ontology":
                return await self.getattr(self.ONTOLOGY_ROOT_INODE, ctx)

            # Check if it's a global user query
            if self.query_store.is_query_dir(None, name_str):
                inode = self._get_or_create_query_inode(None, name_str, parent_inode)
                return await self.getattr(inode, ctx)

        # ontology_root: list actual ontologies
        elif parent_entry.entry_type == "ontology_root":
            entries = await self._list_ontologies()
            for inode, ont_name in entries:
                if ont_name == name_str:
                    return await self.getattr(inode, ctx)

        # Inside ontology: "documents" (fixed) + user queries
        elif parent_entry.entry_type == "ontology":
            ontology = parent_entry.ontology

            if name_str == "documents":
                inode = self._get_or_create_documents_dir_inode(ontology, parent_inode)
                return await self.getattr(inode, ctx)

            # Check if it's a query directory
            if self.query_store.is_query_dir(ontology, name_str):
                inode = self._get_or_create_query_inode(ontology, name_str, parent_inode)
                return await self.getattr(inode, ctx)

        # documents_dir: list actual document files
        elif parent_entry.entry_type == "documents_dir":
            ontology = parent_entry.ontology
            entries = await self._list_documents(parent_inode, ontology)
            for inode, doc_name in entries:
                if doc_name == name_str:
                    return await self.getattr(inode, ctx)

        # Query directory: .meta + images + concepts + nested queries
        elif parent_entry.entry_type == "query":
            ontology = parent_entry.ontology  # Can be None for global queries
            parent_path = parent_entry.query_path

            # Check for .meta directory
            if name_str == ".meta":
                inode = self._get_or_create_meta_dir_inode(ontology, parent_path, parent_inode)
                return await self.getattr(inode, ctx)

            # Check for images directory
            if name_str == "images":
                inode = self._image_handler.get_or_create_images_dir_inode(ontology, parent_path, parent_inode)
                return await self.getattr(inode, ctx)

            nested_path = f"{parent_path}/{name_str}" if parent_path else name_str

            # Check if it's a nested query directory
            if self.query_store.is_query_dir(ontology, nested_path):
                inode = self._get_or_create_query_inode(ontology, nested_path, parent_inode)
                return await self.getattr(inode, ctx)

            # Check if it's a concept file (fetch results if needed)
            entries = await self._list_query_results(parent_inode, ontology, parent_path)
            for inode, file_name in entries:
                if file_name == name_str:
                    return await self.getattr(inode, ctx)

        # images directory: list image evidence files
        elif parent_entry.entry_type == "images_dir":
            entries = await self._image_handler.list_query_images(
                parent_inode, parent_entry.ontology, parent_entry.query_path,
                cache=self._cache
            )
            for inode, file_name in entries:
                if file_name == name_str:
                    return await self.getattr(inode, ctx)

        # .meta directory: list virtual config files
        elif parent_entry.entry_type == "meta_dir":
            ontology = parent_entry.ontology
            query_path = parent_entry.query_path

            if name_str in self.META_FILES:
                inode = self._get_or_create_meta_file_inode(name_str, ontology, query_path, parent_inode)
                return await self.getattr(inode, ctx)

        # Not found
        raise pyfuse3.FUSEError(errno.ENOENT)

    async def opendir(self, inode: int, ctx: pyfuse3.RequestContext) -> int:
        """Open a directory, return file handle."""
        if inode not in self._inodes:
            raise pyfuse3.FUSEError(errno.ENOENT)
        if not self._is_dir_type(self._inodes[inode].entry_type):
            raise pyfuse3.FUSEError(errno.ENOTDIR)

        return inode  # Use inode as file handle

    async def mkdir(self, parent_inode: int, name: bytes, mode: int, ctx: pyfuse3.RequestContext) -> pyfuse3.EntryAttributes:
        """Create a query directory."""
        name_str = name.decode("utf-8")
        log.info(f"mkdir: parent={parent_inode}, name={name_str}")

        parent_entry = self._inodes.get(parent_inode)
        if not parent_entry:
            raise pyfuse3.FUSEError(errno.ENOENT)

        # Determine ontology scope and query path based on parent type
        if parent_entry.entry_type == "root":
            # Global query at root level (searches all ontologies)
            ontology = None
            query_path = name_str
            # Create query in store
            self.query_store.add_query(ontology, query_path)
            # Create inode for the new directory
            inode = self._get_or_create_query_inode(ontology, query_path, parent_inode)

        elif parent_entry.entry_type == "ontology_root":
            # Creating a new ontology - track as pending until files are ingested
            ontology_name = name_str
            self._pending_ontologies.add(ontology_name)
            log.info(f"Created pending ontology: {ontology_name}")
            # Create inode for the new ontology directory
            inode = self._allocate_inode()
            self._inodes[inode] = InodeEntry(
                name=ontology_name,
                entry_type="ontology",
                parent=parent_inode,
                ontology=ontology_name,
            )

        elif parent_entry.entry_type == "ontology":
            # Query scoped to this ontology
            ontology = parent_entry.ontology
            query_path = name_str
            # Create query in store
            self.query_store.add_query(ontology, query_path)
            # Create inode for the new directory
            inode = self._get_or_create_query_inode(ontology, query_path, parent_inode)

        elif parent_entry.entry_type == "query":
            # Nested query (inherits ontology scope from parent)
            ontology = parent_entry.ontology  # Can be None for global queries
            query_path = f"{parent_entry.query_path}/{name_str}"
            # Create query in store
            self.query_store.add_query(ontology, query_path)
            # Create inode for the new directory
            inode = self._get_or_create_query_inode(ontology, query_path, parent_inode)

        else:
            # Can't mkdir under documents_dir, etc.
            raise pyfuse3.FUSEError(errno.EPERM)

        # Invalidate parent cache
        self._invalidate_cache(parent_inode)

        return await self.getattr(inode, ctx)

    async def rmdir(self, parent_inode: int, name: bytes, ctx: pyfuse3.RequestContext) -> None:
        """Remove a query directory."""
        name_str = name.decode("utf-8")
        log.info(f"rmdir: parent={parent_inode}, name={name_str}")

        parent_entry = self._inodes.get(parent_inode)
        if not parent_entry:
            raise pyfuse3.FUSEError(errno.ENOENT)

        # Determine ontology scope and query path based on parent type
        if parent_entry.entry_type == "root":
            # Global query at root level
            ontology = None
            query_path = name_str
        elif parent_entry.entry_type == "ontology":
            # Query scoped to this ontology
            ontology = parent_entry.ontology
            query_path = name_str
        elif parent_entry.entry_type == "query":
            # Nested query
            ontology = parent_entry.ontology  # Can be None for global queries
            query_path = f"{parent_entry.query_path}/{name_str}"
        else:
            # Can't rmdir from ontology_root, documents_dir, etc.
            raise pyfuse3.FUSEError(errno.EPERM)

        # Check it exists
        if not self.query_store.is_query_dir(ontology, query_path):
            raise pyfuse3.FUSEError(errno.ENOENT)

        # Remove from store (also removes children)
        self.query_store.remove_query(ontology, query_path)

        # Find all query inodes to remove (the target and any nested queries)
        query_inodes_to_remove = set()
        for inode, entry in self._inodes.items():
            if entry.entry_type == "query" and entry.ontology == ontology:
                if entry.query_path == query_path or entry.query_path.startswith(query_path + "/"):
                    query_inodes_to_remove.add(inode)

        # Recursively find all descendant inodes (concepts, meta_dir, meta_files, symlinks)
        all_inodes_to_remove = set(query_inodes_to_remove)
        changed = True
        while changed:
            changed = False
            for inode, entry in self._inodes.items():
                if inode not in all_inodes_to_remove and entry.parent in all_inodes_to_remove:
                    all_inodes_to_remove.add(inode)
                    changed = True

        # Remove all identified inodes
        for inode in all_inodes_to_remove:
            if inode in self._inodes:
                del self._inodes[inode]
                self._free_inode(inode)
                self._invalidate_cache(inode)

        # Invalidate parent cache
        self._invalidate_cache(parent_inode)

    async def readdir(self, fh: int, start_id: int, token: pyfuse3.ReaddirToken) -> None:
        """Read directory contents with stale-while-revalidate.

        If the epoch changed and we have cached directory listings, serves
        stale data immediately and spawns a background refresh. The kernel
        is notified via invalidate_inode when fresh data arrives.
        """
        log.debug(f"readdir: fh={fh}, start_id={start_id}")

        # Check graph epoch (does not invalidate — stale data survives)
        await self._cache.check_epoch()

        entry = self._inodes.get(fh)
        if not entry:
            return

        entries = []

        if entry.entry_type == "root":
            entries = await self._list_root_contents(fh)

        elif entry.entry_type == "ontology_root":
            entries = await self._list_ontologies()

        elif entry.entry_type == "ontology":
            entries = await self._list_ontology_contents(fh, entry.ontology)

        elif entry.entry_type == "documents_dir":
            entries = await self._list_documents(fh, entry.ontology)

        elif entry.entry_type == "query":
            meta_inode = self._get_or_create_meta_dir_inode(entry.ontology, entry.query_path, fh)
            entries.append((meta_inode, ".meta"))
            results = await self._list_query_results(fh, entry.ontology, entry.query_path)
            entries.extend(results)

        elif entry.entry_type == "images_dir":
            entries = await self._image_handler.list_query_images(
                fh, entry.ontology, entry.query_path,
                cache=self._cache
            )

        elif entry.entry_type == "meta_dir":
            for meta_key in self.META_FILES:
                inode = self._get_or_create_meta_file_inode(meta_key, entry.ontology, entry.query_path, fh)
                entries.append((inode, meta_key))

        # Spawn background refresh if directory listing is stale
        if (self._cache.get_dir(fh) is not None
                and not self._cache.is_dir_fresh(fh)):
            self._cache.spawn_dir_refresh(fh, lambda: self._refresh_dir(fh, entry))

        # Emit entries starting from start_id
        for idx, (inode, name) in enumerate(entries):
            if idx < start_id:
                continue
            attr = await self.getattr(inode, None)
            if not pyfuse3.readdir_reply(token, name.encode("utf-8"), attr, idx + 1):
                break

    async def _refresh_dir(self, fh: int, entry: InodeEntry) -> list[tuple[int, str]]:
        """Fetch fresh directory listing for background refresh.

        Invalidates the stale cache entry first so the _list_* methods
        re-fetch from the API instead of returning stale data.
        """
        self._cache.invalidate_dir(fh)

        if entry.entry_type == "root":
            return await self._list_root_contents(fh)
        elif entry.entry_type == "ontology_root":
            return await self._list_ontologies()
        elif entry.entry_type == "ontology":
            return await self._list_ontology_contents(fh, entry.ontology)
        elif entry.entry_type == "documents_dir":
            return await self._list_documents(fh, entry.ontology)
        elif entry.entry_type == "query":
            entries = []
            meta_inode = self._get_or_create_meta_dir_inode(entry.ontology, entry.query_path, fh)
            entries.append((meta_inode, ".meta"))
            results = await self._list_query_results(fh, entry.ontology, entry.query_path)
            entries.extend(results)
            return entries
        elif entry.entry_type == "images_dir":
            return await self._image_handler.list_query_images(
                fh, entry.ontology, entry.query_path,
                cache=self._cache
            )
        return []

    async def _list_root_contents(self, parent_inode: int) -> list[tuple[int, str]]:
        """List root directory contents: ontology/ + global user queries."""
        entries = []

        # Fixed: the "ontology" directory
        entries.append((self.ONTOLOGY_ROOT_INODE, "ontology"))

        # Global user queries (ontology=None)
        global_queries = self.query_store.list_queries_under(None, "")
        for query_name in global_queries:
            inode = self._get_or_create_query_inode(None, query_name, parent_inode)
            entries.append((inode, query_name))

        return entries

    async def _list_ontologies(self) -> list[tuple[int, str]]:
        """List ontologies as directories under /ontology/."""
        cache_key = self.ONTOLOGY_ROOT_INODE
        cached = self._cache.get_dir(cache_key)
        if cached is not None:
            return cached

        try:
            data = await self._api.get("/ontology/")
            ontologies = data.get("ontologies", [])

            entries = []
            seen_names = set()
            for ont in ontologies:
                name = ont.get("ontology", "unknown")
                seen_names.add(name)
                # Allocate inode for this ontology
                inode = self._get_or_create_ontology_inode(name)
                entries.append((inode, name))

            # Add pending ontologies (created with mkdir but no documents yet)
            for pending_name in self._pending_ontologies:
                if pending_name not in seen_names:
                    inode = self._get_or_create_ontology_inode(pending_name)
                    entries.append((inode, pending_name))

            self._cache.put_dir(cache_key, entries)
            return entries

        except Exception as e:
            log.error(f"Failed to list ontologies: {e}")
            return []

    async def _list_ontology_contents(self, parent_inode: int, ontology: str) -> list[tuple[int, str]]:
        """List contents of an ontology directory: documents/ + user queries."""
        cached = self._cache.get_dir(parent_inode)
        if cached is not None:
            return cached

        entries = []

        # Fixed: the "documents" directory
        docs_inode = self._get_or_create_documents_dir_inode(ontology, parent_inode)
        entries.append((docs_inode, "documents"))

        # Add user-created query directories
        query_dirs = self.query_store.list_queries_under(ontology, "")
        for query_name in query_dirs:
            inode = self._get_or_create_query_inode(ontology, query_name, parent_inode)
            entries.append((inode, query_name))

        self._cache.put_dir(parent_inode, entries)
        return entries

    async def _list_documents(self, parent_inode: int, ontology: str) -> list[tuple[int, str]]:
        """List document files inside an ontology's documents/ directory.

        Also includes virtual job files ({filename}.ingesting) for jobs tracked locally.
        Uses lazy polling: jobs are only polled when their .job file is read.
        """
        cached = self._cache.get_dir(parent_inode)
        if cached is not None:
            return cached

        entries = []

        # Get documents from API
        try:
            data = await self._api.get("/documents", params={"ontology": ontology, "limit": 100})
            documents = data.get("documents", [])

            for doc in documents:
                filename = doc.get("filename", doc.get("document_id", "unknown"))
                document_id = doc.get("document_id")
                content_type = doc.get("content_type", "document")

                if content_type == "image":
                    # Image: two entries — raw image bytes + companion .md
                    img_inode = self._image_handler.get_or_create_image_document_inode(
                        filename, parent_inode, ontology, document_id
                    )
                    entries.append((img_inode, filename))

                    prose_name = f"{filename}.md"
                    prose_inode = self._image_handler.get_or_create_image_prose_inode(
                        prose_name, parent_inode, ontology, document_id
                    )
                    entries.append((prose_inode, prose_name))
                else:
                    # Text document: single entry (unchanged)
                    inode = self._get_or_create_document_inode(
                        filename, parent_inode, ontology, document_id
                    )
                    entries.append((inode, filename))

        except Exception as e:
            log.error(f"Failed to list documents for {ontology}: {e}")

        # Add tracked jobs for this ontology as virtual files (no API call!)
        # JobTracker handles atomic cleanup of completed/stale jobs
        for job in self._job_tracker.get_jobs_for_ontology(ontology):
            virtual_name = self.jobs_config.format_job_filename(job.filename)
            inode = self._get_or_create_job_inode(
                virtual_name, parent_inode, ontology, job.job_id
            )
            entries.append((inode, virtual_name))

            # For image jobs, also show companion .md as ingesting
            if _is_image_file(job.filename):
                md_virtual_name = self.jobs_config.format_job_filename(f"{job.filename}.md")
                md_inode = self._get_or_create_job_inode(
                    md_virtual_name, parent_inode, ontology, job.job_id
                )
                entries.append((md_inode, md_virtual_name))

        self._cache.put_dir(parent_inode, entries)
        return entries

    async def _list_query_results(self, parent_inode: int, ontology: Optional[str], query_path: str) -> list[tuple[int, str]]:
        """Execute semantic search and list results + child queries + symlinks."""
        cached = self._cache.get_dir(parent_inode)
        if cached is not None:
            return cached

        entries = []

        # Get the query chain for nested resolution
        queries = self.query_store.get_query_chain(ontology, query_path)
        if not queries:
            log.warning(f"No query found for {ontology}/{query_path}")
            return entries

        leaf_query = queries[-1]

        # Execute semantic search with AND intersection for nested queries
        try:
            # For global queries with symlinks, search those specific ontologies
            # Otherwise search the scoped ontology (or all if global without symlinks)
            symlinked_ontologies = leaf_query.symlinks if ontology is None else []

            # Collect all query terms from hierarchy for AND intersection
            query_terms = [q.query_text for q in queries]

            results = await self._execute_search(
                ontology,
                query_terms,  # Pass list for AND intersection
                leaf_query.threshold,
                leaf_query.limit,
                symlinked_ontologies,
                exclude_terms=leaf_query.exclude,
                union_terms=leaf_query.union
            )

            for concept in results:
                concept_id = concept.get("concept_id", "unknown")
                concept_name = concept.get("label", concept_id)
                # Sanitize name for filename
                safe_name = self._sanitize_filename(concept_name)
                filename = f"{safe_name}.concept.md"

                inode = self._get_or_create_concept_inode(
                    filename, parent_inode, ontology, query_path, concept_id
                )
                entries.append((inode, filename))

        except Exception as e:
            log.error(f"Failed to execute search for {ontology}/{query_path}: {e}")

        # Always include images/ directory (lazy-loaded on readdir)
        images_dir_inode = self._image_handler.get_or_create_images_dir_inode(ontology, query_path, parent_inode)
        entries.append((images_dir_inode, "images"))

        # Add child query directories
        child_queries = self.query_store.list_queries_under(ontology, query_path)
        for child_name in child_queries:
            child_path = f"{query_path}/{child_name}"
            inode = self._get_or_create_query_inode(ontology, child_path, parent_inode)
            entries.append((inode, child_name))

        # Add symlinks (for global queries only)
        if ontology is None:
            for linked_ont in leaf_query.symlinks:
                target = f"../ontology/{linked_ont}"
                inode = self._get_or_create_symlink_inode(linked_ont, linked_ont, query_path, target, parent_inode)
                entries.append((inode, linked_ont))

        self._cache.put_dir(parent_inode, entries)
        return entries

    async def _execute_search(
        self,
        ontology: Optional[str],
        query_terms: list[str],
        threshold: float,
        limit: int = 50,
        symlinked_ontologies: list[str] = None,
        exclude_terms: list[str] = None,
        union_terms: list[str] = None
    ) -> list[dict]:
        """Execute semantic search via API with full filtering model.

        Args:
            ontology: Single ontology to search (None for global)
            query_terms: List of search terms (AND intersection if multiple)
            threshold: Minimum similarity score
            limit: Maximum results
            symlinked_ontologies: For global queries, list of ontologies to search
            exclude_terms: Terms to exclude from results (semantic NOT)
            union_terms: Additional terms to include (semantic OR)
        """
        exclude_terms = exclude_terms or []
        union_terms = union_terms or []

        try:
            async def search_single_term(term: str, ontologies: list[str] = None, fetch_limit: int = None) -> list[dict]:
                """Search for a single term, optionally across multiple ontologies."""
                body = {
                    "query": term,
                    "min_similarity": threshold,
                    "limit": fetch_limit or limit * 2,  # Fetch more for intersection/filtering
                }

                if ontology is not None:
                    # Scoped query - search single ontology
                    body["ontology"] = ontology
                    result = await self._api.post("/query/search", json=body)
                    return result.get("results", [])
                elif ontologies:
                    # Global query with symlinks - search specific ontologies
                    all_results = []
                    for ont in ontologies:
                        body["ontology"] = ont
                        result = await self._api.post("/query/search", json=body)
                        all_results.extend(result.get("results", []))
                    return all_results
                else:
                    # Global query without symlinks - search all
                    result = await self._api.post("/query/search", json=body)
                    return result.get("results", [])

            # Step 1: Get base results from query terms (AND intersection)
            concept_data = {}  # concept_id -> full result dict

            if len(query_terms) == 1:
                # Single term: simple search
                results = await search_single_term(query_terms[0], symlinked_ontologies)
                for r in results:
                    cid = r.get("concept_id")
                    if cid not in concept_data or r.get("score", 0) > concept_data[cid].get("score", 0):
                        concept_data[cid] = r
                base_ids = set(concept_data.keys())
            else:
                # Multiple terms: AND intersection
                result_sets = []
                for term in query_terms:
                    results = await search_single_term(term, symlinked_ontologies)
                    concept_ids = set()
                    for r in results:
                        cid = r.get("concept_id")
                        concept_ids.add(cid)
                        if cid not in concept_data or r.get("score", 0) > concept_data[cid].get("score", 0):
                            concept_data[cid] = r
                    result_sets.append(concept_ids)

                if not result_sets:
                    base_ids = set()
                else:
                    base_ids = result_sets[0]
                    for rs in result_sets[1:]:
                        base_ids = base_ids & rs

            # Step 2: Add union terms (semantic OR - expand results)
            if union_terms:
                for term in union_terms:
                    results = await search_single_term(term, symlinked_ontologies, fetch_limit=limit)
                    for r in results:
                        cid = r.get("concept_id")
                        base_ids.add(cid)  # Add to result set
                        if cid not in concept_data or r.get("score", 0) > concept_data[cid].get("score", 0):
                            concept_data[cid] = r

            # Step 3: Apply exclude terms (semantic NOT - filter results)
            if exclude_terms:
                exclude_ids = set()
                for term in exclude_terms:
                    results = await search_single_term(term, symlinked_ontologies, fetch_limit=limit * 2)
                    for r in results:
                        exclude_ids.add(r.get("concept_id"))
                # Remove excluded concepts
                base_ids = base_ids - exclude_ids

            # Step 4: Build final results, sorted by similarity
            matched = [concept_data[cid] for cid in base_ids if cid in concept_data]
            matched.sort(key=lambda x: x.get("score", 0), reverse=True)
            return matched[:limit]

        except Exception as e:
            log.error(f"Search failed: {e}")
            return []

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

    # The virtual files available in .meta directories
    META_FILES = ["limit", "threshold", "exclude", "union", "query.toml"]

    def _render_meta_file(self, entry: InodeEntry) -> str:
        """Render content for a .meta virtual file."""
        query = self.query_store.get_query(entry.ontology, entry.query_path)
        return render_meta_file(entry.meta_key, query, entry.ontology)

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

    def set_nursery(self, nursery):
        """Set the trio nursery for background tasks. Called by main.py."""
        self._cache.set_nursery(nursery)

    def _invalidate_cache(self, inode: int):
        """Invalidate cache for an inode."""
        self._cache.invalidate_dir(inode)
        self._cache.invalidate_content(inode)

    async def open(self, inode: int, flags: int, ctx: pyfuse3.RequestContext) -> pyfuse3.FileInfo:
        """Open a file."""
        if inode not in self._inodes:
            raise pyfuse3.FUSEError(errno.ENOENT)

        entry = self._inodes[inode]
        if entry.entry_type not in ("document", "concept", "meta_file", "ingestion_file", "job_file",
                                     "image_document", "image_prose", "image_evidence"):
            raise pyfuse3.FUSEError(errno.EISDIR)

        # Check write permissions for meta files
        if entry.entry_type == "meta_file":
            # query.toml is read-only
            if entry.meta_key == "query.toml" and (flags & os.O_WRONLY or flags & os.O_RDWR):
                raise pyfuse3.FUSEError(errno.EACCES)

        # Job files are read-only
        if entry.entry_type == "job_file" and (flags & os.O_WRONLY or flags & os.O_RDWR):
            raise pyfuse3.FUSEError(errno.EACCES)

        fi = pyfuse3.FileInfo(fh=inode)

        # Image entries have unknown size until first read — use direct_io
        # to bypass kernel page cache so reads aren't limited by st_size
        if entry.entry_type in ("image_document", "image_evidence"):
            fi.direct_io = True

        return fi

    async def read(self, fh: int, off: int, size: int) -> bytes:
        """Read file contents with stale-while-revalidate.

        Cache flow:
        1. Epoch unchanged + cached → serve fresh (zero API calls)
        2. Epoch changed + cached → serve stale instantly, background refresh
        3. No cache → block on first fetch (unavoidable)

        Image bytes are handled by ImageHandler's immutable cache.
        """
        entry = self._inodes.get(fh)
        if not entry:
            raise pyfuse3.FUSEError(errno.ENOENT)

        # Check graph epoch (throttled)
        await self._cache.check_epoch()

        # Image types have their own immutable cache — skip content cache
        if entry.entry_type == "image_document":
            content_bytes = await self._image_handler.read_image_bytes(entry)
            return content_bytes[off:off + size]
        elif entry.entry_type == "image_evidence":
            content_bytes = await self._image_handler.read_image_evidence(entry)
            return content_bytes[off:off + size]

        # For cacheable types: check content cache first
        # (meta_file and job_file are dynamic/local — don't cache)
        cacheable = entry.entry_type in ("document", "concept", "image_prose")

        if cacheable:
            cached = self._cache.get_content(fh)
            if cached is not None:
                if not self._cache.is_content_fresh(fh):
                    # Stale — serve immediately, refresh in background
                    self._cache.spawn_refresh(fh, lambda e=entry: self._fetch_content(e))
                return cached[off:off + size]

        # No cache — block on fetch
        try:
            content_bytes = await self._fetch_content(entry)

            if cacheable:
                self._cache.put_content(fh, content_bytes)

            return content_bytes[off:off + size]

        except Exception as e:
            log.error(f"Failed to read file: {e}")
            return f"# Error reading file: {e}\n".encode("utf-8")

    async def _fetch_content(self, entry: InodeEntry) -> bytes:
        """Fetch file content from API. Used by both sync reads and background refresh."""
        if entry.entry_type == "document":
            content = await self._read_document(entry)
        elif entry.entry_type == "image_prose":
            content = await self._image_handler.read_image_prose(entry)
        elif entry.entry_type == "concept":
            content = await self._read_concept(entry)
        elif entry.entry_type == "meta_file":
            content = self._render_meta_file(entry)
        elif entry.entry_type == "job_file":
            content = await self._read_job(entry)
        else:
            content = "# Unknown file type\n"
        return content.encode("utf-8")

    async def _read_document(self, entry: InodeEntry) -> str:
        """Read and format a document file."""
        if not entry.document_id:
            return "# No document ID\n"

        data = await self._api.get(f"/documents/{entry.document_id}/content")

        # Fetch concepts if tags are enabled
        concepts = []
        if self.tags_config.enabled:
            try:
                concepts_data = await self._api.get(f"/documents/{entry.document_id}/concepts")
                concepts = concepts_data.get("concepts", [])
            except Exception as e:
                log.debug(f"Could not fetch concepts for document: {e}")

        return self._format_document(data, concepts)

    async def _read_concept(self, entry: InodeEntry) -> str:
        """Read and format a concept file."""
        if not entry.concept_id:
            return "# No concept ID\n"

        data = await self._api.get(f"/query/concept/{entry.concept_id}")
        return self._format_concept(data)

    async def _read_job(self, entry: InodeEntry) -> str:
        """Read and format a job status file.

        This is where lazy polling happens - we only fetch job status
        when someone actually reads the .job file.

        If the job is complete (terminal status), we mark it for removal
        so the next directory listing won't show it.
        """
        if not entry.job_id:
            return "# No job ID\n"

        try:
            data = await self._api.get(f"/jobs/{entry.job_id}")
        except Exception as e:
            # Job may have been deleted - mark for removal
            log.debug(f"Job {entry.job_id} not found, marking for removal: {e}")
            self._job_tracker.mark_job_not_found(entry.job_id)
            self._invalidate_cache(entry.parent)
            return f"# Job Not Found\n\njob_id = \"{entry.job_id}\"\nerror = \"Job no longer exists\"\n"

        status = data.get("status", "unknown")

        # Update job tracker with status (handles seen_complete logic)
        self._job_tracker.mark_job_status(entry.job_id, status)

        # If job is now marked for removal, invalidate caches
        job = self._job_tracker.get_job(entry.job_id)
        if job and job.marked_for_removal:
            self._invalidate_cache(entry.parent)
            # Notify kernel so file managers refresh
            try:
                pyfuse3.invalidate_inode(entry.parent, attr_only=False)
            except Exception:
                pass  # Non-critical

        return format_job(data)

    def _format_document(self, data: dict, concepts: list = None) -> str:
        """Format document data as markdown with optional YAML frontmatter."""
        return format_document(data, concepts, self.tags_config)

    def _format_concept(self, data: dict) -> str:
        """Format concept data as markdown with YAML frontmatter."""
        return format_concept(data, self.tags_config)

    async def write(self, fh: int, off: int, buf: bytes) -> int:
        """Write to a file (meta files and ingestion files are writable)."""
        entry = self._inodes.get(fh)
        if not entry:
            raise pyfuse3.FUSEError(errno.ENOENT)

        # Handle ingestion file writes - buffer content
        if entry.entry_type == "ingestion_file":
            if fh not in self._write_buffers:
                self._write_buffers[fh] = b""
            # Check size limit before accepting more data
            new_size = max(off + len(buf), len(self._write_buffers[fh]))
            if new_size > MAX_INGESTION_SIZE:
                log.error(f"File exceeds maximum ingestion size ({MAX_INGESTION_SIZE} bytes)")
                raise pyfuse3.FUSEError(errno.EFBIG)
            # Append to buffer at offset (usually sequential)
            current = self._write_buffers[fh]
            if off == len(current):
                self._write_buffers[fh] = current + buf
            else:
                # Handle sparse writes by padding if needed
                if off > len(current):
                    current = current + b"\x00" * (off - len(current))
                self._write_buffers[fh] = current[:off] + buf + current[off + len(buf):]
            # Update size
            entry.size = len(self._write_buffers[fh])
            return len(buf)

        if entry.entry_type != "meta_file":
            raise pyfuse3.FUSEError(errno.EACCES)

        if entry.meta_key == "query.toml":
            raise pyfuse3.FUSEError(errno.EACCES)  # Read-only

        try:
            # Decode the written content
            content = buf.decode("utf-8").strip()
            if not content:
                return len(buf)

            # Parse and apply the value based on meta_key
            if entry.meta_key == "limit":
                # Extract the number (skip comment lines)
                for line in content.split("\n"):
                    line = line.strip()
                    if line and not line.startswith("#"):
                        try:
                            limit = int(line)
                            self.query_store.update_limit(entry.ontology, entry.query_path, limit)
                            # Invalidate query cache so results refresh
                            self._invalidate_query_cache(entry.ontology, entry.query_path)
                        except ValueError:
                            pass  # Ignore invalid numbers
                        break

            elif entry.meta_key == "threshold":
                # Extract the float (skip comment lines)
                for line in content.split("\n"):
                    line = line.strip()
                    if line and not line.startswith("#"):
                        try:
                            threshold = float(line)
                            self.query_store.update_threshold(entry.ontology, entry.query_path, threshold)
                            self._invalidate_query_cache(entry.ontology, entry.query_path)
                        except ValueError:
                            pass
                        break

            elif entry.meta_key == "exclude":
                # Add each non-comment line as an exclude term
                for line in content.split("\n"):
                    line = line.strip()
                    if line and not line.startswith("#"):
                        self.query_store.add_exclude(entry.ontology, entry.query_path, line)
                self._invalidate_query_cache(entry.ontology, entry.query_path)

            elif entry.meta_key == "union":
                # Add each non-comment line as a union term
                for line in content.split("\n"):
                    line = line.strip()
                    if line and not line.startswith("#"):
                        self.query_store.add_union(entry.ontology, entry.query_path, line)
                self._invalidate_query_cache(entry.ontology, entry.query_path)

            return len(buf)

        except Exception as e:
            log.error(f"Failed to write meta file: {e}")
            raise pyfuse3.FUSEError(errno.EIO)

    async def setattr(self, inode: int, attr: pyfuse3.EntryAttributes, fields: pyfuse3.SetattrFields, fh: int, ctx: pyfuse3.RequestContext) -> pyfuse3.EntryAttributes:
        """Set file attributes (needed for truncate on write)."""
        entry = self._inodes.get(inode)
        if not entry:
            raise pyfuse3.FUSEError(errno.ENOENT)

        # For meta files, truncate clears the value
        if entry.entry_type == "meta_file" and fields.update_size and attr.st_size == 0:
            if entry.meta_key == "query.toml":
                raise pyfuse3.FUSEError(errno.EACCES)

            # Clear the appropriate field
            if entry.meta_key == "exclude":
                self.query_store.clear_exclude(entry.ontology, entry.query_path)
                self._invalidate_query_cache(entry.ontology, entry.query_path)
            elif entry.meta_key == "union":
                self.query_store.clear_union(entry.ontology, entry.query_path)
                self._invalidate_query_cache(entry.ontology, entry.query_path)
            # limit and threshold don't have clear - they just keep their value

        return await self.getattr(inode, ctx)

    def _invalidate_query_cache(self, ontology: Optional[str], query_path: str):
        """Invalidate cache for a query directory when its parameters change."""
        # Find the query inode and invalidate its cache
        for inode, entry in self._inodes.items():
            if (entry.entry_type == "query" and
                entry.ontology == ontology and
                entry.query_path == query_path):
                self._invalidate_cache(inode)
                break

    async def symlink(self, parent_inode: int, name: bytes, target: bytes, ctx: pyfuse3.RequestContext) -> pyfuse3.EntryAttributes:
        """Create a symbolic link (for linking ontologies into queries)."""
        name_str = name.decode("utf-8")
        target_str = target.decode("utf-8")
        log.info(f"symlink: parent={parent_inode}, name={name_str}, target={target_str}")

        parent_entry = self._inodes.get(parent_inode)
        if not parent_entry:
            raise pyfuse3.FUSEError(errno.ENOENT)

        # Only allow symlinks in global query directories (not ontology-scoped)
        if parent_entry.entry_type != "query" or parent_entry.ontology is not None:
            log.warning(f"symlink rejected: only allowed in global query dirs")
            raise pyfuse3.FUSEError(errno.EPERM)

        # Validate target points to an ontology
        # Expected format: ../ontology/OntologyName or ../../ontology/OntologyName
        ontology_name = self._parse_ontology_symlink_target(target_str)
        if not ontology_name:
            log.warning(f"symlink rejected: target must be ../ontology/NAME")
            raise pyfuse3.FUSEError(errno.EINVAL)

        # Create inode for symlink
        inode = self._allocate_inode()
        self._inodes[inode] = InodeEntry(
            name=name_str,
            entry_type="symlink",
            parent=parent_inode,
            ontology=ontology_name,  # Store the linked ontology name
            query_path=parent_entry.query_path,
            symlink_target=target_str,
        )

        # Track symlink in query store
        self.query_store.add_symlink(None, parent_entry.query_path, ontology_name)

        # Invalidate parent cache
        self._invalidate_cache(parent_inode)

        return await self.getattr(inode, ctx)

    def _parse_ontology_symlink_target(self, target: str) -> Optional[str]:
        """Parse symlink target to extract ontology name.

        Valid formats:
        - ../ontology/OntologyName
        - ../../ontology/OntologyName

        Ontology names must be alphanumeric with dashes/underscores only.
        """
        # Relative: ../ontology/Name or ../../ontology/Name
        # Restrict ontology name to alphanumeric, dash, underscore for security
        match = re.match(r'^(?:\.\./)+ontology/([A-Za-z0-9_-]+)$', target)
        if match:
            return match.group(1)
        return None

    async def readlink(self, inode: int, ctx: pyfuse3.RequestContext) -> bytes:
        """Read the target of a symbolic link."""
        entry = self._inodes.get(inode)
        if not entry:
            raise pyfuse3.FUSEError(errno.ENOENT)

        if entry.entry_type != "symlink":
            raise pyfuse3.FUSEError(errno.EINVAL)

        return entry.symlink_target.encode("utf-8")

    async def unlink(self, parent_inode: int, name: bytes, ctx: pyfuse3.RequestContext) -> None:
        """Remove a file or symlink."""
        name_str = name.decode("utf-8")
        log.info(f"unlink: parent={parent_inode}, name={name_str}")

        # Find the entry
        target_inode = None
        target_entry = None
        for inode, entry in self._inodes.items():
            if entry.parent == parent_inode and entry.name == name_str:
                target_inode = inode
                target_entry = entry
                break

        if not target_entry:
            raise pyfuse3.FUSEError(errno.ENOENT)

        # Only allow unlinking symlinks
        if target_entry.entry_type != "symlink":
            raise pyfuse3.FUSEError(errno.EPERM)

        # Remove from query store
        parent_entry = self._inodes.get(parent_inode)
        if parent_entry and parent_entry.entry_type == "query":
            self.query_store.remove_symlink(None, parent_entry.query_path, target_entry.ontology)

        # Remove inode and recycle it
        del self._inodes[target_inode]
        self._free_inode(target_inode)

        # Invalidate parent cache
        self._invalidate_cache(parent_inode)

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

    async def create(self, parent_inode: int, name: bytes, mode: int, flags: int, ctx: pyfuse3.RequestContext) -> tuple[pyfuse3.FileInfo, pyfuse3.EntryAttributes]:
        """Create a file for ingestion (black hole - file gets ingested on release)."""
        name_str = name.decode("utf-8")
        log.info(f"create: parent={parent_inode}, name={name_str}")

        parent_entry = self._inodes.get(parent_inode)
        if not parent_entry:
            raise pyfuse3.FUSEError(errno.ENOENT)

        # Only allow creating files directly in ontology directories (for ingestion)
        if parent_entry.entry_type != "ontology":
            log.warning(f"create rejected: can only create files in ontology dirs, got {parent_entry.entry_type}")
            raise pyfuse3.FUSEError(errno.EPERM)

        ontology = parent_entry.ontology

        # Create a temporary inode for the file being written
        inode = self._allocate_inode()
        self._inodes[inode] = InodeEntry(
            name=name_str,
            entry_type="ingestion_file",  # Special type for files being ingested
            parent=parent_inode,
            ontology=ontology,
            size=0,
        )

        # Initialize write buffer and info
        self._write_buffers[inode] = b""
        self._write_info[inode] = {
            "ontology": ontology,
            "filename": name_str,
        }

        log.info(f"Created ingestion file: {name_str} in ontology {ontology}, inode={inode}")

        # Return file handle and attributes
        fi = pyfuse3.FileInfo(fh=inode)
        attr = await self.getattr(inode, ctx)
        return (fi, attr)

    async def release(self, fh: int) -> None:
        """Release (close) a file - triggers ingestion for ingestion files."""
        entry = self._inodes.get(fh)
        if not entry:
            return

        # If this is an ingestion file with buffered content, trigger ingestion
        if entry.entry_type == "ingestion_file" and fh in self._write_buffers:
            content = self._write_buffers.pop(fh)
            info = self._write_info.pop(fh, {})

            if content:
                ontology = info.get("ontology", entry.ontology)
                filename = info.get("filename", entry.name)

                log.info(f"Triggering ingestion: {filename} ({len(content)} bytes) into {ontology}")

                try:
                    if _is_image_file(filename):
                        await self._image_handler.ingest_image(ontology, filename, content)
                    else:
                        await self._ingest_document(ontology, filename, content)
                    log.info(f"Ingestion submitted successfully: {filename}")

                    # Remove from pending ontologies if this was the first document
                    if ontology in self._pending_ontologies:
                        self._pending_ontologies.discard(ontology)
                        log.info(f"Ontology {ontology} is no longer pending")

                    # Invalidate documents dir so new job files show up.
                    # Both internal cache (epoch-gated) and kernel cache.
                    docs_dir_inode = self._find_documents_dir_inode(ontology)
                    if docs_dir_inode:
                        self._invalidate_cache(docs_dir_inode)
                        try:
                            pyfuse3.invalidate_inode(docs_dir_inode, attr_only=False)
                            log.debug(f"Invalidated documents directory for {ontology}")
                        except OSError as e:
                            log.debug(f"invalidate_inode not supported: {e}")
                        except Exception as notify_err:
                            log.debug(f"Kernel notification failed (non-critical): {notify_err}")

                except Exception as e:
                    log.error(f"Ingestion failed for {filename}: {e}")

            # Clean up the temporary inode (file disappears after ingestion)
            if fh in self._inodes:
                parent_inode = self._inodes[fh].parent
                del self._inodes[fh]
                self._free_inode(fh)
                # Invalidate parent cache so new documents show up
                if parent_inode:
                    self._invalidate_cache(parent_inode)

    async def _ingest_document(self, ontology: str, filename: str, content: bytes) -> dict:
        """Submit document to ingestion API and track the job."""
        # Use multipart form upload
        files = {"file": (filename, content)}
        data = {
            "ontology": ontology,
            "auto_approve": "true",  # Auto-approve for FUSE ingestions
        }

        result = await self._api.post("/ingest", data=data, files=files)
        log.info(f"Ingestion response: {result}")

        # Track the job so it shows as a .ingesting file until complete
        job_id = result.get("job_id")
        if job_id:
            self._job_tracker.track_job(job_id, ontology, filename)

        return result

    # ── Extended attributes (hydration state) ───────────────────────────

    _XATTR_PREFIX = b"user.kg."
    _KNOWN_XATTRS = (b"user.kg.state", b"user.kg.epoch")

    async def getxattr(self, inode: int, name: bytes, ctx: pyfuse3.RequestContext) -> bytes:
        """Get extended attribute — exposes cache hydration state."""
        if name == b"user.kg.state":
            state = self._cache.hydration_state(inode)
            return state.encode("utf-8")
        elif name == b"user.kg.epoch":
            return str(self._cache.graph_epoch).encode("utf-8")
        raise pyfuse3.FUSEError(errno.ENODATA)

    async def listxattrs(self, inode: int, ctx: pyfuse3.RequestContext) -> list[bytes]:
        """List available extended attributes."""
        if inode in self._inodes:
            return list(self._KNOWN_XATTRS)
        return []

    # ── Lifecycle ─────────────────────────────────────────────────────

    async def destroy(self) -> None:
        """Clean up resources on unmount."""
        log.info("Destroying filesystem, cleaning up resources")
        await self._api.close()
        self._cache.clear()
        self._write_buffers.clear()
        self._job_tracker.clear()
        self._write_info.clear()
        self._image_handler.clear_cache()
