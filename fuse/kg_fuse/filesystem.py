"""
Knowledge Graph FUSE Filesystem Operations

Hierarchy:
- /ontology/                     - Fixed root
- /ontology/{name}/              - Ontology directories (from graph)
- /ontology/{name}/{doc}.md      - Documents (from graph)
- /ontology/{name}/{query}/      - User-created query directories
- /ontology/{name}/{query}/*.concept.md  - Concept search results
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
    """Metadata for an inode."""
    name: str
    entry_type: str  # "root", "ontology", "document", "query", "concept"
    parent: Optional[int]
    ontology: Optional[str] = None  # Which ontology this belongs to
    query_path: Optional[str] = None  # For query dirs: path under ontology
    document_id: Optional[str] = None  # For documents
    concept_id: Optional[str] = None  # For concepts
    size: int = 0


class KnowledgeGraphFS(pyfuse3.Operations):
    """FUSE filesystem backed by Knowledge Graph API."""

    ROOT_INODE = pyfuse3.ROOT_INODE  # 1

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

        # Inode management
        self._inodes: dict[int, InodeEntry] = {
            self.ROOT_INODE: InodeEntry(name="", entry_type="root", parent=None),
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
        return entry_type in ("root", "ontology", "query")

    async def getattr(self, inode: int, ctx: pyfuse3.RequestContext) -> pyfuse3.EntryAttributes:
        """Get file/directory attributes."""
        if inode not in self._inodes:
            raise pyfuse3.FUSEError(errno.ENOENT)

        entry = self._inodes[inode]
        is_dir = self._is_dir_type(entry.entry_type)
        size = entry.size

        # Ontology and query directories are writable (for mkdir)
        writable = entry.entry_type in ("ontology", "query")

        return self._make_attr(inode, is_dir=is_dir, size=size, writable=writable)

    async def lookup(self, parent_inode: int, name: bytes, ctx: pyfuse3.RequestContext) -> pyfuse3.EntryAttributes:
        """Look up a directory entry by name."""
        name_str = name.decode("utf-8")
        log.debug(f"lookup: parent={parent_inode}, name={name_str}")

        # Check existing inodes
        for inode, entry in self._inodes.items():
            if entry.parent == parent_inode and entry.name == name_str:
                return await self.getattr(inode, ctx)

        parent_entry = self._inodes.get(parent_inode)
        if not parent_entry:
            raise pyfuse3.FUSEError(errno.ENOENT)

        # Handle lookup at root level - check if it's an ontology
        if parent_entry.entry_type == "root":
            # Fetch ontologies if not cached and check if name is one
            entries = await self._list_ontologies()
            for inode, ont_name in entries:
                if ont_name == name_str:
                    return await self.getattr(inode, ctx)

        # Handle lookup under ontology
        elif parent_entry.entry_type == "ontology":
            ontology = parent_entry.ontology

            # Check if it's a query directory
            if self.query_store.is_query_dir(ontology, name_str):
                inode = self._get_or_create_query_inode(ontology, name_str, parent_inode)
                return await self.getattr(inode, ctx)

            # Check if it's a document (fetch from API if needed)
            entries = await self._list_ontology_contents(parent_inode, ontology)
            for inode, doc_name in entries:
                if doc_name == name_str:
                    return await self.getattr(inode, ctx)

        # Handle lookup under query directory
        elif parent_entry.entry_type == "query":
            ontology = parent_entry.ontology
            parent_path = parent_entry.query_path
            nested_path = f"{parent_path}/{name_str}"

            # Check if it's a nested query directory
            if self.query_store.is_query_dir(ontology, nested_path):
                inode = self._get_or_create_query_inode(ontology, nested_path, parent_inode)
                return await self.getattr(inode, ctx)

            # Check if it's a concept file (fetch results if needed)
            entries = await self._list_query_results(parent_inode, ontology, parent_path)
            for inode, file_name in entries:
                if file_name == name_str:
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

        # Can only mkdir under ontology or query directories
        if parent_entry.entry_type == "ontology":
            ontology = parent_entry.ontology
            query_path = name_str
        elif parent_entry.entry_type == "query":
            ontology = parent_entry.ontology
            query_path = f"{parent_entry.query_path}/{name_str}"
        else:
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

        # Determine the query path
        if parent_entry.entry_type == "ontology":
            ontology = parent_entry.ontology
            query_path = name_str
        elif parent_entry.entry_type == "query":
            ontology = parent_entry.ontology
            query_path = f"{parent_entry.query_path}/{name_str}"
        else:
            raise pyfuse3.FUSEError(errno.EPERM)

        # Check it exists
        if not self.query_store.is_query_dir(ontology, query_path):
            raise pyfuse3.FUSEError(errno.ENOENT)

        # Remove from store (also removes children)
        self.query_store.remove_query(ontology, query_path)

        # Remove inode
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
            # Root directory: list ontologies
            entries = await self._list_ontologies()

        elif entry.entry_type == "ontology":
            # Ontology directory: list documents + query dirs
            entries = await self._list_ontology_contents(fh, entry.ontology)

        elif entry.entry_type == "query":
            # Query directory: execute search + list child queries
            entries = await self._list_query_results(fh, entry.ontology, entry.query_path)

        # Emit entries starting from start_id
        for idx, (inode, name) in enumerate(entries):
            if idx < start_id:
                continue
            attr = await self.getattr(inode, None)
            if not pyfuse3.readdir_reply(token, name.encode("utf-8"), attr, idx + 1):
                break

    async def _list_ontologies(self) -> list[tuple[int, str]]:
        """List ontologies as directories at root."""
        # Check cache
        cache_key = self.ROOT_INODE
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
        """List documents and query directories in an ontology."""
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

        # Add user-created query directories
        query_dirs = self.query_store.list_queries_under(ontology, "")
        for query_name in query_dirs:
            inode = self._get_or_create_query_inode(ontology, query_name, parent_inode)
            entries.append((inode, query_name))

        # Cache result
        self._dir_cache[parent_inode] = entries
        self._cache_time[parent_inode] = time.time()

        return entries

    async def _list_query_results(self, parent_inode: int, ontology: str, query_path: str) -> list[tuple[int, str]]:
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

    async def _execute_search(self, ontology: str, query_text: str, threshold: float) -> list[dict]:
        """Execute semantic search via API."""
        try:
            token = await self._get_token()
            client = await self._get_client()

            response = await client.post(
                "/query/search",
                json={
                    "query": query_text,
                    "ontology": ontology,
                    "min_similarity": threshold,
                    "limit": 50,
                },
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
            parent=self.ROOT_INODE,
            ontology=name,
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

    def _get_or_create_concept_inode(self, name: str, parent: int, ontology: str, query_path: str, concept_id: str) -> int:
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

    def _invalidate_cache(self, inode: int):
        """Invalidate cache for an inode."""
        self._dir_cache.pop(inode, None)
        self._cache_time.pop(inode, None)

    async def open(self, inode: int, flags: int, ctx: pyfuse3.RequestContext) -> pyfuse3.FileInfo:
        """Open a file."""
        if inode not in self._inodes:
            raise pyfuse3.FUSEError(errno.ENOENT)

        entry = self._inodes[inode]
        if entry.entry_type not in ("document", "concept"):
            raise pyfuse3.FUSEError(errno.EISDIR)

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

        # Source documents (actual document names from evidence)
        instances = data.get("instances", [])
        source_docs = sorted(set(
            inst.get("document", "")
            for inst in instances
            if inst.get("document")
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
                para = inst.get("paragraph_number", "?")
                doc = inst.get("document", "")
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
