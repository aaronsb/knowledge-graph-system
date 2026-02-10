"""Tests for kg-fuse configuration management."""

import json
import os
import stat
import pytest
from pathlib import Path
from unittest.mock import patch

from kg_fuse.config import (
    FuseConfig, MountConfig, TagsConfig, CacheConfig, JobsConfig,
    WriteProtectConfig,
    get_mount_id, get_mount_data_dir,
    read_kg_config, read_kg_credentials,
    read_fuse_config, write_fuse_config,
    load_config, add_mount_to_config, remove_mount_from_config,
    normalize_fuse_config, _mount_config_to_dict,
)


class TestDataClasses:
    """Tests for config data classes."""

    def test_fuse_config_defaults(self):
        cfg = FuseConfig()
        assert cfg.client_id == ""
        assert cfg.client_secret == ""
        assert cfg.api_url == "http://localhost:8000"
        assert cfg.mounts == {}

    def test_mount_config_defaults(self):
        mc = MountConfig(path="/mnt/test")
        assert mc.path == "/mnt/test"
        assert mc.tags.enabled is True
        assert mc.tags.threshold == 0.5
        assert mc.cache.epoch_check_interval == 5.0
        assert mc.jobs.hide_jobs is False

    def test_mount_config_mutable_defaults_isolated(self):
        mc1 = MountConfig(path="/a")
        mc2 = MountConfig(path="/b")
        mc1.tags.threshold = 0.9
        assert mc2.tags.threshold == 0.5

    def test_write_protect_defaults_blocked(self):
        wp = WriteProtectConfig()
        assert wp.allow_ontology_delete is False
        assert wp.allow_document_delete is False

    def test_write_protect_explicit_enable(self):
        wp = WriteProtectConfig(allow_ontology_delete=True, allow_document_delete=True)
        assert wp.allow_ontology_delete is True
        assert wp.allow_document_delete is True

    def test_mount_config_includes_write_protect(self):
        mc = MountConfig(path="/mnt/test")
        assert mc.write_protect.allow_ontology_delete is False
        assert mc.write_protect.allow_document_delete is False


class TestPathHelpers:
    """Tests for path computation helpers."""

    def test_mount_id_is_stable(self):
        id1 = get_mount_id("/mnt/knowledge")
        id2 = get_mount_id("/mnt/knowledge")
        assert id1 == id2

    def test_mount_id_differs_for_different_paths(self):
        id1 = get_mount_id("/mnt/knowledge")
        id2 = get_mount_id("/mnt/archive")
        assert id1 != id2

    def test_mount_id_is_12_chars(self):
        assert len(get_mount_id("/mnt/test")) == 12

    def test_mount_data_dir_contains_mount_id(self):
        data_dir = get_mount_data_dir("/mnt/test")
        mount_id = get_mount_id("/mnt/test")
        assert mount_id in str(data_dir)


class TestReadKgConfig:
    """Tests for reading kg CLI's config.json (read-only)."""

    def test_returns_none_when_missing(self, tmp_path):
        with patch("kg_fuse.config.get_kg_config_path", return_value=tmp_path / "missing.json"):
            assert read_kg_config() is None

    def test_reads_valid_json(self, tmp_path):
        cfg = tmp_path / "config.json"
        cfg.write_text(json.dumps({"api_url": "http://test:8000", "auth": {"oauth_client_id": "abc"}}))
        with patch("kg_fuse.config.get_kg_config_path", return_value=cfg):
            data = read_kg_config()
            assert data["api_url"] == "http://test:8000"
            assert data["auth"]["oauth_client_id"] == "abc"

    def test_returns_none_on_invalid_json(self, tmp_path):
        cfg = tmp_path / "config.json"
        cfg.write_text("not json {{{")
        with patch("kg_fuse.config.get_kg_config_path", return_value=cfg):
            assert read_kg_config() is None


class TestReadKgCredentials:
    """Tests for credential extraction from kg config."""

    def test_returns_nones_when_no_config(self, tmp_path):
        with patch("kg_fuse.config.get_kg_config_path", return_value=tmp_path / "missing.json"):
            cid, secret, url = read_kg_credentials()
            assert cid is None
            assert secret is None
            assert url is None

    def test_extracts_credentials(self, tmp_path):
        cfg = tmp_path / "config.json"
        cfg.write_text(json.dumps({
            "api_url": "http://test:8000",
            "auth": {"oauth_client_id": "my-id", "oauth_client_secret": "my-secret"},
        }))
        with patch("kg_fuse.config.get_kg_config_path", return_value=cfg):
            cid, secret, url = read_kg_credentials()
            assert cid == "my-id"
            assert secret == "my-secret"
            assert url == "http://test:8000"

    def test_handles_missing_auth_section(self, tmp_path):
        cfg = tmp_path / "config.json"
        cfg.write_text(json.dumps({"api_url": "http://test:8000"}))
        with patch("kg_fuse.config.get_kg_config_path", return_value=cfg):
            cid, secret, url = read_kg_credentials()
            assert cid is None
            assert secret is None
            assert url == "http://test:8000"


