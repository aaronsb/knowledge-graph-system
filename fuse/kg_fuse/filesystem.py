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

    def __init__(self, api_url: str, client_id: str, client_secret: str):
        super().__init__()
        self.api_url = api_url.rstrip("/")
        self.client_id = client_id
        self.client_secret = client_secret

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

        # Writable directories: root (global queries), ontology (scoped queries), query (nested)
        # Not writable: ontology_root (fixed), documents_dir (read-only), meta_dir (fixed structure)
        writable = entry.entry_type in ("root", "ontology", "query")

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
        elif parent_entry.entry_type == "ontology":
            # Query scoped to this ontology
            ontology = parent_entry.ontology
            query_path = name_str
        elif parent_entry.entry_type == "query":
            # Nested query (inherits ontology scope from parent)
            ontology = parent_entry.ontology  # Can be None for global queries
            query_path = f"{parent_entry.query_path}/{name_str}"
        else:
            # Can't mkdir under ontology_root, documents_dir, etc.
            raise pyfuse3.FUSEError(errno.EPERM)

        # Create query in store
        self.query_store.add_query(ontology, query_path)

        # Create inode for the new directory
        inode = self._get_or_create_query_inode(ontology, query_path, parent_inode)

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
            for ont in ontologies:
                name = ont.get("ontology", "unknown")
                # Allocate inode for this ontology
                inode = self._get_or_create_ontology_inode(name)
                entries.append((inode, name))

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
        """Execute semantic search and list results + child queries."""
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

        # Execute semantic search
        try:
            # For now, use the leaf query text
            # TODO: Implement proper nested query intersection
            leaf_query = queries[-1]
            results = await self._execute_search(ontology, leaf_query.query_text, leaf_query.threshold)

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

        # Cache result
        self._dir_cache[parent_inode] = entries
        self._cache_time[parent_inode] = time.time()

        return entries

    async def _execute_search(self, ontology: Optional[str], query_text: str, threshold: float) -> list[dict]:
        """Execute semantic search via API."""
        try:
            token = await self._get_token()
            client = await self._get_client()

            # Build request body - omit ontology for global queries
            body = {
                "query": query_text,
                "min_similarity": threshold,
                "limit": 50,
            }
            if ontology is not None:
                body["ontology"] = ontology

            response = await client.post(
                "/query/search",
                json=body,
                headers={"Authorization": f"Bearer {token}"},
            )
            response.raise_for_status()
            data = response.json()
            return data.get("results", [])

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
        if entry.entry_type not in ("document", "concept", "meta_file"):
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

        data = await self._api_get(f"/documents/{entry.document_id}")
        return self._format_document(data)

    async def _read_concept(self, entry: InodeEntry) -> str:
        """Read and format a concept file."""
        if not entry.concept_id:
            return "# No concept ID\n"

        data = await self._api_get(f"/query/concept/{entry.concept_id}")
        return self._format_concept(data)

    def _format_document(self, data: dict) -> str:
        """Format document data as markdown."""
        lines = []
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
        """Write to a file (only meta files are writable)."""
        entry = self._inodes.get(fh)
        if not entry:
            raise pyfuse3.FUSEError(errno.ENOENT)

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
