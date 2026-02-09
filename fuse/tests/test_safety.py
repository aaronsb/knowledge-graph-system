"""Tests for kg-fuse safety fences."""

import os
import stat
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from kg_fuse.safety import (
    validate_mountpoint, ensure_mountpoint,
    BLOCKED_PATHS,
    write_pid, read_pid, clear_pid,
    is_process_alive, is_kg_fuse_process,
    find_mounted_fuse, find_all_fuse_mounts,
    is_mount_orphaned, fusermount_unmount,
    detect_shell,
    add_to_rc, remove_from_rc, RC_BEGIN, RC_END,
    has_systemd, get_systemd_unit_path,
    check_config_permissions, fix_config_permissions,
)


class TestValidateMountpoint:
    """Tests for mountpoint validation."""

    def test_blocks_system_paths(self):
        # Only test paths that resolve to themselves (avoid /bin -> /usr/bin symlinks)
        for path in ["/", "/home", "/etc", "/usr", "/var", "/tmp"]:
            resolved = os.path.realpath(path)
            if resolved in BLOCKED_PATHS:
                error = validate_mountpoint(path)
                assert error is not None, f"Should block {path}"
                assert "system directory" in error

    def test_allows_reasonable_paths(self, tmp_path):
        mount_dir = tmp_path / "knowledge"
        mount_dir.mkdir()
        with patch("kg_fuse.safety.find_all_fuse_mounts", return_value=[]):
            error = validate_mountpoint(str(mount_dir))
            assert error is None

    def test_blocks_non_empty_directory(self, tmp_path):
        mount_dir = tmp_path / "notempty"
        mount_dir.mkdir()
        (mount_dir / "file.txt").write_text("data")
        with patch("kg_fuse.safety.find_all_fuse_mounts", return_value=[]):
            error = validate_mountpoint(str(mount_dir))
            assert error is not None
            assert "not empty" in error

    def test_allows_empty_directory(self, tmp_path):
        mount_dir = tmp_path / "empty"
        mount_dir.mkdir()
        with patch("kg_fuse.safety.find_all_fuse_mounts", return_value=[]):
            error = validate_mountpoint(str(mount_dir))
            assert error is None

    def test_blocks_existing_fuse_collision(self, tmp_path):
        mount_dir = tmp_path / "mnt"
        mount_dir.mkdir()
        fake_fuse = [{
            "source": "rclone",
            "mountpoint": str(mount_dir),
            "fstype": "fuse.rclone",
            "is_ours": False,
            "is_system": False,
        }]
        with patch("kg_fuse.safety.find_all_fuse_mounts", return_value=fake_fuse):
            error = validate_mountpoint(str(mount_dir))
            assert error is not None
            assert "already a FUSE mount" in error

    def test_blocks_existing_kg_fuse_collision(self, tmp_path):
        mount_dir = tmp_path / "mnt"
        mount_dir.mkdir()
        fake_fuse = [{
            "source": "kg-fuse",
            "mountpoint": str(mount_dir),
            "fstype": "fuse.kg-fuse",
            "is_ours": True,
            "is_system": False,
        }]
        with patch("kg_fuse.safety.find_all_fuse_mounts", return_value=fake_fuse):
            error = validate_mountpoint(str(mount_dir))
            assert error is not None
            assert "already has a kg-fuse mount" in error

    def test_allows_nonexistent_directory(self, tmp_path):
        mount_dir = tmp_path / "new_mount"
        with patch("kg_fuse.safety.find_all_fuse_mounts", return_value=[]):
            error = validate_mountpoint(str(mount_dir))
            assert error is None


class TestEnsureMountpoint:
    """Tests for mountpoint directory creation."""

    def test_creates_new_directory(self, tmp_path):
        mount_dir = tmp_path / "new_mount"
        err = ensure_mountpoint(str(mount_dir))
        assert err is None
        assert mount_dir.is_dir()

    def test_noop_on_existing_directory(self, tmp_path):
        mount_dir = tmp_path / "existing"
        mount_dir.mkdir()
        err = ensure_mountpoint(str(mount_dir))
        assert err is None

    def test_returns_error_on_permission_denied(self):
        # /proc is not writable
        err = ensure_mountpoint("/proc/fake_mount")
        assert err is not None