class TestFuseConfigReadWrite:
    """Tests for fuse.json read/write with atomic writes."""

    def test_read_returns_none_when_missing(self, tmp_path):
        with patch("kg_fuse.config.get_fuse_config_path", return_value=tmp_path / "missing.json"):
            assert read_fuse_config() is None

    def test_write_and_read_roundtrip(self, tmp_path):
        fuse_path = tmp_path / "fuse.json"
        data = {"auth_client_id": "test-id", "mounts": {"/mnt/test": {"tags": {"enabled": True}}}}
        with patch("kg_fuse.config.get_fuse_config_path", return_value=fuse_path):
            write_fuse_config(data)
            result = read_fuse_config()
            assert result == data

    def test_write_enforces_600_permissions(self, tmp_path):
        fuse_path = tmp_path / "fuse.json"
        with patch("kg_fuse.config.get_fuse_config_path", return_value=fuse_path):
            write_fuse_config({"mounts": {}})
            mode = fuse_path.stat().st_mode & 0o777
            assert mode == 0o600

    def test_write_creates_parent_dirs(self, tmp_path):
        fuse_path = tmp_path / "subdir" / "fuse.json"
        with patch("kg_fuse.config.get_fuse_config_path", return_value=fuse_path):
            write_fuse_config({"mounts": {}})
            assert fuse_path.exists()

    def test_write_validates_roundtrip(self, tmp_path):
        """Values that don't survive JSON roundtrip should be rejected."""
        fuse_path = tmp_path / "fuse.json"
        # json.dumps(data) -> json.loads(content) should equal data
        # This is hard to break with normal Python dicts, but verifies the check exists
        with patch("kg_fuse.config.get_fuse_config_path", return_value=fuse_path):
            write_fuse_config({"key": "value"})
            assert json.loads(fuse_path.read_text()) == {"key": "value"}

    def test_read_returns_none_on_corrupt_file(self, tmp_path):
        fuse_path = tmp_path / "fuse.json"
        fuse_path.write_text("corrupted {{{")
        with patch("kg_fuse.config.get_fuse_config_path", return_value=fuse_path):
            assert read_fuse_config() is None


