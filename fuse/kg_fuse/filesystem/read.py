"""
ReadMixin — File open and read operations.

Handles open, read with stale-while-revalidate caching,
content fetching dispatch, and all rendering/formatting methods.
"""

import errno
import logging
import os

import pyfuse3

from ..formatters import format_concept, format_document, format_job, render_meta_file
from ..models import InodeEntry

log = logging.getLogger(__name__)


class ReadMixin:
    """File open and read operations."""

    async def open(self, inode: int, flags: int, ctx: pyfuse3.RequestContext) -> pyfuse3.FileInfo:
        """Open a file."""
        if inode not in self._inodes:
            raise pyfuse3.FUSEError(errno.ENOENT)

        entry = self._inodes[inode]
        if entry.entry_type not in ("document", "concept", "meta_file", "ingestion_file", "job_file",
                                     "image_document", "image_prose", "image_evidence", "info_file"):
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

        # Virtual files have unknown size until first read — use direct_io
        # to bypass kernel page cache so reads aren't limited by st_size.
        # Without this, the kernel truncates reads at the placeholder st_size (4096).
        if entry.entry_type in ("document", "concept", "image_document", "image_prose", "image_evidence", "info_file"):
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
        cacheable = entry.entry_type in ("document", "concept", "image_prose", "info_file")

        if cacheable:
            cached = self._cache.get_content(fh)
            if cached is not None:
                entry.size = len(cached)
                if not self._cache.is_content_fresh(fh):
                    # Stale — serve immediately, refresh in background
                    self._cache.spawn_refresh(fh, lambda e=entry: self._fetch_content(e))
                return cached[off:off + size]

        # No cache — block on fetch
        try:
            content_bytes = await self._fetch_content(entry)
            entry.size = len(content_bytes)

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
        elif entry.entry_type == "info_file":
            content = await self._render_info_file(entry)
        else:
            content = "# Unknown file type\n"
        return content.encode("utf-8")

    async def _render_info_file(self, entry: InodeEntry) -> str:
        """Render content for virtual info dotfiles (.ontology, .documents, .ingest)."""
        ontology = entry.ontology
        name = entry.name

        if name == ".ingest":
            return (
                f"# {ontology} — Ingest\n\n"
                "Drop or copy files here to ingest them into the knowledge graph.\n\n"
                "Supported formats: text, markdown, PDF, and images.\n"
                "Files are processed automatically after upload.\n"
            )

        # .ontology and .documents both need API data
        try:
            data = await self._api.get(f"/ontology/{ontology}")
        except Exception as e:
            log.debug(f"Could not fetch ontology info for {name}: {e}")
            return f"# {ontology}\n\nUnable to fetch ontology info.\n"

        if name == ".ontology":
            return self._format_ontology_info(ontology, data)
        elif name == ".documents":
            return self._format_documents_info(ontology, data)

        return f"# {ontology}\n"

    def _format_ontology_info(self, ontology: str, data: dict) -> str:
        """Format .ontology file: statistics overview."""
        lines = [f"# {ontology}\n"]
        stats = data.get("statistics", {})
        if stats:
            for key, value in stats.items():
                label = key.replace("_", " ").title()
                lines.append(f"- {label}: {value}")
            lines.append("")
        node = data.get("node")
        if node and node.get("description"):
            lines.append(f"## Description\n\n{node['description']}\n")
        return "\n".join(lines) + "\n"

    def _format_documents_info(self, ontology: str, data: dict) -> str:
        """Format .documents file: document listing with count."""
        files = data.get("files", [])
        lines = [f"# {ontology} — Documents ({len(files)})\n"]
        if files:
            for f in files:
                lines.append(f"- {f}")
            lines.append("")
        else:
            lines.append("No documents ingested yet.\n")
        return "\n".join(lines) + "\n"

    def _render_meta_file(self, entry: InodeEntry) -> str:
        """Render content for a .meta virtual file."""
        query = self.query_store.get_query(entry.ontology, entry.query_path)
        return render_meta_file(entry.meta_key, query, entry.ontology)

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

        # Update job tracker with status (marks terminal jobs for removal)
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