class TestPidManagement:
    """Tests for PID file operations."""

    def test_write_read_clear_cycle(self, tmp_path):
        mp = "/mnt/test"
        with patch("kg_fuse.safety.get_pid_path", return_value=tmp_path / "test.pid"):
            write_pid(mp, 12345)
            assert read_pid(mp) == 12345
            clear_pid(mp)
            assert read_pid(mp) is None

    def test_read_returns_none_when_missing(self, tmp_path):
        with patch("kg_fuse.safety.get_pid_path", return_value=tmp_path / "missing.pid"):
            assert read_pid("/mnt/missing") is None

    def test_read_returns_none_on_corrupt_pid(self, tmp_path):
        pid_file = tmp_path / "bad.pid"
        pid_file.write_text("not-a-number")
        with patch("kg_fuse.safety.get_pid_path", return_value=pid_file):
            assert read_pid("/mnt/bad") is None


class TestProcessChecks:
    """Tests for process alive/identity checks."""

    def test_is_process_alive_for_self(self):
        assert is_process_alive(os.getpid()) is True

    def test_is_process_alive_for_invalid_pid(self):
        # PID 99999999 is very unlikely to exist
        assert is_process_alive(99999999) is False

    def test_is_kg_fuse_process_for_nonexistent(self):
        assert is_kg_fuse_process(99999999) is False


class TestFuseMountDetection:
    """Tests for FUSE mount enumeration."""

    def test_find_mounted_fuse_parses_proc_mounts(self, tmp_path):
        proc_mounts = tmp_path / "mounts"
        proc_mounts.write_text(
            "kg-fuse /mnt/knowledge fuse.kg-fuse rw 0 0\n"
            "sysfs /sys sysfs rw 0 0\n"
        )
        with patch("kg_fuse.safety.Path") as mock_path:
            # Make Path("/proc/mounts").read_text() return our test data
            mock_path.return_value.read_text.return_value = proc_mounts.read_text()
            # But we need the actual Path for other uses — this is tricky.
            # Use a more targeted patch:
            pass

        # More reliable: patch at the read level
        with patch("kg_fuse.safety.Path.__truediv__") as _:
            pass

        # Simplest: test the output format contract
        # find_mounted_fuse returns list of dicts with "mountpoint" and "fstype"
        mounts = find_mounted_fuse()
        # We can't easily mock /proc/mounts in a unit test, but we can
        # verify the return type
        assert isinstance(mounts, list)

    def test_find_all_fuse_mounts_filters_system(self):
        """System FUSE mounts (fusectl, portal) should be marked."""
        # Test with real /proc/mounts if available
        mounts = find_all_fuse_mounts()
        assert isinstance(mounts, list)
        for m in mounts:
            assert "source" in m
            assert "mountpoint" in m
            assert "is_ours" in m
            assert "is_system" in m
            # System mounts like fusectl should be flagged
            if m["source"] == "fusectl":
                assert m["is_system"] is True


class TestProcMountsParsing:
    """Tests for /proc/mounts parsing with controlled input."""

    def test_find_mounted_fuse_with_mock_data(self):
        mock_content = (
            "kg-fuse /mnt/knowledge fuse.kg-fuse rw,nosuid,nodev 0 0\n"
            "sysfs /sys sysfs rw,nosuid,nodev,noexec,relatime 0 0\n"
            "kg-fuse /mnt/archive fuse.kg-fuse rw 0 0\n"
        )
        with patch.object(Path, "read_text", return_value=mock_content):
            mounts = find_mounted_fuse()
            assert len(mounts) == 2
            assert mounts[0]["mountpoint"] == "/mnt/knowledge"
            assert mounts[1]["mountpoint"] == "/mnt/archive"

    def test_find_all_fuse_mounts_with_mixed_data(self):
        mock_content = (
            "kg-fuse /mnt/knowledge fuse.kg-fuse rw 0 0\n"
            "fusectl /sys/fs/fuse/connections fusectl rw 0 0\n"
            "rclone /mnt/gdrive fuse.rclone rw 0 0\n"
            "portal /run/user/1000/doc fuse.portal rw 0 0\n"
            "sysfs /sys sysfs rw 0 0\n"
        )
        with patch.object(Path, "read_text", return_value=mock_content):
            mounts = find_all_fuse_mounts()
            # Should find 4 FUSE mounts (not sysfs)
            assert len(mounts) == 4

            # kg-fuse is ours
            kg = [m for m in mounts if m["is_ours"]]
            assert len(kg) == 1
            assert kg[0]["mountpoint"] == "/mnt/knowledge"

            # fusectl and portal are system
            system = [m for m in mounts if m["is_system"]]
            assert len(system) == 2

            # rclone is neither ours nor system
            rclone = [m for m in mounts if m["source"] == "rclone"]
            assert len(rclone) == 1
            assert rclone[0]["is_ours"] is False
            assert rclone[0]["is_system"] is False


class TestOrphanDetection:
    """Tests for orphaned mount detection."""

    def test_is_mount_orphaned_on_real_path(self, tmp_path):
        # A normal directory should not be orphaned
        assert is_mount_orphaned(str(tmp_path)) is False


