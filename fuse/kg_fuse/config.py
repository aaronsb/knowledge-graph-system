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
    enabled: bool = False
    threshold: float = 0.5  # Min similarity for related concepts to include as tags


@dataclass
class FuseConfig:
    """FUSE driver configuration"""
    client_id: str
    client_secret: str
    api_url: str = "http://localhost:8000"
    tags: TagsConfig = None

    def __post_init__(self):
        if self.tags is None:
            self.tags = TagsConfig()


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

    client_id = auth.get("client_id")
    client_secret = auth.get("client_secret")

    if not client_id or not client_secret:
        raise ValueError(f"Missing client_id or client_secret in {config_path}")

    # Parse tags config
    tags = TagsConfig(
        enabled=tags_data.get("enabled", False),
        threshold=tags_data.get("threshold", 0.5),
    )

    return FuseConfig(
        client_id=client_id,
        client_secret=client_secret,
        api_url=api.get("url", "http://localhost:8000"),
        tags=tags,
    )
