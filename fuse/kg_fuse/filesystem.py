"""
Knowledge Graph FUSE Filesystem Operations

Hierarchy:
- /                              - Mount root (ontology/ + user global queries)
- /ontology/                     - Fixed, system-managed ontology listing
- /ontology/{name}/              - Ontology directories (from graph)
- /ontology/{name}/documents/    - Source documents (read-only)
- /ontology/{name}/documents/{doc}.md  - Document content
- /ontology/{name}/{query}/      - User query scoped to ontology
- /{user-query}/                 - User global query (all ontologies)
- /{path}/*.concept.md           - Concept search results
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
import stat
import time
from dataclasses import dataclass
from typing import Optional

import pyfuse3
import httpx

from .query_store import QueryStore
from .config import TagsConfig

log = logging.getLogger(__name__)


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
    size: int = 0


class KnowledgeGraphFS(pyfuse3.Operations):
    """FUSE filesystem backed by Knowledge Graph API."""

    ROOT_INODE = pyfuse3.ROOT_INODE  # 1
    ONTOLOGY_ROOT_INODE = 2  # Fixed inode for /ontology/

    def __init__(self, api_url: str, client_id: str, client_secret: str, tags_config: TagsConfig = None):
        super().__init__()
        self.api_url = api_url.rstrip("/")
        self.client_id = client_id
        self.client_secret = client_secret
        self.tags_config = tags_config or TagsConfig()

        # HTTP client (will be initialized async)
        self._client: Optional[httpx.AsyncClient] = None
        self._token: Optional[str] = None
        self._token_expires: float = 0

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

        # Cache for directory listings and API responses
        self._dir_cache: dict[int, list[tuple[int, str]]] = {}
        self._cache_time: dict[int, float] = {}
        self._cache_ttl = 30.0  # seconds

        # Write support: pending ontologies and ingestion buffers
        self._pending_ontologies: set[str] = set()  # Ontologies created but no documents yet
        self._write_buffers: dict[int, bytes] = {}  # inode -> content being written
        self._write_info: dict[int, dict] = {}  # inode -> {ontology, filename}

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(base_url=self.api_url, timeout=30.0)
        return self._client

    async def _get_token(self) -> str:
        """Get OAuth token, refreshing if needed."""
        if self._token and time.time() < self._token_expires:
            return self._token

        client = await self._get_client()
        response = await client.post(
            "/auth/oauth/token",
            data={
                "grant_type": "client_credentials",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            },
        )
        response.raise_for_status()
        data = response.json()
        self._token = data["access_token"]
        self._token_expires = time.time() + data.get("expires_in", 3600) - 60
        log.debug("Obtained OAuth token")
        return self._token

    async def _api_get(self, path: str, params: Optional[dict] = None) -> dict:
        """Make authenticated GET request to API."""
        token = await self._get_token()
        client = await self._get_client()
        response = await client.get(
            path,
            params=params,
            headers={"Authorization": f"Bearer {token}"},
        )
        response.raise_for_status()
        return response.json()

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
        return entry_type in ("root", "ontology_root", "ontology", "documents_dir", "query", "meta_dir")

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

        # Query directory: .meta + concepts + nested queries
        elif parent_entry.entry_type == "query":
            ontology = parent_entry.ontology  # Can be None for global queries
            parent_path = parent_entry.query_path

            # Check for .meta directory
            if name_str == ".meta":
                inode = self._get_or_create_meta_dir_inode(ontology, parent_path, parent_inode)
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
            inode = self._next_inode
            self._next_inode += 1
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

        # Remove inode and any child inodes
        for inode, entry in list(self._inodes.items()):
            if entry.entry_type == "query" and entry.ontology == ontology:
                if entry.query_path == query_path or entry.query_path.startswith(query_path + "/"):
                    del self._inodes[inode]
                    self._invalidate_cache(inode)

        # Invalidate parent cache
        self._invalidate_cache(parent_inode)

    async def readdir(self, fh: int, start_id: int, token: pyfuse3.ReaddirToken) -> None:
        """Read directory contents."""
        log.debug(f"readdir: fh={fh}, start_id={start_id}")

        entry = self._inodes.get(fh)
        if not entry:
            return

        entries = []

        if entry.entry_type == "root":
            # Root: "ontology" (fixed) + global user queries
            entries = await self._list_root_contents(fh)

        elif entry.entry_type == "ontology_root":
            # ontology/: list actual ontologies from graph
            entries = await self._list_ontologies()

        elif entry.entry_type == "ontology":
            # Ontology: "documents" (fixed) + user queries
            entries = await self._list_ontology_contents(fh, entry.ontology)

        elif entry.entry_type == "documents_dir":
            # documents/: list source document files
            entries = await self._list_documents(fh, entry.ontology)

        elif entry.entry_type == "query":
            # Query: .meta + execute search + list child queries
            # Add .meta directory first
            meta_inode = self._get_or_create_meta_dir_inode(entry.ontology, entry.query_path, fh)
            entries.append((meta_inode, ".meta"))
            # Add query results and child queries
            results = await self._list_query_results(fh, entry.ontology, entry.query_path)
            entries.extend(results)

        elif entry.entry_type == "meta_dir":
            # .meta/: list virtual config files
            for meta_key in self.META_FILES:
                inode = self._get_or_create_meta_file_inode(meta_key, entry.ontology, entry.query_path, fh)
                entries.append((inode, meta_key))

        # Emit entries starting from start_id
        for idx, (inode, name) in enumerate(entries):
            if idx < start_id:
                continue
            attr = await self.getattr(inode, None)
            if not pyfuse3.readdir_reply(token, name.encode("utf-8"), attr, idx + 1):
                break

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
        # Check cache
        cache_key = self.ONTOLOGY_ROOT_INODE
        if cache_key in self._dir_cache:
            if time.time() - self._cache_time.get(cache_key, 0) < self._cache_ttl:
                return self._dir_cache[cache_key]

        try:
            data = await self._api_get("/ontology/")
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

            # Cache result
            self._dir_cache[cache_key] = entries
            self._cache_time[cache_key] = time.time()

            return entries

        except Exception as e:
            log.error(f"Failed to list ontologies: {e}")
            return []

    async def _list_ontology_contents(self, parent_inode: int, ontology: str) -> list[tuple[int, str]]:
        """List contents of an ontology directory: documents/ + user queries."""
        # Check cache
        if parent_inode in self._dir_cache:
            if time.time() - self._cache_time.get(parent_inode, 0) < self._cache_ttl:
                return self._dir_cache[parent_inode]

        entries = []

        # Fixed: the "documents" directory
        docs_inode = self._get_or_create_documents_dir_inode(ontology, parent_inode)
        entries.append((docs_inode, "documents"))

        # Add user-created query directories
        query_dirs = self.query_store.list_queries_under(ontology, "")
        for query_name in query_dirs:
            inode = self._get_or_create_query_inode(ontology, query_name, parent_inode)
            entries.append((inode, query_name))

        # Cache result
        self._dir_cache[parent_inode] = entries
        self._cache_time[parent_inode] = time.time()

        return entries

    async def _list_documents(self, parent_inode: int, ontology: str) -> list[tuple[int, str]]:
        """List document files inside an ontology's documents/ directory."""
        # Check cache
        if parent_inode in self._dir_cache:
            if time.time() - self._cache_time.get(parent_inode, 0) < self._cache_ttl:
                return self._dir_cache[parent_inode]

        entries = []

        # Get documents from API
        try:
            data = await self._api_get("/documents", params={"ontology": ontology, "limit": 100})
            documents = data.get("documents", [])

            for doc in documents:
                filename = doc.get("filename", doc.get("document_id", "unknown"))
                inode = self._get_or_create_document_inode(
                    filename, parent_inode, ontology,
                    doc.get("document_id")
                )
                entries.append((inode, filename))

        except Exception as e:
            log.error(f"Failed to list documents for {ontology}: {e}")

        # Cache result
        self._dir_cache[parent_inode] = entries
        self._cache_time[parent_inode] = time.time()

        return entries

    async def _list_query_results(self, parent_inode: int, ontology: Optional[str], query_path: str) -> list[tuple[int, str]]:
        """Execute semantic search and list results + child queries + symlinks."""
        # Check cache
        if parent_inode in self._dir_cache:
            if time.time() - self._cache_time.get(parent_inode, 0) < self._cache_ttl:
                return self._dir_cache[parent_inode]

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

        # Cache result
        self._dir_cache[parent_inode] = entries
        self._cache_time[parent_inode] = time.time()

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
            token = await self._get_token()
            client = await self._get_client()

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
                    response = await client.post(
                        "/query/search",
                        json=body,
                        headers={"Authorization": f"Bearer {token}"},
                    )
                    response.raise_for_status()
                    return response.json().get("results", [])
                elif ontologies:
                    # Global query with symlinks - search specific ontologies
                    all_results = []
                    for ont in ontologies:
                        body["ontology"] = ont
                        response = await client.post(
                            "/query/search",
                            json=body,
                            headers={"Authorization": f"Bearer {token}"},
                        )
                        response.raise_for_status()
                        all_results.extend(response.json().get("results", []))
                    return all_results
                else:
                    # Global query without symlinks - search all
                    response = await client.post(
                        "/query/search",
                        json=body,
                        headers={"Authorization": f"Bearer {token}"},
                    )
                    response.raise_for_status()
                    return response.json().get("results", [])

            # Step 1: Get base results from query terms (AND intersection)
            concept_data = {}  # concept_id -> full result dict

            if len(query_terms) == 1:
                # Single term: simple search
                results = await search_single_term(query_terms[0], symlinked_ontologies)
                for r in results:
                    cid = r.get("concept_id")
                    if cid not in concept_data or r.get("similarity", 0) > concept_data[cid].get("similarity", 0):
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
                        if cid not in concept_data or r.get("similarity", 0) > concept_data[cid].get("similarity", 0):
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
                        if cid not in concept_data or r.get("similarity", 0) > concept_data[cid].get("similarity", 0):
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
            matched.sort(key=lambda x: x.get("similarity", 0), reverse=True)
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

        inode = self._next_inode
        self._next_inode += 1
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

        inode = self._next_inode
        self._next_inode += 1
        self._inodes[inode] = InodeEntry(
            name="documents",
            entry_type="documents_dir",
            parent=parent,
            ontology=ontology,
        )
        return inode

    def _get_or_create_document_inode(self, name: str, parent: int, ontology: str, document_id: str) -> int:
        """Get or create inode for a document file."""
        for inode, entry in self._inodes.items():
            if entry.entry_type == "document" and entry.name == name and entry.parent == parent:
                return inode

        inode = self._next_inode
        self._next_inode += 1
        self._inodes[inode] = InodeEntry(
            name=name,
            entry_type="document",
            parent=parent,
            ontology=ontology,
            document_id=document_id,
            size=4096,  # Placeholder size
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

        inode = self._next_inode
        self._next_inode += 1
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

        inode = self._next_inode
        self._next_inode += 1
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

        inode = self._next_inode
        self._next_inode += 1
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

        inode = self._next_inode
        self._next_inode += 1
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
        if not query:
            return "# Query not found\n"

        if entry.meta_key == "limit":
            return f"# Maximum number of concepts to return. Default is 50.\n{query.limit}\n"

        elif entry.meta_key == "threshold":
            return f"# Minimum similarity score (0.0-1.0). Default is 0.7.\n{query.threshold}\n"

        elif entry.meta_key == "exclude":
            content = "# Terms to exclude from results (one per line, semantic NOT).\n"
            for term in query.exclude:
                content += f"{term}\n"
            return content

        elif entry.meta_key == "union":
            content = "# Additional terms to include (one per line, semantic OR).\n"
            for term in query.union:
                content += f"{term}\n"
            return content

        elif entry.meta_key == "query.toml":
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
            if entry.ontology:
                lines.append(f'ontology = "{entry.ontology}"')
            else:
                lines.append("ontology = null  # Global query")
            return "\n".join(lines) + "\n"

        return "# Unknown meta file\n"

    def _invalidate_cache(self, inode: int):
        """Invalidate cache for an inode."""
        self._dir_cache.pop(inode, None)
        self._cache_time.pop(inode, None)

    async def open(self, inode: int, flags: int, ctx: pyfuse3.RequestContext) -> pyfuse3.FileInfo:
        """Open a file."""
        if inode not in self._inodes:
            raise pyfuse3.FUSEError(errno.ENOENT)

        entry = self._inodes[inode]
        if entry.entry_type not in ("document", "concept", "meta_file", "ingestion_file"):
            raise pyfuse3.FUSEError(errno.EISDIR)

        # Check write permissions for meta files
        if entry.entry_type == "meta_file":
            # query.toml is read-only
            if entry.meta_key == "query.toml" and (flags & os.O_WRONLY or flags & os.O_RDWR):
                raise pyfuse3.FUSEError(errno.EACCES)

        return pyfuse3.FileInfo(fh=inode)

    async def read(self, fh: int, off: int, size: int) -> bytes:
        """Read file contents."""
        entry = self._inodes.get(fh)
        if not entry:
            raise pyfuse3.FUSEError(errno.ENOENT)

        try:
            if entry.entry_type == "document":
                content = await self._read_document(entry)
            elif entry.entry_type == "concept":
                content = await self._read_concept(entry)
            elif entry.entry_type == "meta_file":
                content = self._render_meta_file(entry)
            else:
                content = "# Unknown file type\n"

            content_bytes = content.encode("utf-8")
            return content_bytes[off:off + size]

        except Exception as e:
            log.error(f"Failed to read file: {e}")
            return f"# Error reading file: {e}\n".encode("utf-8")

    async def _read_document(self, entry: InodeEntry) -> str:
        """Read and format a document file."""
        if not entry.document_id:
            return "# No document ID\n"

        data = await self._api_get(f"/documents/{entry.document_id}/content")

        # Fetch concepts if tags are enabled
        concepts = []
        if self.tags_config.enabled:
            try:
                concepts_data = await self._api_get(f"/documents/{entry.document_id}/concepts")
                concepts = concepts_data.get("concepts", [])
            except Exception as e:
                log.debug(f"Could not fetch concepts for document: {e}")

        return self._format_document(data, concepts)

    async def _read_concept(self, entry: InodeEntry) -> str:
        """Read and format a concept file."""
        if not entry.concept_id:
            return "# No concept ID\n"

        data = await self._api_get(f"/query/concept/{entry.concept_id}")
        return self._format_concept(data)

    def _format_document(self, data: dict, concepts: list = None) -> str:
        """Format document data as markdown with optional YAML frontmatter."""
        concepts = concepts or []
        lines = []

        # Add YAML frontmatter if tags are enabled and we have concepts
        if self.tags_config.enabled and concepts:
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

    def _format_concept(self, data: dict) -> str:
        """Format concept data as markdown with YAML frontmatter."""
        lines = []

        # YAML frontmatter
        lines.append("---")
        lines.append(f"id: {data.get('concept_id', 'unknown')}")
        lines.append(f"label: {data.get('label', 'Unknown')}")

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
                lines.append(f"    target: {target_label}")
                lines.append(f"    target_id: {target_id}")

        # Tags for tool integration (Obsidian, Logseq, etc.)
        if self.tags_config.enabled:
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
        instances = data.get("instances", [])
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
                lines.append(f"> {text[:500]}{'...' if len(text) > 500 else ''}\n")
                lines.append("")

        # Relationships as readable list
        if relationships:
            lines.append("## Relationships\n")
            for rel in relationships:
                rel_type = rel.get("rel_type", "RELATED_TO")
                target = rel.get("to_label", rel.get("to_id", "unknown"))
                lines.append(f"- **{rel_type}** → {target}")
            lines.append("")

        return "\n".join(lines)

    async def write(self, fh: int, off: int, buf: bytes) -> int:
        """Write to a file (meta files and ingestion files are writable)."""
        entry = self._inodes.get(fh)
        if not entry:
            raise pyfuse3.FUSEError(errno.ENOENT)

        # Handle ingestion file writes - buffer content
        if entry.entry_type == "ingestion_file":
            if fh not in self._write_buffers:
                self._write_buffers[fh] = b""
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
        inode = self._next_inode
        self._next_inode += 1
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
        - /mnt/kg/ontology/OntologyName (absolute)
        """
        import re
        # Relative: ../ontology/Name or ../../ontology/Name
        match = re.match(r'^(?:\.\./)+ontology/(.+)$', target)
        if match:
            return match.group(1)
        # Could add absolute path support if needed
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

        # Remove inode
        del self._inodes[target_inode]

        # Invalidate parent cache
        self._invalidate_cache(parent_inode)

    def _get_or_create_symlink_inode(self, name: str, ontology: str, query_path: str, target: str, parent: int) -> int:
        """Get or create inode for a symlink."""
        for inode, entry in self._inodes.items():
            if (entry.entry_type == "symlink" and
                entry.name == name and
                entry.parent == parent):
                return inode

        inode = self._next_inode
        self._next_inode += 1
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
        inode = self._next_inode
        self._next_inode += 1
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
                    await self._ingest_document(ontology, filename, content)
                    log.info(f"Ingestion submitted successfully: {filename}")

                    # Remove from pending ontologies if this was the first document
                    if ontology in self._pending_ontologies:
                        self._pending_ontologies.discard(ontology)
                        log.info(f"Ontology {ontology} is no longer pending")

                except Exception as e:
                    log.error(f"Ingestion failed for {filename}: {e}")

            # Clean up the temporary inode (file disappears after ingestion)
            if fh in self._inodes:
                parent_inode = self._inodes[fh].parent
                del self._inodes[fh]
                # Invalidate parent cache so new documents show up
                if parent_inode:
                    self._invalidate_cache(parent_inode)

    async def _ingest_document(self, ontology: str, filename: str, content: bytes) -> dict:
        """Submit document to ingestion API."""
        token = await self._get_token()
        client = await self._get_client()

        # Use multipart form upload
        files = {"file": (filename, content)}
        data = {
            "ontology": ontology,
            "auto_approve": "true",  # Auto-approve for FUSE ingestions
        }

        response = await client.post(
            "/ingest",
            files=files,
            data=data,
            headers={"Authorization": f"Bearer {token}"},
        )
        response.raise_for_status()
        result = response.json()
        log.info(f"Ingestion response: {result}")
        return result
