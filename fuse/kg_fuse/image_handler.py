"""Image handling for the FUSE filesystem.

Encapsulates image-specific operations: reading image bytes and prose,
managing the immutable image cache, listing query image evidence,
creating image-related inodes, and routing image ingestion.
"""

import base64
import logging
import os
from typing import Callable, Optional

from .api_client import KnowledgeGraphClient
from .config import TagsConfig
from .formatters import format_image_prose
from .job_tracker import JobTracker
from .models import InodeEntry

log = logging.getLogger(__name__)


class ImageHandler:
    """Handles image-specific operations for the FUSE filesystem.

    Owns the immutable image cache (100MB budget, no eviction needed
    since images are content-addressed). Delegates inode allocation
    back to the filesystem via the provided callable.
    """

    def __init__(
        self,
        api: KnowledgeGraphClient,
        tags_config: TagsConfig,
        job_tracker: JobTracker,
        inodes: dict[int, InodeEntry],
        allocate_inode: Callable[[], int],
        sanitize_filename: Callable[[str], str],
    ):
        self._api = api
        self._tags_config = tags_config
        self._job_tracker = job_tracker
        self._inodes = inodes  # Shared reference with filesystem
        self._allocate_inode = allocate_inode
        self._sanitize_filename = sanitize_filename

        # Immutable image cache (content-addressed = no staleness bugs)
        self._cache: dict[str, bytes] = {}
        self._cache_total = 0
        self._cache_max = 100 * 1024 * 1024  # 100MB budget

    # ── Inode allocators ─────────────────────────────────────────────

    def get_or_create_image_document_inode(self, name: str, parent: int, ontology: str, document_id: str) -> int:
        """Get or create inode for an image document file (raw bytes)."""
        for inode, entry in self._inodes.items():
            if entry.entry_type == "image_document" and entry.name == name and entry.parent == parent:
                return inode

        inode = self._allocate_inode()
        self._inodes[inode] = InodeEntry(
            name=name,
            entry_type="image_document",
            parent=parent,
            ontology=ontology,
            document_id=document_id,
            content_type="image",
            size=4096,  # Placeholder; updated to actual size on first read
        )
        return inode

    def get_or_create_image_prose_inode(self, name: str, parent: int, ontology: str, document_id: str) -> int:
        """Get or create inode for an image companion markdown file."""
        for inode, entry in self._inodes.items():
            if entry.entry_type == "image_prose" and entry.name == name and entry.parent == parent:
                return inode

        inode = self._allocate_inode()
        self._inodes[inode] = InodeEntry(
            name=name,
            entry_type="image_prose",
            parent=parent,
            ontology=ontology,
            document_id=document_id,
            content_type="image",
            size=4096,  # Placeholder
        )
        return inode

    def get_or_create_images_dir_inode(self, ontology: Optional[str], query_path: str, parent: int) -> int:
        """Get or create inode for the images/ directory inside a query."""
        for inode, entry in self._inodes.items():
            if (entry.entry_type == "images_dir" and
                entry.ontology == ontology and
                entry.query_path == query_path):
                return inode

        inode = self._allocate_inode()
        self._inodes[inode] = InodeEntry(
            name="images",
            entry_type="images_dir",
            parent=parent,
            ontology=ontology,
            query_path=query_path,
        )
        return inode

    def get_or_create_image_evidence_inode(self, name: str, parent: int, ontology: Optional[str], query_path: str, source_id: str) -> int:
        """Get or create inode for an image evidence file in query images/ dir."""
        for inode, entry in self._inodes.items():
            if (entry.entry_type == "image_evidence" and
                entry.name == name and
                entry.parent == parent):
                return inode

        inode = self._allocate_inode()
        self._inodes[inode] = InodeEntry(
            name=name,
            entry_type="image_evidence",
            parent=parent,
            ontology=ontology,
            query_path=query_path,
            source_id=source_id,
            content_type="image",
            size=4096,  # Placeholder; updated to actual size on first read
        )
        return inode

    # ── Read handlers ────────────────────────────────────────────────

    async def read_image_bytes(self, entry: InodeEntry) -> bytes:
        """Read raw image bytes from Garage via API."""
        if not entry.document_id:
            return b""

        cache_key = f"doc:{entry.document_id}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        data = await self._api.get(f"/documents/{entry.document_id}/content")
        content = data.get("content", {})

        if content.get("image"):
            image_bytes = base64.b64decode(content["image"])
            entry.size = len(image_bytes)
            self._cache_image(cache_key, image_bytes)
            return image_bytes

        return b""

    async def read_image_prose(self, entry: InodeEntry) -> str:
        """Read image companion markdown with frontmatter + prose."""
        if not entry.document_id:
            return "# No document ID\n"

        data = await self._api.get(f"/documents/{entry.document_id}/content")

        # Extract the original image filename from the .md name
        image_filename = entry.name[:-3]  # strip ".md" suffix

        return format_image_prose(data, image_filename, self._tags_config)

    async def read_image_evidence(self, entry: InodeEntry) -> bytes:
        """Read raw image bytes for query image evidence."""
        source_id = entry.source_id
        if not source_id:
            return b""

        cache_key = f"evidence:{source_id}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        image_bytes = await self._api.get_bytes(f"/sources/{source_id}/image")
        entry.size = len(image_bytes)
        self._cache_image(cache_key, image_bytes)
        return image_bytes

    # ── Cache management ─────────────────────────────────────────────

    def _cache_image(self, key: str, data: bytes) -> None:
        """Cache image bytes if within budget."""
        if self._cache_total + len(data) < self._cache_max:
            self._cache[key] = data
            self._cache_total += len(data)
        else:
            log.debug(
                f"Image cache budget full ({self._cache_total}/{self._cache_max} bytes), "
                f"not caching {key} ({len(data)} bytes)"
            )

    def clear_cache(self) -> None:
        """Clear the image cache (called on filesystem destroy)."""
        self._cache.clear()
        self._cache_total = 0

    # ── Query image evidence listing ─────────────────────────────────

    async def list_query_images(
        self,
        parent_inode: int,
        ontology: Optional[str],
        query_path: str,
        cache=None,
    ) -> list[tuple[int, str]]:
        """List image evidence files for query results.

        Fetches concept details for each concept in the parent query to find
        instances with image evidence. Deduplicates by source_id.
        """
        # Check cache (epoch-gated via EpochCache)
        if cache is not None:
            cached = cache.get_dir(parent_inode)
            if cached is not None:
                return cached

        entries = []
        seen_sources: set[str] = set()
        used_names: set[str] = set()

        # Find concept inodes under the parent query directory
        parent_entry = self._inodes.get(parent_inode)
        if not parent_entry:
            return entries

        query_parent_inode = parent_entry.parent
        concept_entries = [
            entry for entry in self._inodes.values()
            if entry.parent == query_parent_inode and entry.entry_type == "concept"
        ]

        for concept_entry in concept_entries:
            if not concept_entry.concept_id:
                continue

            try:
                data = await self._api.get(f"/query/concept/{concept_entry.concept_id}")
                instances = data.get("instances", [])

                for inst in instances:
                    if inst.get("has_image") and inst.get("source_id"):
                        source_id = inst["source_id"]
                        if source_id in seen_sources:
                            continue
                        seen_sources.add(source_id)

                        filename = inst.get("filename") or f"{source_id}.jpg"
                        safe_name = self._sanitize_filename(filename)

                        # Handle filename collisions
                        if safe_name in used_names:
                            base, ext = os.path.splitext(safe_name)
                            counter = 1
                            while f"{base}-{counter}{ext}" in used_names:
                                counter += 1
                            safe_name = f"{base}-{counter}{ext}"
                        used_names.add(safe_name)

                        inode = self.get_or_create_image_evidence_inode(
                            safe_name, parent_inode, ontology, query_path, source_id
                        )
                        entries.append((inode, safe_name))
            except Exception as e:
                log.error(f"Failed to fetch concept details for image evidence: {e}")

        if cache is not None:
            cache.put_dir(parent_inode, entries)

        return entries

    # ── Ingestion ────────────────────────────────────────────────────

    async def ingest_image(self, ontology: str, filename: str, content: bytes) -> dict:
        """Submit image to dedicated image ingestion API (ADR-057) and track the job."""
        files = {"file": (filename, content)}
        data = {
            "ontology": ontology,
            "auto_approve": "true",
            "source_type": "file",
        }

        result = await self._api.post("/ingest/image", data=data, files=files)
        log.info(f"Image ingestion response: {result}")

        job_id = result.get("job_id")
        if job_id:
            self._job_tracker.track_job(job_id, ontology, filename)

        return result
