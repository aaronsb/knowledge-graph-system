"""Tests for FUSE ontology/document lifecycle operations (mkdir, rmdir, unlink)."""

import json
import errno
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import pyfuse3

from kg_fuse.config import WriteProtectConfig, TagsConfig, JobsConfig
from kg_fuse.models import InodeEntry


# --- Helpers to build a minimal KnowledgeGraphFS without real FUSE ---

def _make_fs(write_protect=None, mountpoint=None):
    """Create a KnowledgeGraphFS with mocked API client and cache."""
    with patch("kg_fuse.filesystem.KnowledgeGraphClient") as MockClient, \
         patch("kg_fuse.filesystem.EpochCache"), \
         patch("kg_fuse.filesystem.ImageHandler"):
        from kg_fuse.filesystem import KnowledgeGraphFS
        fs = KnowledgeGraphFS(
            api_url="http://test:8000",
            client_id="test-id",
            client_secret="test-secret",
            write_protect_config=write_protect or WriteProtectConfig(),
            mountpoint=mountpoint or "/mnt/test",
        )
        # Replace the API client with a controllable async mock
        fs._api = AsyncMock()
        return fs


def _mock_ctx():
    """Create a mock pyfuse3.RequestContext."""
    ctx = MagicMock(spec=pyfuse3.RequestContext)
    ctx.uid = 1000
    ctx.gid = 1000
    ctx.pid = 12345
    return ctx


class TestMkdirOntology:
    """Tests for mkdir creating ontologies via API."""

    @pytest.mark.anyio
    async def test_mkdir_creates_ontology_via_api(self):
        fs = _make_fs()
        ctx = _mock_ctx()
        fs._api.post = AsyncMock(return_value={"name": "test-onto", "status": "ok"})
        # Mock getattr to return a valid EntryAttributes
        mock_attr = MagicMock(spec=pyfuse3.EntryAttributes)
        fs.getattr = AsyncMock(return_value=mock_attr)

        result = await fs.mkdir(fs.ONTOLOGY_ROOT_INODE, b"test-onto", 0o755, ctx)

        fs._api.post.assert_called_once_with("/ontology/", json={"name": "test-onto"})
        # Verify inode was created for the new ontology
        found = [e for e in fs._inodes.values()
                 if e.entry_type == "ontology" and e.name == "test-onto"]
        assert len(found) == 1
        assert found[0].ontology == "test-onto"

    @pytest.mark.anyio
    async def test_mkdir_ontology_conflict_returns_eexist(self):
        fs = _make_fs()
        ctx = _mock_ctx()
        resp = MagicMock()
        resp.status_code = 409
        exc = Exception("conflict")
        exc.response = resp
        fs._api.post = AsyncMock(side_effect=exc)

        with pytest.raises(pyfuse3.FUSEError) as exc_info:
            await fs.mkdir(fs.ONTOLOGY_ROOT_INODE, b"existing", 0o755, ctx)
        assert exc_info.value.errno == errno.EEXIST

    @pytest.mark.anyio
    async def test_mkdir_ontology_permission_denied(self):
        fs = _make_fs()
        ctx = _mock_ctx()
        resp = MagicMock()
        resp.status_code = 403
        exc = Exception("forbidden")
        exc.response = resp
        fs._api.post = AsyncMock(side_effect=exc)

        with pytest.raises(pyfuse3.FUSEError) as exc_info:
            await fs.mkdir(fs.ONTOLOGY_ROOT_INODE, b"denied", 0o755, ctx)
        assert exc_info.value.errno == errno.EACCES

    @pytest.mark.anyio
    async def test_mkdir_ontology_server_error_returns_eio(self):
        fs = _make_fs()
        ctx = _mock_ctx()
        exc = Exception("server error")
        exc.response = None  # No response object
        fs._api.post = AsyncMock(side_effect=exc)

        with pytest.raises(pyfuse3.FUSEError) as exc_info:
            await fs.mkdir(fs.ONTOLOGY_ROOT_INODE, b"broken", 0o755, ctx)
        assert exc_info.value.errno == errno.EIO