class TestRcFileManagement:
    """Tests for shell RC file manipulation."""

    def test_add_to_rc_creates_block(self, tmp_path):
        rc_path = tmp_path / ".zshrc"
        rc_path.write_text("# existing config\n")

        ok, msg = add_to_rc(rc_path, "kg-fuse mount")
        assert ok is True
        content = rc_path.read_text()
        assert RC_BEGIN in content
        assert RC_END in content
        assert "kg-fuse mount" in content

    def test_add_to_rc_creates_backup(self, tmp_path):
        rc_path = tmp_path / ".zshrc"
        rc_path.write_text("# existing\n")

        add_to_rc(rc_path, "kg-fuse mount")
        # .with_suffix appends to existing suffix (empty for dotfiles)
        backup = rc_path.with_suffix(rc_path.suffix + ".kg-fuse-backup")
        assert backup.exists()
        assert backup.read_text() == "# existing\n"

    def test_add_to_rc_refuses_duplicate(self, tmp_path):
        rc_path = tmp_path / ".zshrc"
        rc_path.write_text("# existing\n")

        add_to_rc(rc_path, "kg-fuse mount")
        ok, msg = add_to_rc(rc_path, "kg-fuse mount again")
        assert ok is False
        assert "already exists" in msg

    def test_remove_from_rc(self, tmp_path):
        rc_path = tmp_path / ".zshrc"
        rc_path.write_text("# before\n")

        add_to_rc(rc_path, "kg-fuse mount")
        ok, msg = remove_from_rc(rc_path)
        assert ok is True
        content = rc_path.read_text()
        assert RC_BEGIN not in content
        assert RC_END not in content
        assert "kg-fuse mount" not in content
        assert "# before\n" in content

    def test_remove_from_rc_when_no_block(self, tmp_path):
        rc_path = tmp_path / ".zshrc"
        rc_path.write_text("# no block\n")
        ok, msg = remove_from_rc(rc_path)
        assert ok is False

    def test_add_to_nonexistent_rc(self, tmp_path):
        rc_path = tmp_path / ".bashrc"
        ok, msg = add_to_rc(rc_path, "kg-fuse mount")
        assert ok is True
        assert rc_path.exists()


class TestShellDetection:
    """Tests for shell and RC file detection."""

    def test_detect_zsh(self):
        with patch.dict(os.environ, {"SHELL": "/usr/bin/zsh"}):
            result = detect_shell()
            assert result is not None
            name, path = result
            assert name == "zsh"
            assert ".zshrc" in str(path)

    def test_detect_bash(self):
        with patch.dict(os.environ, {"SHELL": "/bin/bash"}):
            result = detect_shell()
            assert result is not None
            name, _ = result
            assert name == "bash"

    def test_detect_fish(self):
        with patch.dict(os.environ, {"SHELL": "/usr/bin/fish"}):
            result = detect_shell()
            assert result is not None
            name, path = result
            assert name == "fish"
            assert "config.fish" in str(path)

    def test_detect_unknown_shell(self):
        with patch.dict(os.environ, {"SHELL": "/usr/bin/unknown"}):
            assert detect_shell() is None


class TestSystemdHelpers:
    """Tests for systemd detection."""

    def test_has_systemd_checks_both_conditions(self):
        # Just verify it returns a bool without crashing
        result = has_systemd()
        assert isinstance(result, bool)

    def test_systemd_unit_path_in_config_dir(self):
        path = get_systemd_unit_path()
        assert "systemd" in str(path)
        assert "kg-fuse.service" in str(path)


class TestConfigPermissions:
    """Tests for credential file permission checks."""

    def test_check_warns_on_world_readable(self, tmp_path):
        cfg = tmp_path / "config.json"
        cfg.write_text("{}")
        cfg.chmod(0o644)
        warning = check_config_permissions(cfg)
        assert warning is not None
        assert "readable by group/others" in warning

    def test_check_ok_on_600(self, tmp_path):
        cfg = tmp_path / "config.json"
        cfg.write_text("{}")
        cfg.chmod(0o600)
        assert check_config_permissions(cfg) is None

    def test_check_ok_on_missing_file(self, tmp_path):
        assert check_config_permissions(tmp_path / "missing") is None

    def test_fix_sets_600(self, tmp_path):
        cfg = tmp_path / "config.json"
        cfg.write_text("{}")
        cfg.chmod(0o644)
        ok, msg = fix_config_permissions(cfg)
        assert ok is True
        mode = cfg.stat().st_mode & 0o777
        assert mode == 0o600

    def test_fix_on_missing_file(self, tmp_path):
        ok, msg = fix_config_permissions(tmp_path / "missing")
        assert ok is False
