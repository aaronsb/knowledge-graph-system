"""
Knowledge Graph FUSE Filesystem Operations

Minimal implementation:
- Root lists ontologies
- Each ontology directory lists its documents
- Documents are readable files
"""

import errno
import logging
import stat
import time
from typing import Optional

import pyfuse3
import httpx

log = logging.getLogger(__name__)


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

        # Inode management
        self._inodes = {
            self.ROOT_INODE: {"name": "", "type": "dir", "parent": None},
        }
        self._next_inode = 100  # Dynamic inodes start here

        # Cache for directory listings
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

    def _make_attr(self, inode: int, is_dir: bool = False, size: int = 0) -> pyfuse3.EntryAttributes:
        """Create file attributes."""
        attr = pyfuse3.EntryAttributes()
        attr.st_ino = inode
        attr.st_mode = (stat.S_IFDIR | 0o755) if is_dir else (stat.S_IFREG | 0o444)
        attr.st_nlink = 2 if is_dir else 1
        attr.st_size = size
        attr.st_atime_ns = int(time.time() * 1e9)
        attr.st_mtime_ns = int(time.time() * 1e9)
        attr.st_ctime_ns = int(time.time() * 1e9)
        attr.st_uid = 0
        attr.st_gid = 0
        return attr

    async def getattr(self, inode: int, ctx: pyfuse3.RequestContext) -> pyfuse3.EntryAttributes:
        """Get file/directory attributes."""
        if inode not in self._inodes:
            raise pyfuse3.FUSEError(errno.ENOENT)

        entry = self._inodes[inode]
        is_dir = entry["type"] == "dir"
        size = entry.get("size", 0)

        return self._make_attr(inode, is_dir=is_dir, size=size)

    async def lookup(self, parent_inode: int, name: bytes, ctx: pyfuse3.RequestContext) -> pyfuse3.EntryAttributes:
        """Look up a directory entry by name."""
        name_str = name.decode("utf-8")
        log.debug(f"lookup: parent={parent_inode}, name={name_str}")

        # Check static entries
        for inode, entry in self._inodes.items():
            if entry.get("parent") == parent_inode and entry.get("name") == name_str:
                return await self.getattr(inode, ctx)

        # Not found
        raise pyfuse3.FUSEError(errno.ENOENT)

    async def opendir(self, inode: int, ctx: pyfuse3.RequestContext) -> int:
        """Open a directory, return file handle."""
        if inode not in self._inodes:
            raise pyfuse3.FUSEError(errno.ENOENT)
        if self._inodes[inode]["type"] != "dir":
            raise pyfuse3.FUSEError(errno.ENOTDIR)

        return inode  # Use inode as file handle

    async def readdir(self, fh: int, start_id: int, token: pyfuse3.ReaddirToken) -> None:
        """Read directory contents."""
        log.debug(f"readdir: fh={fh}, start_id={start_id}")

        entries = []

        if fh == self.ROOT_INODE:
            # Root directory: list ontologies
            entries = await self._list_ontologies()

        else:
            # Ontology directory: list documents
            entries = await self._list_ontology_documents(fh)

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
                inode = self._get_or_create_inode(name, "dir", self.ROOT_INODE)
                entries.append((inode, name))

            # Cache result
            self._dir_cache[cache_key] = entries
            self._cache_time[cache_key] = time.time()

            return entries

        except Exception as e:
            log.error(f"Failed to list ontologies: {e}")
            return []

    async def _list_ontology_documents(self, parent_inode: int) -> list[tuple[int, str]]:
        """List documents in an ontology."""
        # Find ontology name from inode
        entry = self._inodes.get(parent_inode)
        if not entry:
            return []

        ontology_name = entry.get("name")
        if not ontology_name:
            return []

        # Check cache
        cache_key = parent_inode
        if cache_key in self._dir_cache:
            if time.time() - self._cache_time.get(cache_key, 0) < self._cache_ttl:
                return self._dir_cache[cache_key]

        try:
            data = await self._api_get("/documents/", params={"ontology": ontology_name, "limit": 100})
            documents = data.get("documents", [])

            entries = []
            for doc in documents:
                filename = doc.get("filename", doc.get("document_id", "unknown"))
                # Allocate inode for this document
                inode = self._get_or_create_inode(
                    filename, "file", parent_inode,
                    extra={"document_id": doc.get("document_id"), "size": 4096}
                )
                entries.append((inode, filename))

            # Cache result
            self._dir_cache[cache_key] = entries
            self._cache_time[cache_key] = time.time()

            return entries

        except Exception as e:
            log.error(f"Failed to list documents for {ontology_name}: {e}")
            return []

    def _get_or_create_inode(self, name: str, entry_type: str, parent: int, extra: Optional[dict] = None) -> int:
        """Get existing inode or create new one."""
        # Check if already exists
        for inode, entry in self._inodes.items():
            if entry.get("name") == name and entry.get("parent") == parent:
                return inode

        # Create new
        inode = self._next_inode
        self._next_inode += 1
        self._inodes[inode] = {
            "name": name,
            "type": entry_type,
            "parent": parent,
            **(extra or {}),
        }
        return inode

    async def open(self, inode: int, flags: int, ctx: pyfuse3.RequestContext) -> pyfuse3.FileInfo:
        """Open a file."""
        if inode not in self._inodes:
            raise pyfuse3.FUSEError(errno.ENOENT)

        entry = self._inodes[inode]
        if entry["type"] != "file":
            raise pyfuse3.FUSEError(errno.EISDIR)

        return pyfuse3.FileInfo(fh=inode)

    async def read(self, fh: int, off: int, size: int) -> bytes:
        """Read file contents."""
        entry = self._inodes.get(fh)
        if not entry:
            raise pyfuse3.FUSEError(errno.ENOENT)

        document_id = entry.get("document_id")
        if not document_id:
            return b"# No content available\n"

        try:
            data = await self._api_get(f"/documents/{document_id}")

            # Format as simple text
            content = self._format_document(data)
            content_bytes = content.encode("utf-8")

            return content_bytes[off:off + size]

        except Exception as e:
            log.error(f"Failed to read document {document_id}: {e}")
            return f"# Error reading document: {e}\n".encode("utf-8")

    def _format_document(self, data: dict) -> str:
        """Format document data as readable text."""
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