class TestRmdirOntology:
    """Tests for rmdir deleting ontologies via API."""

    @pytest.mark.anyio
    async def test_rmdir_blocked_by_default(self):
        """Write protection blocks ontology deletion by default."""
        fs = _make_fs(write_protect=WriteProtectConfig())  # defaults: both False
        ctx = _mock_ctx()

        with pytest.raises(pyfuse3.FUSEError) as exc_info:
            await fs.rmdir(fs.ONTOLOGY_ROOT_INODE, b"some-onto", ctx)
        assert exc_info.value.errno == errno.EPERM
        # API should NOT be called
        fs._api.delete.assert_not_called()

    @pytest.mark.anyio
    async def test_rmdir_allowed_when_write_protect_enabled(self):
        fs = _make_fs(write_protect=WriteProtectConfig(allow_ontology_delete=True))
        ctx = _mock_ctx()
        fs._api.delete = AsyncMock(return_value={"deleted": True})

        # Add an ontology inode to simulate existing state
        inode = fs._allocate_inode()
        fs._inodes[inode] = InodeEntry(
            name="test-onto",
            entry_type="ontology",
            parent=fs.ONTOLOGY_ROOT_INODE,
            ontology="test-onto",
        )

        await fs.rmdir(fs.ONTOLOGY_ROOT_INODE, b"test-onto", ctx)

        fs._api.delete.assert_called_once_with("/ontology/test-onto")
        # Inode should be cleaned up
        remaining = [e for e in fs._inodes.values()
                     if e.entry_type == "ontology" and e.name == "test-onto"]
        assert len(remaining) == 0

    @pytest.mark.anyio
    async def test_rmdir_ontology_not_found(self):
        fs = _make_fs(write_protect=WriteProtectConfig(allow_ontology_delete=True))
        ctx = _mock_ctx()
        resp = MagicMock()
        resp.status_code = 404
        exc = Exception("not found")
        exc.response = resp
        fs._api.delete = AsyncMock(side_effect=exc)

        with pytest.raises(pyfuse3.FUSEError) as exc_info:
            await fs.rmdir(fs.ONTOLOGY_ROOT_INODE, b"missing", ctx)
        assert exc_info.value.errno == errno.ENOENT

    @pytest.mark.anyio
    async def test_rmdir_ontology_cascades_local_inodes(self):
        """When deleting an ontology, all child inodes should be removed."""
        fs = _make_fs(write_protect=WriteProtectConfig(allow_ontology_delete=True))
        ctx = _mock_ctx()
        fs._api.delete = AsyncMock(return_value={"deleted": True})

        # Create ontology + documents_dir + document inodes
        onto_inode = fs._allocate_inode()
        fs._inodes[onto_inode] = InodeEntry(
            name="cascade-test", entry_type="ontology",
            parent=fs.ONTOLOGY_ROOT_INODE, ontology="cascade-test",
        )
        docs_inode = fs._allocate_inode()
        fs._inodes[docs_inode] = InodeEntry(
            name="documents", entry_type="documents_dir",
            parent=onto_inode, ontology="cascade-test",
        )
        doc_inode = fs._allocate_inode()
        fs._inodes[doc_inode] = InodeEntry(
            name="readme.md", entry_type="document",
            parent=docs_inode, ontology="cascade-test",
            document_id="sha256:abc123",
        )

        await fs.rmdir(fs.ONTOLOGY_ROOT_INODE, b"cascade-test", ctx)

        # All cascade-test inodes should be gone
        remaining = [e for e in fs._inodes.values() if e.ontology == "cascade-test"]
        assert len(remaining) == 0


