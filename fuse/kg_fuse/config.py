"""
Configuration management for kg-fuse

Reads from ~/.config/kg-fuse/config.toml (XDG standard)
"""

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class TagsConfig:
    """Tag generation settings for YAML frontmatter (Obsidian, Logseq, etc.)"""
    enabled: bool = True
    threshold: float = 0.5  # Min similarity for related concepts to include as tags


@dataclass
class JobsConfig:
    """Job visibility settings for ingestion tracking"""
    hide_jobs: bool = False  # If true, use dot prefix (hidden in file managers)
                             # If false, no prefix (visible)

    def format_job_filename(self, filename: str) -> str:
        """Format a job filename with .ingesting suffix and optional dot prefix"""
        if self.hide_jobs:
            return f".{filename}.ingesting"
        else:
            return f"{filename}.ingesting"


@dataclass
class CacheConfig:
    """Cache invalidation settings for epoch-gated caching"""
    epoch_check_interval: float = 5.0   # Seconds between epoch API polls
    dir_cache_ttl: float = 30.0         # Fallback TTL for directory listings (safety net)
    content_cache_max: int = 50 * 1024 * 1024  # Content cache budget in bytes (50MB)


@dataclass
class FuseConfig:
    """FUSE driver configuration"""
    client_id: str
    client_secret: str
    api_url: str = "http://localhost:8000"
    tags: TagsConfig = None
    jobs: JobsConfig = None
    cache: CacheConfig = None

    def __post_init__(self):
        if self.tags is None:
            self.tags = TagsConfig()
        if self.jobs is None:
            self.jobs = JobsConfig()
        if self.cache is None:
            self.cache = CacheConfig()


def get_config_path() -> Path:
    """Get path to config file (XDG standard)"""
    xdg_config = os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config"))
    return Path(xdg_config) / "kg-fuse" / "config.toml"


def load_config() -> Optional[FuseConfig]:
    """
    Load configuration from file.

    Returns None if config file doesn't exist.
    Raises ValueError if config is invalid.
    """
    config_path = get_config_path()

    if not config_path.exists():
        return None

    with open(config_path, "rb") as f:
        data = tomllib.load(f)

    auth = data.get("auth", {})
    api = data.get("api", {})
    tags_data = data.get("tags", {})
    jobs_data = data.get("jobs", {})
    cache_data = data.get("cache", {})

    client_id = auth.get("client_id")
    client_secret = auth.get("client_secret")

    if not client_id or not client_secret:
        raise ValueError(f"Missing client_id or client_secret in {config_path}")

    # Parse tags config
    tags = TagsConfig(
        enabled=tags_data.get("enabled", False),
        threshold=tags_data.get("threshold", 0.5),
    )

    # Parse jobs config
    jobs = JobsConfig(
        hide_jobs=jobs_data.get("hide_jobs", False),
    )

    # Parse cache config
    cache = CacheConfig(
        epoch_check_interval=cache_data.get("epoch_check_interval", 5.0),
        dir_cache_ttl=cache_data.get("dir_cache_ttl", 30.0),
        content_cache_max=cache_data.get("content_cache_max", 50 * 1024 * 1024),
    )

    return FuseConfig(
        client_id=client_id,
        client_secret=client_secret,
        api_url=api.get("url", "http://localhost:8000"),
        tags=tags,
        jobs=jobs,
        cache=cache,
    )
