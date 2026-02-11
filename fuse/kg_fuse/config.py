"""
Configuration management for kg-fuse.

Two-file config model:
  ~/.config/kg/config.json  — kg CLI owns (read-only for kg-fuse): auth, api_url
  ~/.config/kg/fuse.json    — kg-fuse owns (read/write): mounts, preferences

Credential resolution (highest → lowest):
  1. CLI flags (--client-id, --client-secret)
  2. fuse.json auth_client_id → lookup in config.json auth
  3. config.json auth section directly
  4. Error with guidance
"""

import fcntl
import hashlib
import json
import logging
import os
import stat
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)


# --- Data classes ---

@dataclass
class TagsConfig:
    """Tag generation settings for YAML frontmatter (Obsidian, Logseq, etc.)"""
    enabled: bool = True
    threshold: float = 0.5

@dataclass
class JobsConfig:
    """Job visibility settings for ingestion tracking."""
    hide_jobs: bool = False

    def format_job_filename(self, filename: str) -> str:
        """Format a job filename with .ingesting suffix and optional dot prefix."""
        if self.hide_jobs:
            return f".{filename}.ingesting"
        return f"{filename}.ingesting"

@dataclass
class CacheConfig:
    """Cache invalidation settings for epoch-gated caching."""
    epoch_check_interval: float = 5.0
    dir_cache_ttl: float = 30.0
    content_cache_max: int = 50 * 1024 * 1024

@dataclass
class WriteProtectConfig:
    """Write protection to prevent accidental deletion via FUSE.

    Both default to False (blocked). Users must explicitly enable
    deletion in fuse.json to allow rm/rmdir on ontologies and documents.
    """
    allow_ontology_delete: bool = False
    allow_document_delete: bool = False

@dataclass
class MountConfig:
    """Configuration for a single FUSE mount point."""
    path: str
    tags: TagsConfig = field(default_factory=TagsConfig)
    cache: CacheConfig = field(default_factory=CacheConfig)
    jobs: JobsConfig = field(default_factory=JobsConfig)
    write_protect: WriteProtectConfig = field(default_factory=WriteProtectConfig)

@dataclass
class FuseConfig:
    """Full kg-fuse configuration (from fuse.json + config.json)."""
    # Auth (resolved from config.json)
    client_id: str = ""
    client_secret: str = ""
    api_url: str = "http://localhost:8000"
    # Mount definitions
    mounts: dict[str, MountConfig] = field(default_factory=dict)
    # Which auth client to use (references config.json auth)
    auth_client_id: str = ""
    # Daemon mode: "systemd" or "daemon" (empty = auto-detect on first use)
    daemon_mode: str = ""


# --- Path helpers ---

def get_kg_config_dir() -> Path:
    """Get kg config directory (~/.config/kg/)."""
    xdg_config = os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config"))
    return Path(xdg_config) / "kg"

def get_kg_config_path() -> Path:
    """Get path to kg CLI's config.json (read-only for kg-fuse)."""
    return get_kg_config_dir() / "config.json"

def get_fuse_config_path() -> Path:
    """Get path to kg-fuse's own config file."""
    return get_kg_config_dir() / "fuse.json"

def get_fuse_data_dir() -> Path:
    """Get XDG data directory for kg-fuse runtime state."""
    xdg_data = os.environ.get("XDG_DATA_HOME", os.path.expanduser("~/.local/share"))
    return Path(xdg_data) / "kg-fuse"

def get_fuse_state_dir() -> Path:
    """Get XDG state directory for kg-fuse PID files."""
    xdg_state = os.environ.get("XDG_STATE_HOME", os.path.expanduser("~/.local/state"))
    return Path(xdg_state) / "kg-fuse"

def get_mount_id(mountpoint: str) -> str:
    """Stable short hash of mountpoint path for per-mount data dirs."""
    return hashlib.sha256(mountpoint.encode()).hexdigest()[:12]

def get_mount_data_dir(mountpoint: str) -> Path:
    """Get per-mount data directory for query store etc."""
    return get_fuse_data_dir() / "mounts" / get_mount_id(mountpoint)