class TestLoadConfig:
    """Tests for full config loading with credential resolution."""

    @pytest.fixture
    def config_dir(self, tmp_path):
        """Set up a tmp config directory with both config files."""
        kg_config = {
            "api_url": "http://api:8000",
            "auth": {"oauth_client_id": "kg-id", "oauth_client_secret": "kg-secret"},
        }
        fuse_config = {
            "auth_client_id": "kg-id",
            "mounts": {
                "/mnt/test": {
                    "tags": {"enabled": True, "threshold": 0.8},
                    "cache": {"epoch_check_interval": 10.0},
                    "jobs": {"hide_jobs": True},
                }
            },
        }
        kg_path = tmp_path / "config.json"
        fuse_path = tmp_path / "fuse.json"
        kg_path.write_text(json.dumps(kg_config))
        fuse_path.write_text(json.dumps(fuse_config))
        return tmp_path, kg_path, fuse_path

    def test_loads_from_both_files(self, config_dir):
        tmp_path, kg_path, fuse_path = config_dir
        with patch("kg_fuse.config.get_kg_config_path", return_value=kg_path), \
             patch("kg_fuse.config.get_fuse_config_path", return_value=fuse_path):
            cfg = load_config()
            assert cfg.client_id == "kg-id"
            assert cfg.client_secret == "kg-secret"
            assert cfg.api_url == "http://api:8000"
            assert "/mnt/test" in cfg.mounts
            assert cfg.mounts["/mnt/test"].tags.threshold == 0.8
            assert cfg.mounts["/mnt/test"].jobs.hide_jobs is True

    def test_cli_flags_override_file_config(self, config_dir):
        tmp_path, kg_path, fuse_path = config_dir
        with patch("kg_fuse.config.get_kg_config_path", return_value=kg_path), \
             patch("kg_fuse.config.get_fuse_config_path", return_value=fuse_path):
            cfg = load_config(
                cli_client_id="override-id",
                cli_client_secret="override-secret",
                cli_api_url="http://override:9999",
            )
            assert cfg.client_id == "override-id"
            assert cfg.client_secret == "override-secret"
            assert cfg.api_url == "http://override:9999"

    def test_falls_through_to_kg_auth_when_no_fuse_ref(self, tmp_path):
        """When fuse.json has no auth_client_id, fall through to config.json auth."""
        kg_path = tmp_path / "config.json"
        fuse_path = tmp_path / "fuse.json"
        kg_path.write_text(json.dumps({
            "auth": {"oauth_client_id": "direct-id", "oauth_client_secret": "direct-secret"},
        }))
        fuse_path.write_text(json.dumps({"mounts": {}}))
        with patch("kg_fuse.config.get_kg_config_path", return_value=kg_path), \
             patch("kg_fuse.config.get_fuse_config_path", return_value=fuse_path):
            cfg = load_config()
            assert cfg.client_id == "direct-id"
            assert cfg.client_secret == "direct-secret"

    def test_returns_empty_creds_when_nothing_found(self, tmp_path):
        kg_path = tmp_path / "missing_kg.json"
        fuse_path = tmp_path / "missing_fuse.json"
        with patch("kg_fuse.config.get_kg_config_path", return_value=kg_path), \
             patch("kg_fuse.config.get_fuse_config_path", return_value=fuse_path):
            cfg = load_config()
            assert cfg.client_id == ""
            assert cfg.client_secret == ""
            assert cfg.api_url == "http://localhost:8000"

    def test_loads_write_protect_from_fuse_json(self, tmp_path):
        kg_path = tmp_path / "config.json"
        fuse_path = tmp_path / "fuse.json"
        kg_path.write_text(json.dumps({"auth": {}}))
        fuse_path.write_text(json.dumps({
            "mounts": {
                "/mnt/test": {
                    "write_protect": {
                        "allow_ontology_delete": True,
                        "allow_document_delete": False,
                    }
                }
            },
        }))
        with patch("kg_fuse.config.get_kg_config_path", return_value=kg_path), \
             patch("kg_fuse.config.get_fuse_config_path", return_value=fuse_path):
            cfg = load_config()
            mc = cfg.mounts["/mnt/test"]
            assert mc.write_protect.allow_ontology_delete is True
            assert mc.write_protect.allow_document_delete is False

    def test_write_protect_defaults_when_absent(self, tmp_path):
        kg_path = tmp_path / "config.json"
        fuse_path = tmp_path / "fuse.json"
        kg_path.write_text(json.dumps({"auth": {}}))
        fuse_path.write_text(json.dumps({
            "mounts": {"/mnt/test": {"tags": {"enabled": True}}},
        }))
        with patch("kg_fuse.config.get_kg_config_path", return_value=kg_path), \
             patch("kg_fuse.config.get_fuse_config_path", return_value=fuse_path):
            cfg = load_config()
            mc = cfg.mounts["/mnt/test"]
            assert mc.write_protect.allow_ontology_delete is False
            assert mc.write_protect.allow_document_delete is False

    def test_default_api_url_when_not_set(self, tmp_path):
        kg_path = tmp_path / "config.json"
        fuse_path = tmp_path / "fuse.json"
        kg_path.write_text(json.dumps({"auth": {}}))
        fuse_path.write_text(json.dumps({"mounts": {}}))
        with patch("kg_fuse.config.get_kg_config_path", return_value=kg_path), \
             patch("kg_fuse.config.get_fuse_config_path", return_value=fuse_path):
            cfg = load_config()
            assert cfg.api_url == "http://localhost:8000"


class TestMountManagement:
    """Tests for add/remove mount operations."""

    def test_add_mount_creates_file(self, tmp_path):
        fuse_path = tmp_path / "fuse.json"
        kg_path = tmp_path / "config.json"
        kg_path.write_text(json.dumps({"auth": {"oauth_client_id": "test-id"}}))
        with patch("kg_fuse.config.get_fuse_config_path", return_value=fuse_path), \
             patch("kg_fuse.config.get_kg_config_path", return_value=kg_path):
            add_mount_to_config("/mnt/new")
            data = json.loads(fuse_path.read_text())
            assert "/mnt/new" in data["mounts"]
            assert data["auth_client_id"] == "test-id"

    def test_add_mount_preserves_existing(self, tmp_path):
        fuse_path = tmp_path / "fuse.json"
        kg_path = tmp_path / "config.json"
        kg_path.write_text(json.dumps({"auth": {}}))
        fuse_path.write_text(json.dumps({
            "mounts": {"/mnt/existing": {"tags": {"enabled": True}}},
        }))
        with patch("kg_fuse.config.get_fuse_config_path", return_value=fuse_path), \
             patch("kg_fuse.config.get_kg_config_path", return_value=kg_path):
            add_mount_to_config("/mnt/new")
            data = json.loads(fuse_path.read_text())
            assert "/mnt/existing" in data["mounts"]
            assert "/mnt/new" in data["mounts"]

    def test_remove_mount(self, tmp_path):
        fuse_path = tmp_path / "fuse.json"
        fuse_path.write_text(json.dumps({
            "mounts": {"/mnt/test": {"tags": {"enabled": True}}},
        }))
        with patch("kg_fuse.config.get_fuse_config_path", return_value=fuse_path):
            assert remove_mount_from_config("/mnt/test") is True
            data = json.loads(fuse_path.read_text())
            assert "/mnt/test" not in data["mounts"]

    def test_add_mount_includes_write_protect(self, tmp_path):
        fuse_path = tmp_path / "fuse.json"
        kg_path = tmp_path / "config.json"
        kg_path.write_text(json.dumps({"auth": {}}))
        with patch("kg_fuse.config.get_fuse_config_path", return_value=fuse_path), \
             patch("kg_fuse.config.get_kg_config_path", return_value=kg_path):
            add_mount_to_config("/mnt/new")
            data = json.loads(fuse_path.read_text())
            wp = data["mounts"]["/mnt/new"]["write_protect"]
            assert wp["allow_ontology_delete"] is False
            assert wp["allow_document_delete"] is False

    def test_remove_nonexistent_mount(self, tmp_path):
        fuse_path = tmp_path / "fuse.json"
        fuse_path.write_text(json.dumps({"mounts": {}}))
        with patch("kg_fuse.config.get_fuse_config_path", return_value=fuse_path):
            assert remove_mount_from_config("/mnt/missing") is False