class TestUnlinkDocument:
    """Tests for unlink deleting documents via API."""

    def _setup_doc_inodes(self, fs):
        """Add a documents_dir with a document inside an ontology."""
        onto_inode = fs._allocate_inode()
        fs._inodes[onto_inode] = InodeEntry(
            name="test-onto", entry_type="ontology",
            parent=fs.ONTOLOGY_ROOT_INODE, ontology="test-onto",
        )
        docs_inode = fs._allocate_inode()
        fs._inodes[docs_inode] = InodeEntry(
            name="documents", entry_type="documents_dir",
            parent=onto_inode, ontology="test-onto",
        )
        doc_inode = fs._allocate_inode()
        fs._inodes[doc_inode] = InodeEntry(
            name="paper.md", entry_type="document",
            parent=docs_inode, ontology="test-onto",
            document_id="sha256:doc1",
        )
        return docs_inode, doc_inode

    @pytest.mark.anyio
    async def test_unlink_blocked_by_default(self):
        fs = _make_fs(write_protect=WriteProtectConfig())
        ctx = _mock_ctx()
        docs_inode, doc_inode = self._setup_doc_inodes(fs)

        with pytest.raises(pyfuse3.FUSEError) as exc_info:
            await fs.unlink(docs_inode, b"paper.md", ctx)
        assert exc_info.value.errno == errno.EPERM
        fs._api.delete.assert_not_called()

    @pytest.mark.anyio
    async def test_unlink_document_calls_api(self):
        fs = _make_fs(write_protect=WriteProtectConfig(allow_document_delete=True))
        ctx = _mock_ctx()
        docs_inode, doc_inode = self._setup_doc_inodes(fs)
        fs._api.delete = AsyncMock(return_value={
            "document_id": "sha256:doc1", "deleted": True,
            "sources_deleted": 3, "orphaned_concepts_deleted": 1,
        })

        await fs.unlink(docs_inode, b"paper.md", ctx)

        fs._api.delete.assert_called_once_with("/documents/sha256:doc1")
        # Inode should be cleaned up
        assert doc_inode not in fs._inodes

    @pytest.mark.anyio
    async def test_unlink_document_not_found(self):
        fs = _make_fs(write_protect=WriteProtectConfig(allow_document_delete=True))
        ctx = _mock_ctx()
        docs_inode, doc_inode = self._setup_doc_inodes(fs)
        resp = MagicMock()
        resp.status_code = 404
        exc = Exception("not found")
        exc.response = resp
        fs._api.delete = AsyncMock(side_effect=exc)

        with pytest.raises(pyfuse3.FUSEError) as exc_info:
            await fs.unlink(docs_inode, b"paper.md", ctx)
        assert exc_info.value.errno == errno.ENOENT

    @pytest.mark.anyio
    async def test_unlink_removes_companion_image_inodes(self):
        """Image deletion should also remove the .png.md companion."""
        fs = _make_fs(write_protect=WriteProtectConfig(allow_document_delete=True))
        ctx = _mock_ctx()

        # Set up image document + companion prose
        onto_inode = fs._allocate_inode()
        fs._inodes[onto_inode] = InodeEntry(
            name="test-onto", entry_type="ontology",
            parent=fs.ONTOLOGY_ROOT_INODE, ontology="test-onto",
        )
        docs_inode = fs._allocate_inode()
        fs._inodes[docs_inode] = InodeEntry(
            name="documents", entry_type="documents_dir",
            parent=onto_inode, ontology="test-onto",
        )
        img_inode = fs._allocate_inode()
        fs._inodes[img_inode] = InodeEntry(
            name="diagram.png", entry_type="image_document",
            parent=docs_inode, ontology="test-onto",
            document_id="sha256:img1",
        )
        prose_inode = fs._allocate_inode()
        fs._inodes[prose_inode] = InodeEntry(
            name="diagram.png.md", entry_type="image_prose",
            parent=docs_inode, ontology="test-onto",
            document_id="sha256:img1",  # Same document_id
        )

        fs._api.delete = AsyncMock(return_value={
            "document_id": "sha256:img1", "deleted": True,
            "sources_deleted": 1, "orphaned_concepts_deleted": 0,
        })

        await fs.unlink(docs_inode, b"diagram.png", ctx)

        # Both the image and its companion should be gone
        assert img_inode not in fs._inodes
        assert prose_inode not in fs._inodes

    @pytest.mark.anyio
    async def test_unlink_nonexistent_file_returns_enoent(self):
        fs = _make_fs(write_protect=WriteProtectConfig(allow_document_delete=True))
        ctx = _mock_ctx()

        # Use ontology_root as parent (no children with this name)
        with pytest.raises(pyfuse3.FUSEError) as exc_info:
            await fs.unlink(fs.ONTOLOGY_ROOT_INODE, b"ghost.md", ctx)
        assert exc_info.value.errno == errno.ENOENT

    @pytest.mark.anyio
    async def test_unlink_non_document_returns_eperm(self):
        """Trying to unlink a non-document, non-symlink entry should fail."""
        fs = _make_fs(write_protect=WriteProtectConfig(allow_document_delete=True))
        ctx = _mock_ctx()

        # Create a concept inode (not deletable via unlink)
        onto_inode = fs._allocate_inode()
        fs._inodes[onto_inode] = InodeEntry(
            name="test-onto", entry_type="ontology",
            parent=fs.ONTOLOGY_ROOT_INODE, ontology="test-onto",
        )
        concept_inode = fs._allocate_inode()
        fs._inodes[concept_inode] = InodeEntry(
            name="some-concept.concept.md", entry_type="concept",
            parent=onto_inode, ontology="test-onto",
            concept_id="c_abc123",
        )

        with pytest.raises(pyfuse3.FUSEError) as exc_info:
            await fs.unlink(onto_inode, b"some-concept.concept.md", ctx)
        assert exc_info.value.errno == errno.EPERM


