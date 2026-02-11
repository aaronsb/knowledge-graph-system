"""Tests for kg-fuse CLI subcommands and helpers."""

import os
import sys
import pytest
from argparse import Namespace
from io import StringIO
from unittest.mock import patch, MagicMock

from kg_fuse.cli import (
    _supports_color, _use_color,
    _bold, _green, _yellow, _red, _dim,
    _mask_secret, _get_version,
    _test_api, _test_auth,
    _systemd_unit_active, _systemd_unit_enabled,
    _resolve_daemon_mode,
)


class TestAnsiHelpers:
    """Tests for ANSI color formatting."""

    def test_supports_color_false_with_no_color_env(self):
        with patch.dict(os.environ, {"NO_COLOR": "1"}):
            assert _supports_color() is False

    def test_supports_color_false_without_tty(self):
        with patch.dict(os.environ, {}, clear=True):
            mock_stdout = MagicMock()
            mock_stdout.isatty.return_value = False
            with patch.object(sys, "stdout", mock_stdout):
                assert _supports_color() is False

    def test_supports_color_true_with_tty(self):
        env = {k: v for k, v in os.environ.items() if k != "NO_COLOR"}
        with patch.dict(os.environ, env, clear=True):
            mock_stdout = MagicMock()
            mock_stdout.isatty.return_value = True
            with patch.object(sys, "stdout", mock_stdout):
                assert _supports_color() is True

    def test_bold_with_color(self):
        with patch("kg_fuse.cli._use_color", return_value=True):
            result = _bold("test")
            assert "\033[1m" in result
            assert "test" in result

    def test_bold_without_color(self):
        with patch("kg_fuse.cli._use_color", return_value=False):
            assert _bold("test") == "test"

    def test_green_with_color(self):
        with patch("kg_fuse.cli._use_color", return_value=True):
            result = _green("ok")
            assert "\033[32m" in result

    def test_green_without_color(self):
        with patch("kg_fuse.cli._use_color", return_value=False):
            assert _green("ok") == "ok"

    def test_yellow_with_color(self):
        with patch("kg_fuse.cli._use_color", return_value=True):
            result = _yellow("warn")
            assert "\033[33m" in result

    def test_red_with_color(self):
        with patch("kg_fuse.cli._use_color", return_value=True):
            result = _red("error")
            assert "\033[31m" in result

    def test_dim_with_color(self):
        with patch("kg_fuse.cli._use_color", return_value=True):
            result = _dim("faded")
            assert "\033[2m" in result

    def test_all_helpers_passthrough_without_color(self):
        with patch("kg_fuse.cli._use_color", return_value=False):
            assert _bold("a") == "a"
            assert _green("b") == "b"
            assert _yellow("c") == "c"
            assert _red("d") == "d"
            assert _dim("e") == "e"


class TestMaskSecret:
    """Tests for secret masking."""

    def test_masks_long_secret(self):
        assert _mask_secret("abcdefghijklmnop") == "****mnop"

    def test_masks_short_secret(self):
        assert _mask_secret("abc") == "****"

    def test_masks_exactly_4_chars(self):
        assert _mask_secret("abcd") == "****"

    def test_masks_5_chars(self):
        assert _mask_secret("abcde") == "****bcde"


class TestGetVersion:
    """Tests for version retrieval."""

    def test_returns_string(self):
        ver = _get_version()
        assert isinstance(ver, str)
        assert len(ver) > 0

    def test_returns_dev_when_not_installed(self):
        from importlib.metadata import PackageNotFoundError
        with patch("importlib.metadata.version", side_effect=PackageNotFoundError("kg-fuse")):
            ver = _get_version()
            assert ver == "dev"


