"""
BaseMixin — Lifecycle, configuration, and core FUSE plumbing.

Handles init, destroy, nursery setup, config hot-reload, access checks,
statfs, extended attributes, and shared attribute helpers.
"""

import errno
import logging
import os
import stat
import time
from typing import Optional

import pyfuse3

from ..api_client import KnowledgeGraphClient
from ..config import (
    TagsConfig, JobsConfig, CacheConfig, WriteProtectConfig,
    get_fuse_config_path, read_fuse_config,
)
from ..epoch_cache import EpochCache
from ..image_handler import ImageHandler
from ..job_tracker import JobTracker
from ..models import InodeEntry, is_dir_type
from ..query_store import QueryStore

log = logging.getLogger(__name__)


class BaseMixin(pyfuse3.Operations):
    """Lifecycle, configuration, and core FUSE plumbing."""

    ROOT_INODE = pyfuse3.ROOT_INODE  # 1
    ONTOLOGY_ROOT_INODE = 2  # Fixed inode for /ontology/

    # The virtual files available in .meta directories
    META_FILES = ["limit", "threshold", "exclude", "union", "query.toml"]

    # Extended attributes
    _XATTR_PREFIX = b"user.kg."
    _KNOWN_XATTRS = (b"user.kg.state", b"user.kg.epoch")

    def __init__(self, api_url: str, client_id: str, client_secret: str,
                 tags_config: TagsConfig = None, jobs_config: JobsConfig = None,
                 cache_config: CacheConfig = None,
                 write_protect_config: WriteProtectConfig = None,
                 query_store: QueryStore = None,
                 mountpoint: str = None):
        super().__init__()
        self.tags_config = tags_config or TagsConfig()
        self.jobs_config = jobs_config or JobsConfig()
        self.cache_config = cache_config or CacheConfig()
        self.write_protect = write_protect_config or WriteProtectConfig()
        self._mountpoint = mountpoint  # For config reload (which mount section to read)
        self._config_mtime: float = 0  # Last known mtime of fuse.json

        # API client for graph operations
        self._api = KnowledgeGraphClient(api_url, client_id, client_secret)

        # Query store for user-created directories (caller can inject per-mount store)
        self.query_store = query_store or QueryStore()

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

        # Write-back queue: released files waiting for ingestion.
        # Key: "ontology/filename", Value: dict with ontology, filename, content, timestamp.
        # Editors do create→write→release→rename; the delay lets that settle so we
        # ingest with the final filename, not an intermediate temp name.
        self._pending_ingestions: dict[str, dict] = {}

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
            # Files: writable=True used for deletable docs and writable meta files.
            # With default_permissions, FUSE kernel checks file mode for unlink.
            attr.st_mode = stat.S_IFREG | (0o644 if writable else 0o444)

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

    async def statfs(self, ctx: pyfuse3.RequestContext) -> pyfuse3.StatvfsData:
        """Return filesystem stats. Required for file managers like Dolphin.

        Reports generous free space so file managers don't gray out paste/write
        operations. Actual write gating is done by our create/write handlers.
        """
        s = pyfuse3.StatvfsData()
        s.f_bsize = 4096
        s.f_frsize = 4096
        s.f_blocks = 1024 * 1024  # 4 GB virtual
        s.f_bfree = 1024 * 1024
        s.f_bavail = 1024 * 1024
        s.f_files = len(self._inodes)
        s.f_ffree = 1024 * 1024
        s.f_favail = 1024 * 1024
        s.f_namemax = 255
        return s

    async def access(self, inode: int, mode: int, ctx: pyfuse3.RequestContext) -> bool:
        """Permission check — always allow, we enforce in each handler.

        Without default_permissions, the kernel calls this for every access
        check. Our handlers (unlink, create, write, etc.) do their own
        permission gating via write_protect config and entry type checks.
        """
        return True

    async def flush(self, fh: int) -> None:
        """Flush file data. No-op — write-back is handled in release()."""
        pass

    def set_nursery(self, nursery):
        """Set the trio nursery for background tasks. Called by main.py."""
        self._cache.set_nursery(nursery)
        nursery.start_soon(self._flush_pending_ingestions)
        if self._mountpoint:
            nursery.start_soon(self._watch_config)

    async def _watch_config(self):
        """Poll fuse.json for changes and hot-reload mutable settings.

        Reads are flock-protected (LOCK_SH) so we never see a half-written
        file — write_fuse_config holds LOCK_EX through atomic rename.
        """
        import trio
        config_path = get_fuse_config_path()

        # Seed mtime
        try:
            self._config_mtime = config_path.stat().st_mtime
        except OSError:
            pass

        while True:
            await trio.sleep(5)
            try:
                mtime = config_path.stat().st_mtime
                if mtime == self._config_mtime:
                    continue
                self._config_mtime = mtime
                self._reload_config()
            except OSError:
                pass

    def _reload_config(self):
        """Re-read fuse.json and update mutable settings for this mount."""
        fuse_data = read_fuse_config()
        if not fuse_data:
            return
        mount_data = fuse_data.get("mounts", {}).get(self._mountpoint)
        if not mount_data:
            return

        # Write protection
        wp = mount_data.get("write_protect", {})
        new_wp = WriteProtectConfig(
            allow_ontology_delete=wp.get("allow_ontology_delete", False),
            allow_document_delete=wp.get("allow_document_delete", False),
        )
        if (new_wp.allow_ontology_delete != self.write_protect.allow_ontology_delete or
                new_wp.allow_document_delete != self.write_protect.allow_document_delete):
            log.info(f"Config reload: write_protect changed → "
                     f"ontology_delete={'allowed' if new_wp.allow_ontology_delete else 'blocked'}, "
                     f"document_delete={'allowed' if new_wp.allow_document_delete else 'blocked'}")
            self.write_protect = new_wp

        # Tags
        tags = mount_data.get("tags", {})
        new_tags = TagsConfig(
            enabled=tags.get("enabled", True),
            threshold=tags.get("threshold", 0.5),
        )
        if new_tags.enabled != self.tags_config.enabled or new_tags.threshold != self.tags_config.threshold:
            log.info(f"Config reload: tags changed → enabled={new_tags.enabled}, threshold={new_tags.threshold}")
            self.tags_config = new_tags

        # Jobs
        jobs = mount_data.get("jobs", {})
        new_jobs = JobsConfig(hide_jobs=jobs.get("hide_jobs", False))
        if new_jobs.hide_jobs != self.jobs_config.hide_jobs:
            log.info(f"Config reload: jobs changed → hide_jobs={new_jobs.hide_jobs}")
            self.jobs_config = new_jobs

    # ── Extended attributes (hydration state) ───────────────────────────

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
        """Clean up resources on unmount. Flushes pending ingestions first."""
        log.info("Destroying filesystem, cleaning up resources")

        # Flush any pending write-back entries before shutting down
        if self._pending_ingestions:
            log.info(f"Flushing {len(self._pending_ingestions)} pending ingestion(s) before unmount")
            for key, entry in list(self._pending_ingestions.items()):
                del self._pending_ingestions[key]
                await self._ingest_and_notify(entry)

        await self._api.close()
        self._cache.clear()
        self._write_buffers.clear()
        self._job_tracker.clear()
        self._write_info.clear()
        self._image_handler.clear_cache()