class TestConfigReload:
    """Tests for hot-reload of fuse.json config changes."""

    def test_reload_updates_write_protect(self, tmp_path):
        fs = _make_fs(mountpoint="/mnt/test")
        assert fs.write_protect.allow_ontology_delete is False

        fuse_path = tmp_path / "fuse.json"
        fuse_path.write_text(json.dumps({
            "mounts": {"/mnt/test": {
                "write_protect": {"allow_ontology_delete": True, "allow_document_delete": True},
            }},
        }))
        with patch("kg_fuse.filesystem.read_fuse_config",
                    return_value=json.loads(fuse_path.read_text())):
            fs._reload_config()

        assert fs.write_protect.allow_ontology_delete is True
        assert fs.write_protect.allow_document_delete is True

    def test_reload_updates_tags(self, tmp_path):
        fs = _make_fs(mountpoint="/mnt/test")
        assert fs.tags_config.threshold == 0.5

        with patch("kg_fuse.filesystem.read_fuse_config", return_value={
            "mounts": {"/mnt/test": {
                "tags": {"enabled": False, "threshold": 0.8},
            }},
        }):
            fs._reload_config()

        assert fs.tags_config.enabled is False
        assert fs.tags_config.threshold == 0.8

    def test_reload_updates_jobs(self, tmp_path):
        fs = _make_fs(mountpoint="/mnt/test")
        assert fs.jobs_config.hide_jobs is False

        with patch("kg_fuse.filesystem.read_fuse_config", return_value={
            "mounts": {"/mnt/test": {"jobs": {"hide_jobs": True}}},
        }):
            fs._reload_config()

        assert fs.jobs_config.hide_jobs is True

    def test_reload_noop_when_no_config(self):
        fs = _make_fs(mountpoint="/mnt/test")
        with patch("kg_fuse.filesystem.read_fuse_config", return_value=None):
            fs._reload_config()
        # Defaults unchanged
        assert fs.write_protect.allow_ontology_delete is False

    def test_reload_noop_when_mount_missing(self):
        fs = _make_fs(mountpoint="/mnt/test")
        with patch("kg_fuse.filesystem.read_fuse_config", return_value={
            "mounts": {"/mnt/other": {}},
        }):
            fs._reload_config()
        assert fs.write_protect.allow_ontology_delete is False

    def test_reload_preserves_unchanged_values(self):
        """Only changed sections trigger updates."""
        fs = _make_fs(
            write_protect=WriteProtectConfig(allow_ontology_delete=True),
            mountpoint="/mnt/test",
        )
        with patch("kg_fuse.filesystem.read_fuse_config", return_value={
            "mounts": {"/mnt/test": {
                "write_protect": {"allow_ontology_delete": True, "allow_document_delete": False},
            }},
        }):
            fs._reload_config()
        # Unchanged — should still be True
        assert fs.write_protect.allow_ontology_delete is True


