"""Tests for kg-fuse daemon lifecycle management."""

import os
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from kg_fuse.daemon import mount_status

# mount_status() imports find_mounted_fuse and is_mount_orphaned locally from .safety,
# so we patch them at the safety module level.
_SAFETY = "kg_fuse.safety"


class TestMountStatus:
    """Tests for mount_status() which checks daemon state."""

    def test_running_with_valid_pid(self, tmp_path):
        """Process alive + is kg-fuse + has PID file = running."""
        my_pid = os.getpid()
        with patch("kg_fuse.daemon.read_pid", return_value=my_pid), \
             patch("kg_fuse.daemon.is_process_alive", return_value=True), \
             patch("kg_fuse.daemon.is_kg_fuse_process", return_value=True), \
             patch(f"{_SAFETY}.find_mounted_fuse", return_value=[]):
            status = mount_status("/mnt/test")
            assert status["running"] is True
            assert status["pid"] == my_pid
            assert status["orphaned"] is False

    def test_not_running_no_pid(self):
        """No PID file = not running."""
        with patch("kg_fuse.daemon.read_pid", return_value=None), \
             patch(f"{_SAFETY}.find_mounted_fuse", return_value=[]), \
             patch("kg_fuse.daemon.clear_pid"):
            status = mount_status("/mnt/test")
            assert status["running"] is False
            assert status["pid"] is None
            assert status["orphaned"] is False

    def test_stale_pid_cleaned_up(self):
        """PID exists but process dead + not in /proc/mounts = stale, cleaned up."""
        with patch("kg_fuse.daemon.read_pid", return_value=99999), \
             patch("kg_fuse.daemon.is_process_alive", return_value=False), \
             patch("kg_fuse.daemon.is_kg_fuse_process", return_value=False), \
             patch(f"{_SAFETY}.find_mounted_fuse", return_value=[]), \
             patch("kg_fuse.daemon.clear_pid") as mock_clear:
            status = mount_status("/mnt/test")
            assert status["running"] is False
            assert status["pid"] is None
            mock_clear.assert_called_once_with("/mnt/test")

    def test_orphaned_mount_detected(self):
        """Mount in /proc/mounts but process dead = orphaned."""
        mounted = [{"mountpoint": "/mnt/test", "fstype": "fuse.kg-fuse"}]
        with patch("kg_fuse.daemon.read_pid", return_value=99999), \
             patch("kg_fuse.daemon.is_process_alive", return_value=False), \
             patch("kg_fuse.daemon.is_kg_fuse_process", return_value=False), \
             patch(f"{_SAFETY}.find_mounted_fuse", return_value=mounted), \
             patch(f"{_SAFETY}.is_mount_orphaned", return_value=True):
            status = mount_status("/mnt/test")
            assert status["orphaned"] is True
            assert status["running"] is False

    def test_running_mount_in_proc_mounts(self):
        """Mount in /proc/mounts and not orphaned = running (even without PID)."""
        mounted = [{"mountpoint": "/mnt/test", "fstype": "fuse.kg-fuse"}]
        with patch("kg_fuse.daemon.read_pid", return_value=None), \
             patch(f"{_SAFETY}.find_mounted_fuse", return_value=mounted), \
             patch(f"{_SAFETY}.is_mount_orphaned", return_value=False):
            status = mount_status("/mnt/test")
            assert status["running"] is True
            assert status["orphaned"] is False

    def test_pid_not_kg_fuse_process(self):
        """PID exists, process alive, but not a kg-fuse process = not running."""
        with patch("kg_fuse.daemon.read_pid", return_value=12345), \
             patch("kg_fuse.daemon.is_process_alive", return_value=True), \
             patch("kg_fuse.daemon.is_kg_fuse_process", return_value=False), \
             patch(f"{_SAFETY}.find_mounted_fuse", return_value=[]), \
             patch("kg_fuse.daemon.clear_pid"):
            status = mount_status("/mnt/test")
            assert status["running"] is False


class TestForkMountContract:
    """Verify fork_mount's interface contract without actually forking."""

    def test_fork_mount_exists(self):
        """fork_mount should be importable."""
        from kg_fuse.daemon import fork_mount
        assert callable(fork_mount)

    def test_fork_mount_signature(self):
        """fork_mount takes (mountpoint, config, run_fn)."""
        import inspect
        from kg_fuse.daemon import fork_mount
        sig = inspect.signature(fork_mount)
        params = list(sig.parameters.keys())
        assert params == ["mountpoint", "config", "run_fn"]

    def test_no_daemonize_function(self):
        """Dead daemonize() function should have been removed."""
        import kg_fuse.daemon as daemon_mod
        assert not hasattr(daemon_mod, "daemonize")