# --- Read kg CLI config (read-only) ---

def read_kg_config() -> Optional[dict]:
    """Read kg CLI's config.json. Returns None if not found."""
    path = get_kg_config_path()
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError) as e:
        log.warning(f"Could not read kg config at {path}: {e}")
        return None

def read_kg_credentials() -> tuple[Optional[str], Optional[str], Optional[str]]:
    """Read OAuth credentials from kg CLI's config.json.

    Returns (client_id, client_secret, api_url). Any may be None.
    """
    data = read_kg_config()
    if data is None:
        return None, None, None
    auth = data.get("auth", {})
    return (
        auth.get("oauth_client_id"),
        auth.get("oauth_client_secret"),
        data.get("api_url"),
    )


# --- Read/write fuse.json (kg-fuse owns this) ---

def read_fuse_config() -> Optional[dict]:
    """Read fuse.json. Returns None if not found."""
    path = get_fuse_config_path()
    if not path.exists():
        return None
    try:
        with open(path, "r") as f:
            fcntl.flock(f, fcntl.LOCK_SH)
            try:
                return json.load(f)
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)
    except (json.JSONDecodeError, OSError) as e:
        log.warning(f"Could not read fuse config at {path}: {e}")
        return None

def write_fuse_config(data: dict) -> None:
    """Atomic write to fuse.json with file locking.

    Writes to a temp file, validates the roundtrip, then renames atomically.
    The flock is held through the rename to prevent concurrent writers from
    seeing a partially-written state. Enforces 600 permissions.
    """
    path = get_fuse_config_path()
    tmp_path = path.with_suffix(".tmp")

    path.parent.mkdir(parents=True, exist_ok=True)

    # Serialize and validate roundtrip before writing
    content = json.dumps(data, indent=2) + "\n"
    roundtrip = json.loads(content)
    if roundtrip != data:
        raise ValueError("JSON roundtrip validation failed — refusing to write")

    # Write to temp file with exclusive lock held through rename
    with open(tmp_path, "w") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
            # Rename while still holding the lock — atomic on same filesystem
            os.rename(tmp_path, path)
            os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)  # 600
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


# --- High-level config loading ---

def load_config(
    cli_client_id: Optional[str] = None,
    cli_client_secret: Optional[str] = None,
    cli_api_url: Optional[str] = None,
) -> FuseConfig:
    """Load full FUSE config with credential resolution.

    Priority:
      1. CLI flags
      2. fuse.json auth_client_id → config.json auth
      3. config.json auth directly
      4. Empty (caller should handle missing creds)
    """
    config = FuseConfig()

    # Read kg CLI config (auth + api_url)
    kg_data = read_kg_config()
    kg_auth = kg_data.get("auth", {}) if kg_data else {}
    kg_api_url = kg_data.get("api_url") if kg_data else None

    # Read fuse config (mounts + preferences), backfilling missing sections
    normalize_fuse_config()
    fuse_data = read_fuse_config()

    # Daemon mode
    if fuse_data:
        config.daemon_mode = fuse_data.get("daemon_mode", "")

    # Parse mounts from fuse.json
    if fuse_data:
        config.auth_client_id = fuse_data.get("auth_client_id", "")
        for mount_path, mount_data in fuse_data.get("mounts", {}).items():
            tags_data = mount_data.get("tags", {})
            cache_data = mount_data.get("cache", {})
            jobs_data = mount_data.get("jobs", {})
            wp_data = mount_data.get("write_protect", {})
            config.mounts[mount_path] = MountConfig(
                path=mount_path,
                tags=TagsConfig(
                    enabled=tags_data.get("enabled", True),
                    threshold=tags_data.get("threshold", 0.5),
                ),
                cache=CacheConfig(
                    epoch_check_interval=cache_data.get("epoch_check_interval", 5.0),
                    dir_cache_ttl=cache_data.get("dir_cache_ttl", 30.0),
                    content_cache_max=cache_data.get("content_cache_max", 50 * 1024 * 1024),
                ),
                jobs=JobsConfig(
                    hide_jobs=jobs_data.get("hide_jobs", False),
                ),
                write_protect=WriteProtectConfig(
                    allow_ontology_delete=wp_data.get("allow_ontology_delete", False),
                    allow_document_delete=wp_data.get("allow_document_delete", False),
                ),
            )

    # Resolve credentials: CLI flags > fuse.json ref > config.json auth
    if cli_client_id and cli_client_secret:
        config.client_id = cli_client_id
        config.client_secret = cli_client_secret
    elif config.auth_client_id and config.auth_client_id == kg_auth.get("oauth_client_id"):
        config.client_id = kg_auth.get("oauth_client_id", "")
        config.client_secret = kg_auth.get("oauth_client_secret", "")
    elif kg_auth.get("oauth_client_id"):
        config.client_id = kg_auth.get("oauth_client_id", "")
        config.client_secret = kg_auth.get("oauth_client_secret", "")

    # Resolve API URL: CLI flag > config.json > default
    config.api_url = cli_api_url or kg_api_url or "http://localhost:8000"

    return config


