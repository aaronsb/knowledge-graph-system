"""
Epoch-gated cache for FUSE filesystem.

Tracks the graph change counter (epoch) and invalidates caches when the
graph changes. Uses stale-while-revalidate: serves cached data immediately
and refreshes in the background via trio nursery.

Cache contract:
  - Epoch unchanged → cache valid, serve immediately
  - Epoch changed → cache stale, serve stale + background refresh
  - No cache → block on first fetch (unavoidable)
"""

import logging
import time
from typing import Callable, Awaitable, Optional

import trio

from .api_client import KnowledgeGraphClient
from .config import CacheConfig

log = logging.getLogger(__name__)


class EpochCache:
    """Graph-epoch-aware cache with stale-while-revalidate semantics."""

    def __init__(self, api: KnowledgeGraphClient, config: CacheConfig = None):
        config = config or CacheConfig()

        self._api = api
        self._epoch_check_interval: float = config.epoch_check_interval

        # Graph epoch tracking
        self._graph_epoch: int = -1           # Last known epoch (-1 = unknown)
        self._epoch_check_time: float = 0.0   # When we last polled

        # Directory listing cache
        self._dir_cache: dict[int, list[tuple[int, str]]] = {}
        self._dir_cache_time: dict[int, float] = {}
        self._dir_cache_ttl: float = config.dir_cache_ttl

        # Content cache (rendered file bytes, epoch-gated)
        self._content: dict[int, bytes] = {}
        self._content_total: int = 0
        self._content_max: int = config.content_cache_max

        # Background refresh tracking
        self._refreshing: set[int] = set()
        self._nursery: trio.Nursery | None = None

    @property
    def graph_epoch(self) -> int:
        return self._graph_epoch

    def set_nursery(self, nursery: trio.Nursery):
        """Set trio nursery for background tasks. Starts periodic sweep."""
        self._nursery = nursery
        nursery.start_soon(self._periodic_epoch_sweep)
        log.info("Epoch cache: background sweep started")

    # ── Epoch checking ───────────────────────────────────────────────────

    async def check_epoch(self) -> bool:
        """Check if graph epoch changed. Throttled to one API call per interval.

        Returns True if epoch changed (caches were invalidated).
        """
        now = time.time()
        if now - self._epoch_check_time < self._epoch_check_interval:
            return False

        self._epoch_check_time = now
        new_epoch = await self._api.get_epoch()

        if new_epoch == self._graph_epoch:
            return False

        old_epoch = self._graph_epoch
        self._graph_epoch = new_epoch

        if old_epoch == -1:
            log.info(f"Epoch cache: initial epoch {new_epoch}")
            return False

        log.info(f"Epoch cache: {old_epoch} -> {new_epoch}, invalidating all caches")
        self.invalidate_all()
        return True

    async def _periodic_epoch_sweep(self):
        """Check epoch every 60s regardless of file access.

        Prevents long-lived stale caches when nobody is reading files
        but the graph is changing (garbage collection).
        """
        while True:
            await trio.sleep(60)
            try:
                await self.check_epoch()
            except Exception as e:
                log.debug(f"Epoch sweep error: {e}")

    # ── Directory listing cache ──────────────────────────────────────────

    def get_dir(self, inode: int) -> Optional[list[tuple[int, str]]]:
        """Get cached directory listing, or None if stale/missing."""
        if inode not in self._dir_cache:
            return None
        # TTL as fallback safety net (primary invalidation is epoch-driven)
        age = time.time() - self._dir_cache_time.get(inode, 0)
        if age > self._dir_cache_ttl:
            return None
        return self._dir_cache[inode]

    def put_dir(self, inode: int, entries: list[tuple[int, str]]):
        """Cache a directory listing."""
        self._dir_cache[inode] = entries
        self._dir_cache_time[inode] = time.time()

    def invalidate_dir(self, inode: int):
        """Invalidate a single directory's cache."""
        self._dir_cache.pop(inode, None)
        self._dir_cache_time.pop(inode, None)

    # ── Content cache ────────────────────────────────────────────────────

    def get_content(self, inode: int) -> Optional[bytes]:
        """Get cached file content, or None if not cached."""
        return self._content.get(inode)

    def put_content(self, inode: int, data: bytes):
        """Cache file content with LRU eviction on budget overflow."""
        # Evict oldest entries if needed
        while self._content and self._content_total + len(data) > self._content_max:
            evict_inode = next(iter(self._content))
            evicted = self._content.pop(evict_inode)
            self._content_total -= len(evicted)

        self._content[inode] = data
        self._content_total += len(data)

    def invalidate_content(self, inode: int):
        """Invalidate a single file's cached content."""
        evicted = self._content.pop(inode, None)
        if evicted:
            self._content_total -= len(evicted)

    # ── Hydration state ──────────────────────────────────────────────────

    def is_refreshing(self, inode: int) -> bool:
        return inode in self._refreshing

    def hydration_state(self, inode: int) -> str:
        """Get hydration state for xattr reporting."""
        if inode in self._refreshing:
            return "refreshing"
        if inode in self._content or inode in self._dir_cache:
            return "fresh"
        return "pending"

    # ── Background refresh ───────────────────────────────────────────────

    def spawn_refresh(self, inode: int, fetch_fn: Callable[[], Awaitable[bytes]]):
        """Spawn a background content refresh if not already running.

        Args:
            inode: The inode to refresh
            fetch_fn: Async callable that returns the new content bytes
        """
        if self._nursery is None or inode in self._refreshing:
            return
        self._refreshing.add(inode)
        self._nursery.start_soon(self._do_refresh, inode, fetch_fn)

    async def _do_refresh(self, inode: int, fetch_fn: Callable[[], Awaitable[bytes]]):
        """Background task: fetch fresh content and update cache."""
        try:
            data = await fetch_fn()
            self.put_content(inode, data)
            log.debug(f"Background refresh complete: inode {inode} ({len(data)} bytes)")
            # Notify kernel to re-fetch
            try:
                pyfuse3.invalidate_inode(inode, attr_only=False)
            except Exception:
                pass  # Non-critical
        except Exception as e:
            log.warning(f"Background refresh failed for inode {inode}: {e}")
        finally:
            self._refreshing.discard(inode)

    def spawn_dir_refresh(self, inode: int, fetch_fn: Callable[[], Awaitable[list[tuple[int, str]]]]):
        """Spawn a background directory listing refresh."""
        if self._nursery is None or inode in self._refreshing:
            return
        self._refreshing.add(inode)
        self._nursery.start_soon(self._do_dir_refresh, inode, fetch_fn)

    async def _do_dir_refresh(self, inode: int, fetch_fn: Callable[[], Awaitable[list[tuple[int, str]]]]):
        """Background task: fetch fresh directory listing."""
        try:
            entries = await fetch_fn()
            self.put_dir(inode, entries)
            log.debug(f"Background dir refresh complete: inode {inode} ({len(entries)} entries)")
            try:
                pyfuse3.invalidate_inode(inode, attr_only=False)
            except Exception:
                pass
        except Exception as e:
            log.warning(f"Background dir refresh failed for inode {inode}: {e}")
        finally:
            self._refreshing.discard(inode)

    # ── Bulk operations ──────────────────────────────────────────────────

    def invalidate_all(self):
        """Invalidate all non-immutable caches (epoch changed)."""
        self._dir_cache.clear()
        self._dir_cache_time.clear()
        self._content.clear()
        self._content_total = 0

    def clear(self):
        """Full cleanup for unmount."""
        self.invalidate_all()
        self._refreshing.clear()
        self._graph_epoch = -1
        self._epoch_check_time = 0.0


# Import here to avoid circular — pyfuse3 is only needed for invalidate_inode
import pyfuse3  # noqa: E402