class TestApiTesting:
    """Tests for API connectivity checks."""

    def test_api_reachable(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"version": "1.2.3"}
        with patch("kg_fuse.cli.httpx.get", return_value=mock_resp):
            ok, info = _test_api("http://localhost:8000")
            assert ok is True
            assert info == "1.2.3"

    def test_api_unreachable(self):
        import httpx
        with patch("kg_fuse.cli.httpx.get", side_effect=httpx.ConnectError("refused")):
            ok, info = _test_api("http://localhost:8000")
            assert ok is False
            assert "connection refused" in info

    def test_api_error_status(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        with patch("kg_fuse.cli.httpx.get", return_value=mock_resp):
            ok, info = _test_api("http://localhost:8000")
            assert ok is False
            assert "500" in info


class TestAuthTesting:
    """Tests for OAuth credential testing."""

    def test_auth_valid(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"username": "admin"}
        with patch("kg_fuse.cli.httpx.post", return_value=mock_resp):
            ok, info = _test_auth("http://localhost:8000", "id", "secret")
            assert ok is True
            assert info == "admin"

    def test_auth_invalid(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_resp.text = "unauthorized"
        with patch("kg_fuse.cli.httpx.post", return_value=mock_resp):
            ok, info = _test_auth("http://localhost:8000", "bad", "creds")
            assert ok is False
            assert "401" in info


class TestSystemdChecks:
    """Tests for systemd unit state detection."""

    def test_systemd_active_when_active(self):
        mock_result = MagicMock()
        mock_result.stdout = "active\n"
        with patch("kg_fuse.cli.subprocess.run", return_value=mock_result):
            assert _systemd_unit_active() is True

    def test_systemd_active_when_inactive(self):
        mock_result = MagicMock()
        mock_result.stdout = "inactive\n"
        with patch("kg_fuse.cli.subprocess.run", return_value=mock_result):
            assert _systemd_unit_active() is False

    def test_systemd_active_when_no_systemctl(self):
        with patch("kg_fuse.cli.subprocess.run", side_effect=FileNotFoundError):
            assert _systemd_unit_active() is False

    def test_systemd_enabled_when_enabled(self):
        mock_result = MagicMock()
        mock_result.stdout = "enabled\n"
        with patch("kg_fuse.cli.subprocess.run", return_value=mock_result):
            assert _systemd_unit_enabled() is True

    def test_systemd_enabled_when_disabled(self):
        mock_result = MagicMock()
        mock_result.stdout = "disabled\n"
        with patch("kg_fuse.cli.subprocess.run", return_value=mock_result):
            assert _systemd_unit_enabled() is False


class TestCmdStatusOutput:
    """Integration-style tests for cmd_status output."""

    def test_status_no_config(self, capsys):
        """When no config exists, should show setup guidance."""
        from kg_fuse.cli import cmd_status
        from kg_fuse.config import FuseConfig

        with patch("kg_fuse.cli.load_config", return_value=FuseConfig()), \
             patch("kg_fuse.cli.get_fuse_config_path") as mock_path, \
             patch("kg_fuse.cli.get_kg_config_path") as mock_kg_path, \
             patch("kg_fuse.cli._use_color", return_value=False):
            mock_path.return_value = MagicMock(exists=MagicMock(return_value=False))
            mock_kg_path.return_value = MagicMock(exists=MagicMock(return_value=True))

            cmd_status(Namespace())
            output = capsys.readouterr().out
            assert "No configuration found" in output
            assert "kg-fuse init" in output

    def test_status_with_mount(self, capsys):
        """When config has a mount, should show it."""
        from kg_fuse.cli import cmd_status
        from kg_fuse.config import FuseConfig, MountConfig

        cfg = FuseConfig(
            client_id="test-id",
            api_url="http://localhost:8000",
            mounts={"/mnt/test": MountConfig(path="/mnt/test")},
            daemon_mode="daemon",
        )

        with patch("kg_fuse.cli.load_config", return_value=cfg), \
             patch("kg_fuse.cli.get_fuse_config_path") as mock_fuse, \
             patch("kg_fuse.cli.get_kg_config_path") as mock_kg, \
             patch("kg_fuse.cli.mount_status", return_value={"running": False, "pid": None, "orphaned": False}), \
             patch("kg_fuse.cli.find_kg_fuse_processes", return_value=[]), \
             patch("kg_fuse.cli._systemd_unit_enabled", return_value=False), \
             patch("kg_fuse.cli._systemd_unit_active", return_value=False), \
             patch("kg_fuse.cli.get_systemd_unit_path") as mock_unit, \
             patch("kg_fuse.cli._test_api", return_value=(True, "1.0")), \
             patch("kg_fuse.cli.find_all_fuse_mounts", return_value=[]), \
             patch("kg_fuse.cli.shutil.which", return_value="/usr/bin/fusermount3"), \
             patch("kg_fuse.cli.has_systemd", return_value=False), \
             patch("kg_fuse.cli._use_color", return_value=False):
            mock_fuse.return_value = MagicMock(exists=MagicMock(return_value=True))
            mock_kg.return_value = MagicMock(exists=MagicMock(return_value=True))
            mock_unit.return_value = MagicMock(exists=MagicMock(return_value=False))

            cmd_status(Namespace())
            output = capsys.readouterr().out
            assert "/mnt/test" in output
            assert "stopped" in output
            assert "test-id" in output

    def test_status_shows_systemd_mode(self, capsys):
        """When daemon_mode=systemd, status should reflect it."""
        from kg_fuse.cli import cmd_status
        from kg_fuse.config import FuseConfig, MountConfig

        cfg = FuseConfig(
            client_id="test-id",
            api_url="http://localhost:8000",
            mounts={"/mnt/test": MountConfig(path="/mnt/test")},
            daemon_mode="systemd",
        )

        with patch("kg_fuse.cli.load_config", return_value=cfg), \
             patch("kg_fuse.cli.get_fuse_config_path") as mock_fuse, \
             patch("kg_fuse.cli.get_kg_config_path") as mock_kg, \
             patch("kg_fuse.cli.mount_status", return_value={"running": False, "pid": None, "orphaned": False}), \
             patch("kg_fuse.cli.find_kg_fuse_processes", return_value=[]), \
             patch("kg_fuse.cli._systemd_unit_enabled", return_value=True), \
             patch("kg_fuse.cli._systemd_unit_active", return_value=True), \
             patch("kg_fuse.cli.get_systemd_unit_path") as mock_unit, \
             patch("kg_fuse.cli._test_api", return_value=(True, "1.0")), \
             patch("kg_fuse.cli.find_all_fuse_mounts", return_value=[]), \
             patch("kg_fuse.cli.shutil.which", return_value="/usr/bin/fusermount3"), \
             patch("kg_fuse.cli.has_systemd", return_value=True), \
             patch("kg_fuse.cli.set_daemon_mode"), \
             patch("kg_fuse.cli._use_color", return_value=False):
            mock_fuse.return_value = MagicMock(exists=MagicMock(return_value=True))
            mock_kg.return_value = MagicMock(exists=MagicMock(return_value=True))
            mock_unit.return_value = MagicMock(exists=MagicMock(return_value=True))

            cmd_status(Namespace())
            output = capsys.readouterr().out
            assert "systemd user service" in output
            assert "active" in output


class TestResolveDaemonMode:
    """Tests for daemon mode resolution logic."""

    def test_returns_systemd_when_configured(self):
        from kg_fuse.config import FuseConfig
        cfg = FuseConfig(daemon_mode="systemd")
        with patch("kg_fuse.cli.has_systemd", return_value=True), \
             patch("kg_fuse.cli.set_daemon_mode"):
            assert _resolve_daemon_mode(cfg) == "systemd"

    def test_returns_daemon_when_configured(self):
        from kg_fuse.config import FuseConfig
        cfg = FuseConfig(daemon_mode="daemon")
        with patch("kg_fuse.cli.has_systemd", return_value=True), \
             patch("kg_fuse.cli.set_daemon_mode"):
            assert _resolve_daemon_mode(cfg) == "daemon"

    def test_auto_detects_systemd(self):
        from kg_fuse.config import FuseConfig
        cfg = FuseConfig(daemon_mode="")
        with patch("kg_fuse.cli.has_systemd", return_value=True), \
             patch("kg_fuse.cli.set_daemon_mode") as mock_set:
            result = _resolve_daemon_mode(cfg)
            assert result == "systemd"
            mock_set.assert_called_once_with("systemd")

    def test_auto_detects_daemon_when_no_systemd(self):
        from kg_fuse.config import FuseConfig
        cfg = FuseConfig(daemon_mode="")
        with patch("kg_fuse.cli.has_systemd", return_value=False), \
             patch("kg_fuse.cli.set_daemon_mode") as mock_set:
            result = _resolve_daemon_mode(cfg)
            assert result == "daemon"
            mock_set.assert_called_once_with("daemon")

    def test_does_not_write_when_already_set(self):
        from kg_fuse.config import FuseConfig
        cfg = FuseConfig(daemon_mode="daemon")
        with patch("kg_fuse.cli.set_daemon_mode") as mock_set:
            _resolve_daemon_mode(cfg)
            mock_set.assert_not_called()
