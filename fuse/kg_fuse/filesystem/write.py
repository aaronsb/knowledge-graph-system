"""
WriteMixin — File creation, writing, and mutation operations.

Handles create, write, release, setattr, rename, unlink, symlink,
readlink, mkdir, and rmdir — everything that modifies the filesystem.
"""

import errno
import logging
import os
import re
import time
from typing import Optional

import pyfuse3

from ..models import InodeEntry
from .ingestion import MAX_INGESTION_SIZE

log = logging.getLogger(__name__)


class WriteMixin:
    """File creation, writing, and mutation operations."""

    async def create(self, parent_inode: int, name: bytes, mode: int, flags: int, ctx: pyfuse3.RequestContext) -> tuple[pyfuse3.FileInfo, pyfuse3.EntryAttributes]:
        """Create a file in the ingest/ drop box for ingestion."""
        name_str = name.decode("utf-8")
        log.info(f"create: parent={parent_inode}, name={name_str}")

        parent_entry = self._inodes.get(parent_inode)
        if not parent_entry:
            raise pyfuse3.FUSEError(errno.ENOENT)

        # Only allow creating files in the ingest/ drop box
        if parent_entry.entry_type != "ingest_dir":
            log.warning(f"create rejected: files can only be created in ingest/ dirs, got {parent_entry.entry_type}")
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

    async def release(self, fh: int) -> None:
        """Release (close) a file — queues non-empty ingestion files for immediate ingestion.

        Content is stashed in _pending_ingestions and flushed on the next
        background tick (~1s). Rename events update the queue key so editor
        save dances still work correctly.
        """
        entry = self._inodes.get(fh)
        if not entry:
            return

        if entry.entry_type == "ingestion_file" and fh in self._write_buffers:
            content = self._write_buffers.pop(fh)
            info = self._write_info.pop(fh, {})

            if content:
                ontology = info.get("ontology", entry.ontology)
                filename = info.get("filename", entry.name)
                key = f"{ontology}/{filename}"

                self._pending_ingestions[key] = {
                    "ontology": ontology,
                    "filename": filename,
                    "content": content,
                    "timestamp": time.monotonic(),
                    "inode": fh,
                }
                log.info(f"Queued for ingestion: {filename} ({len(content)} bytes) → {ontology}")

            if content:
                # Keep the inode alive so rename() and lookup() still work.
                # The inode is cleaned up after write-back flush in _ingest_and_notify().
                pass
            else:
                # Empty file — not queued, clean up the inode immediately
                if fh in self._inodes:
                    parent_inode = self._inodes[fh].parent
                    del self._inodes[fh]
                    self._free_inode(fh)
                    if parent_inode:
                        self._invalidate_cache(parent_inode)

    async def rename(self, parent_inode_old: int, name_old: bytes, parent_inode_new: int, name_new: bytes, flags: int, ctx: pyfuse3.RequestContext) -> None:
        """Rename a file — supports editor save patterns (write-temp-then-rename).

        Handles two cases:
        1. Active inode: file is still open, rename the inode + write_info.
        2. Pending ingestion: file was already released (content in write-back
           queue), update the queue key and reset the delay timer.
        """
        old_name = name_old.decode("utf-8")
        new_name = name_new.decode("utf-8")
        log.info(f"rename: {old_name} -> {new_name} (parent {parent_inode_old} -> {parent_inode_new})")

        # Case 1: active inode (file still open)
        source_inode = None
        source_entry = None
        for inode, entry in self._inodes.items():
            if entry.parent == parent_inode_old and entry.name == old_name:
                source_inode = inode
                source_entry = entry
                break

        if source_entry:
            if source_entry.entry_type != "ingestion_file":
                raise pyfuse3.FUSEError(errno.EPERM)

            if parent_inode_old != parent_inode_new:
                new_parent = self._inodes.get(parent_inode_new)
                if not new_parent or new_parent.entry_type != "ingest_dir":
                    raise pyfuse3.FUSEError(errno.EPERM)
                source_entry.parent = parent_inode_new

            # Remove any existing ingestion_file with the target name
            for inode, entry in list(self._inodes.items()):
                if (entry.parent == parent_inode_new and
                    entry.name == new_name and
                    entry.entry_type == "ingestion_file" and
                    inode != source_inode):
                    self._write_buffers.pop(inode, None)
                    self._write_info.pop(inode, None)
                    del self._inodes[inode]
                    self._free_inode(inode)
                    break

            source_entry.name = new_name
            if source_inode in self._write_info:
                self._write_info[source_inode]["filename"] = new_name

            # Also update the pending ingestion queue if content was already released
            ontology = source_entry.ontology
            if ontology:
                old_key = f"{ontology}/{old_name}"
                if old_key in self._pending_ingestions:
                    pending = self._pending_ingestions.pop(old_key)
                    pending["filename"] = new_name
                    pending["timestamp"] = time.monotonic()
                    new_key = f"{ontology}/{new_name}"
                    self._pending_ingestions[new_key] = pending

            self._invalidate_cache(parent_inode_old)
            if parent_inode_new != parent_inode_old:
                self._invalidate_cache(parent_inode_new)
            return

        # Case 2: file already released — check write-back queue
        old_parent = self._inodes.get(parent_inode_old)
        if old_parent and old_parent.ontology:
            old_key = f"{old_parent.ontology}/{old_name}"
            if old_key in self._pending_ingestions:
                pending = self._pending_ingestions.pop(old_key)
                pending["filename"] = new_name
                pending["timestamp"] = time.monotonic()  # Reset timer

                # Resolve target ontology (may differ if cross-directory rename)
                new_parent = self._inodes.get(parent_inode_new)
                if new_parent and new_parent.ontology:
                    pending["ontology"] = new_parent.ontology

                new_key = f"{pending['ontology']}/{new_name}"
                self._pending_ingestions[new_key] = pending
                log.info(f"Write-back rename: {old_key} → {new_key} (timer reset)")
                return

        raise pyfuse3.FUSEError(errno.ENOENT)

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

        # Document deletion
        if target_entry.entry_type in ("document", "image_document"):
            if not self.write_protect.allow_document_delete:
                log.warning(f"unlink blocked: document deletion disabled (write_protect.allow_document_delete=false)")
                raise pyfuse3.FUSEError(errno.EPERM)
            doc_id = target_entry.document_id
            if not doc_id:
                raise pyfuse3.FUSEError(errno.EPERM)
            try:
                await self._api.delete(f"/documents/{doc_id}")
                log.info(f"Deleted document via API: {target_entry.name} (id={doc_id})")
            except Exception as e:
                status = getattr(getattr(e, "response", None), "status_code", None)
                if status == 404:
                    raise pyfuse3.FUSEError(errno.ENOENT)
                elif status == 403:
                    raise pyfuse3.FUSEError(errno.EACCES)
                log.error(f"Failed to delete document '{doc_id}': {e}")
                raise pyfuse3.FUSEError(errno.EIO)
            # Also remove companion inode for images (image_prose)
            companion_inodes = set()
            for inode, entry in self._inodes.items():
                if entry.document_id == doc_id and inode != target_inode:
                    companion_inodes.add(inode)
            for inode in companion_inodes:
                del self._inodes[inode]
                self._free_inode(inode)
            del self._inodes[target_inode]
            self._free_inode(target_inode)
            self._invalidate_cache(parent_inode)
            return

        # Ingestion file cleanup (e.g. vim test files like 4913, or abandoned writes)
        if target_entry.entry_type == "ingestion_file":
            self._write_buffers.pop(target_inode, None)
            self._write_info.pop(target_inode, None)
            del self._inodes[target_inode]
            self._free_inode(target_inode)
            self._invalidate_cache(parent_inode)
            return

        # Symlink unlinking
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
            # Create ontology on the platform via API
            ontology_name = name_str
            try:
                await self._api.post("/ontology/", json={"name": ontology_name})
                log.info(f"Created ontology via API: {ontology_name}")
            except Exception as e:
                status = getattr(getattr(e, "response", None), "status_code", None)
                if status == 409:
                    raise pyfuse3.FUSEError(errno.EEXIST)
                elif status == 403:
                    raise pyfuse3.FUSEError(errno.EACCES)
                log.error(f"Failed to create ontology '{ontology_name}': {e}")
                raise pyfuse3.FUSEError(errno.EIO)
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
        """Remove a query directory or delete an ontology."""
        name_str = name.decode("utf-8")
        log.info(f"rmdir: parent={parent_inode}, name={name_str}")

        parent_entry = self._inodes.get(parent_inode)
        if not parent_entry:
            raise pyfuse3.FUSEError(errno.ENOENT)

        # Ontology deletion via rmdir on ontology_root children
        if parent_entry.entry_type == "ontology_root":
            if not self.write_protect.allow_ontology_delete:
                log.warning(f"rmdir blocked: ontology deletion disabled (write_protect.allow_ontology_delete=false)")
                raise pyfuse3.FUSEError(errno.EPERM)
            try:
                await self._api.delete(f"/ontology/{name_str}")
                log.info(f"Deleted ontology via API: {name_str}")
            except Exception as e:
                status = getattr(getattr(e, "response", None), "status_code", None)
                if status == 404:
                    raise pyfuse3.FUSEError(errno.ENOENT)
                elif status == 403:
                    raise pyfuse3.FUSEError(errno.EACCES)
                log.error(f"Failed to delete ontology '{name_str}': {e}")
                raise pyfuse3.FUSEError(errno.EIO)
            # Clean up all local inodes for this ontology
            inodes_to_remove = set()
            for inode, entry in self._inodes.items():
                if entry.ontology == name_str and entry.entry_type != "ontology_root":
                    inodes_to_remove.add(inode)
            for inode in inodes_to_remove:
                del self._inodes[inode]
                self._free_inode(inode)
            self._pending_ontologies.discard(name_str)
            self._invalidate_cache(parent_inode)
            return

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
            # Can't rmdir from documents_dir, etc.
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
