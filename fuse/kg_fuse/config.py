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
class FuseConfig:
    """FUSE driver configuration"""
    client_id: str
    client_secret: str
    api_url: str = "http://localhost:8000"


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

    client_id = auth.get("client_id")
    client_secret = auth.get("client_secret")

    if not client_id or not client_secret:
        raise ValueError(f"Missing client_id or client_secret in {config_path}")

    return FuseConfig(
        client_id=client_id,
        client_secret=client_secret,
        api_url=api.get("url", "http://localhost:8000"),
    )