class TestWriteBack:
    """Tests for the write-back ingestion queue (hysteresis for editor save patterns)."""

    def _setup_ingest_dir(self, fs):
        """Add an ontology + ingest_dir and return the ingest_dir inode."""
        onto_inode = fs._allocate_inode()
        fs._inodes[onto_inode] = InodeEntry(
            name="test-onto", entry_type="ontology",
            parent=fs.ONTOLOGY_ROOT_INODE, ontology="test-onto",
        )
        ingest_inode = fs._allocate_inode()
        fs._inodes[ingest_inode] = InodeEntry(
            name="ingest", entry_type="ingest_dir",
            parent=onto_inode, ontology="test-onto",
        )
        return ingest_inode

    @pytest.mark.anyio
    async def test_release_queues_instead_of_immediate_ingest(self):
        """release() should stash content in pending queue, not call API."""
        fs = _make_fs()
        ctx = _mock_ctx()
        ingest_inode = self._setup_ingest_dir(fs)

        fi, _ = await fs.create(ingest_inode, b"paper.md", 0o644, 0, ctx)
        fh = fi.fh
        await fs.write(fh, 0, b"Hello world")
        await fs.release(fh)

        # Content should be in pending queue
        assert "test-onto/paper.md" in fs._pending_ingestions
        entry = fs._pending_ingestions["test-onto/paper.md"]
        assert entry["content"] == b"Hello world"
        assert entry["ontology"] == "test-onto"
        assert entry["filename"] == "paper.md"
        # API should NOT have been called yet
        fs._api.post.assert_not_called()

    @pytest.mark.anyio
    async def test_release_empty_file_not_queued(self):
        """Empty files (e.g. vim's 4913 test file) should not be queued."""
        fs = _make_fs()
        ctx = _mock_ctx()
        ingest_inode = self._setup_ingest_dir(fs)

        fi, _ = await fs.create(ingest_inode, b"4913", 0o644, 0, ctx)
        fh = fi.fh
        # No write — empty file
        await fs.release(fh)

        assert len(fs._pending_ingestions) == 0
        # Inode should be cleaned up
        assert fh not in fs._inodes

    @pytest.mark.anyio
    async def test_rename_active_inode_updates_name(self):
        """Renaming an open ingestion file updates its name and write_info."""
        fs = _make_fs()
        ctx = _mock_ctx()
        ingest_inode = self._setup_ingest_dir(fs)

        fi, _ = await fs.create(ingest_inode, b".tmp123", 0o644, 0, ctx)
        fh = fi.fh
        await fs.write(fh, 0, b"content here")

        # Rename before release (vim backupcopy=yes pattern)
        await fs.rename(ingest_inode, b".tmp123", ingest_inode, b"paper.md", 0, ctx)

        assert fs._inodes[fh].name == "paper.md"
        assert fs._write_info[fh]["filename"] == "paper.md"

    @pytest.mark.anyio
    async def test_rename_pending_ingestion_updates_queue(self):
        """Renaming after release updates the write-back queue key and resets timer."""
        fs = _make_fs()
        ctx = _mock_ctx()
        ingest_inode = self._setup_ingest_dir(fs)

        fi, _ = await fs.create(ingest_inode, b".tmp456", 0o644, 0, ctx)
        fh = fi.fh
        await fs.write(fh, 0, b"final content")
        await fs.release(fh)

        assert "test-onto/.tmp456" in fs._pending_ingestions
        old_ts = fs._pending_ingestions["test-onto/.tmp456"]["timestamp"]

        # Rename after release (vim release-then-rename ordering)
        import time
        time.sleep(0.01)  # Ensure measurable time difference
        await fs.rename(ingest_inode, b".tmp456", ingest_inode, b"paper.md", 0, ctx)

        # Old key gone, new key present
        assert "test-onto/.tmp456" not in fs._pending_ingestions
        assert "test-onto/paper.md" in fs._pending_ingestions
        entry = fs._pending_ingestions["test-onto/paper.md"]
        assert entry["content"] == b"final content"
        assert entry["filename"] == "paper.md"
        assert entry["timestamp"] >= old_ts  # Timer was reset

    @pytest.mark.anyio
    async def test_unlink_ingestion_file_cleans_up(self):
        """Unlinking an ingestion file should remove inode and buffers (no API call)."""
        fs = _make_fs()
        ctx = _mock_ctx()
        ingest_inode = self._setup_ingest_dir(fs)

        fi, _ = await fs.create(ingest_inode, b"scratch.txt", 0o644, 0, ctx)
        fh = fi.fh
        await fs.write(fh, 0, b"temp data")

        await fs.unlink(ingest_inode, b"scratch.txt", ctx)

        assert fh not in fs._inodes
        assert fh not in fs._write_buffers
        assert fh not in fs._write_info
        # No API calls for ingestion file cleanup
        fs._api.delete.assert_not_called()

    @pytest.mark.anyio
    async def test_rename_nonexistent_raises_enoent(self):
        """Renaming a file that doesn't exist in inodes or pending queue raises ENOENT."""
        fs = _make_fs()
        ctx = _mock_ctx()
        ingest_inode = self._setup_ingest_dir(fs)

        with pytest.raises(pyfuse3.FUSEError) as exc_info:
            await fs.rename(ingest_inode, b"ghost.txt", ingest_inode, b"new.txt", 0, ctx)
        assert exc_info.value.errno == errno.ENOENT

    @pytest.mark.anyio
    async def test_rename_non_ingestion_raises_eperm(self):
        """Renaming a non-ingestion entry (e.g. concept) should fail."""
        fs = _make_fs()
        ctx = _mock_ctx()
        ingest_inode = self._setup_ingest_dir(fs)

        concept_inode = fs._allocate_inode()
        fs._inodes[concept_inode] = InodeEntry(
            name="some.concept.md", entry_type="concept",
            parent=ingest_inode, ontology="test-onto",
            concept_id="c_abc",
        )

        with pytest.raises(pyfuse3.FUSEError) as exc_info:
            await fs.rename(ingest_inode, b"some.concept.md", ingest_inode, b"new.md", 0, ctx)
        assert exc_info.value.errno == errno.EPERM

    @pytest.mark.anyio
    async def test_destroy_flushes_pending(self):
        """Unmount should flush all pending ingestions before cleanup."""
        fs = _make_fs()
        ctx = _mock_ctx()
        ingest_inode = self._setup_ingest_dir(fs)

        fi, _ = await fs.create(ingest_inode, b"final-doc.md", 0o644, 0, ctx)
        fh = fi.fh
        await fs.write(fh, 0, b"important content")
        await fs.release(fh)
        assert len(fs._pending_ingestions) == 1

        # Mock the ingest call
        fs._api.post = AsyncMock(return_value={"job_id": "j_123"})
        fs._api.close = AsyncMock()

        await fs.destroy()

        # Pending queue should be drained
        assert len(fs._pending_ingestions) == 0
        # Ingestion should have been called
        fs._api.post.assert_called_once()