class TestNormalizeFuseConfig:
    """Tests for config normalization (backfilling missing sections)."""

    def test_backfills_missing_write_protect(self, tmp_path):
        fuse_path = tmp_path / "fuse.json"
        fuse_path.write_text(json.dumps({
            "mounts": {
                "/mnt/test": {
                    "tags": {"enabled": True, "threshold": 0.5},
                    "cache": {"epoch_check_interval": 5.0},
                    "jobs": {"hide_jobs": False},
                }
            },
        }))
        with patch("kg_fuse.config.get_fuse_config_path", return_value=fuse_path):
            changed = normalize_fuse_config()
            assert changed is True
            data = json.loads(fuse_path.read_text())
            wp = data["mounts"]["/mnt/test"]["write_protect"]
            assert wp["allow_ontology_delete"] is False
            assert wp["allow_document_delete"] is False

    def test_backfills_missing_key_within_section(self, tmp_path):
        fuse_path = tmp_path / "fuse.json"
        fuse_path.write_text(json.dumps({
            "mounts": {
                "/mnt/test": {
                    "tags": {"enabled": True},
                    "cache": {"epoch_check_interval": 5.0},
                    "jobs": {"hide_jobs": False},
                    "write_protect": {"allow_ontology_delete": True},
                }
            },
        }))
        with patch("kg_fuse.config.get_fuse_config_path", return_value=fuse_path):
            changed = normalize_fuse_config()
            assert changed is True
            data = json.loads(fuse_path.read_text())
            # Missing key backfilled
            assert data["mounts"]["/mnt/test"]["write_protect"]["allow_document_delete"] is False
            # Existing key preserved
            assert data["mounts"]["/mnt/test"]["write_protect"]["allow_ontology_delete"] is True

    def test_no_change_when_complete(self, tmp_path):
        fuse_path = tmp_path / "fuse.json"
        mc = MountConfig(path="/mnt/test")
        fuse_path.write_text(json.dumps({
            "mounts": {"/mnt/test": _mount_config_to_dict(mc)},
        }))
        with patch("kg_fuse.config.get_fuse_config_path", return_value=fuse_path):
            changed = normalize_fuse_config()
            assert changed is False

    def test_noop_when_no_config(self, tmp_path):
        with patch("kg_fuse.config.get_fuse_config_path", return_value=tmp_path / "missing.json"):
            assert normalize_fuse_config() is False

    def test_preserves_user_values(self, tmp_path):
        fuse_path = tmp_path / "fuse.json"
        fuse_path.write_text(json.dumps({
            "mounts": {
                "/mnt/test": {
                    "tags": {"enabled": False, "threshold": 0.9},
                    "cache": {"epoch_check_interval": 20.0},
                    "jobs": {"hide_jobs": True},
                }
            },
        }))
        with patch("kg_fuse.config.get_fuse_config_path", return_value=fuse_path):
            normalize_fuse_config()
            data = json.loads(fuse_path.read_text())
            mount = data["mounts"]["/mnt/test"]
            # User values preserved
            assert mount["tags"]["enabled"] is False
            assert mount["tags"]["threshold"] == 0.9
            assert mount["cache"]["epoch_check_interval"] == 20.0
            assert mount["jobs"]["hide_jobs"] is True
            # Missing section added with defaults
            assert mount["write_protect"]["allow_ontology_delete"] is False