def _mount_config_to_dict(mc: MountConfig) -> dict:
    """Serialize a MountConfig to a JSON-safe dict. Single source of truth."""
    return {
        "tags": {"enabled": mc.tags.enabled, "threshold": mc.tags.threshold},
        "cache": {
            "epoch_check_interval": mc.cache.epoch_check_interval,
            "dir_cache_ttl": mc.cache.dir_cache_ttl,
            "content_cache_max": mc.cache.content_cache_max,
        },
        "jobs": {"hide_jobs": mc.jobs.hide_jobs},
        "write_protect": {
            "allow_ontology_delete": mc.write_protect.allow_ontology_delete,
            "allow_document_delete": mc.write_protect.allow_document_delete,
        },
    }


def normalize_fuse_config() -> bool:
    """Backfill missing config sections with defaults. Returns True if file was updated."""
    fuse_data = read_fuse_config()
    if not fuse_data or "mounts" not in fuse_data:
        return False

    changed = False
    default_dict = _mount_config_to_dict(MountConfig(path=""))

    for mount_path, mount_data in fuse_data["mounts"].items():
        for section_key, section_defaults in default_dict.items():
            if section_key not in mount_data:
                mount_data[section_key] = section_defaults
                changed = True
            elif isinstance(section_defaults, dict):
                # Backfill missing keys within existing sections
                for k, v in section_defaults.items():
                    if k not in mount_data[section_key]:
                        mount_data[section_key][k] = v
                        changed = True

    if changed:
        write_fuse_config(fuse_data)
        log.info("Backfilled missing config sections with defaults")
    return changed


def add_mount_to_config(mountpoint: str, mount_config: Optional[MountConfig] = None) -> None:
    """Add a mount to fuse.json. Creates the file if it doesn't exist."""
    fuse_data = read_fuse_config() or {}

    if "mounts" not in fuse_data:
        fuse_data["mounts"] = {}

    mc = mount_config or MountConfig(path=mountpoint)
    fuse_data["mounts"][mountpoint] = _mount_config_to_dict(mc)

    # Set auth_client_id if not already set
    if "auth_client_id" not in fuse_data or not fuse_data["auth_client_id"]:
        kg_client_id, _, _ = read_kg_credentials()
        if kg_client_id:
            fuse_data["auth_client_id"] = kg_client_id

    write_fuse_config(fuse_data)


def remove_mount_from_config(mountpoint: str) -> bool:
    """Remove a mount from fuse.json. Returns True if found and removed."""
    fuse_data = read_fuse_config()
    if not fuse_data or mountpoint not in fuse_data.get("mounts", {}):
        return False

    del fuse_data["mounts"][mountpoint]
    write_fuse_config(fuse_data)
    return True


def set_daemon_mode(mode: str) -> None:
    """Set daemon_mode in fuse.json. Creates the file if needed."""
    fuse_data = read_fuse_config() or {}
    fuse_data["daemon_mode"] = mode
    write_fuse_config(fuse_data)
