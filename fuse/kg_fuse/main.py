#!/usr/bin/env python3
"""
Knowledge Graph FUSE Driver

Mounts the knowledge graph as a filesystem.

Usage:
    kg-fuse /mnt/knowledge                          # Uses config file
    kg-fuse /mnt/knowledge --client-id X --client-secret Y  # Override config
"""

import argparse
import logging
import sys
from importlib.metadata import version, PackageNotFoundError

import pyfuse3
import trio

from .config import load_config, get_config_path, TagsConfig, JobsConfig, CacheConfig
from .filesystem import KnowledgeGraphFS


def get_version() -> str:
    """Get package version from installed metadata."""
    try:
        return version("kg-fuse")
    except PackageNotFoundError:
        return "dev"

log = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Mount knowledge graph as FUSE filesystem",
        epilog=f"Config file: {get_config_path()}\nCreate with: kg oauth create --for fuse",
    )
    parser.add_argument(
        "--version", "-V",
        action="version",
        version=f"kg-fuse {get_version()}",
    )
    parser.add_argument(
        "mountpoint",
        nargs="?",  # Optional when --version is used
        help="Directory to mount the filesystem",
    )
    parser.add_argument(
        "--api-url",
        help="Knowledge graph API URL (default: from config or http://localhost:8000)",
    )
    parser.add_argument(
        "--client-id",
        help="OAuth client ID (default: from config file)",
    )
    parser.add_argument(
        "--client-secret",
        help="OAuth client secret (default: from config file)",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging",
    )
    parser.add_argument(
        "--foreground", "-f",
        action="store_true",
        help="Run in foreground (don't daemonize)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    # Mountpoint is required unless --version was used (which exits before here)
    if not args.mountpoint:
        print("Error: mountpoint is required", file=sys.stderr)
        print("Usage: kg-fuse MOUNTPOINT [options]", file=sys.stderr)
        sys.exit(1)

    # Setup logging
    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    # Load config from file, allow CLI overrides
    config = load_config()

    client_id = args.client_id
    client_secret = args.client_secret
    api_url = args.api_url

    # Use config file values if not provided on CLI
    if config:
        if not client_id:
            client_id = config.client_id
        if not client_secret:
            client_secret = config.client_secret
        if not api_url:
            api_url = config.api_url

    # Default API URL
    if not api_url:
        api_url = "http://localhost:8000"

    # Validate we have credentials
    if not client_id or not client_secret:
        config_path = get_config_path()
        log.error(f"No OAuth credentials found.")
        log.error(f"")
        log.error(f"Either:")
        log.error(f"  1. Create config: kg oauth create --for fuse")
        log.error(f"  2. Pass on CLI: --client-id ID --client-secret SECRET")
        log.error(f"")
        log.error(f"Config file location: {config_path}")
        sys.exit(1)

    # Get configs (or use defaults)
    tags_config = config.tags if config else TagsConfig()
    jobs_config = config.jobs if config else JobsConfig()
    cache_config = config.cache if config else CacheConfig()

    # Create filesystem
    fs = KnowledgeGraphFS(
        api_url=api_url,
        client_id=client_id,
        client_secret=client_secret,
        tags_config=tags_config,
        jobs_config=jobs_config,
        cache_config=cache_config,
    )

    # FUSE options
    fuse_options = set(pyfuse3.default_options)
    fuse_options.add("fsname=kg-fuse")
    if args.debug:
        fuse_options.add("debug")

    log.info(f"Mounting knowledge graph at {args.mountpoint}")
    log.info(f"API: {api_url}")

    pyfuse3.init(fs, args.mountpoint, fuse_options)

    async def _run():
        async with trio.open_nursery() as nursery:
            fs.set_nursery(nursery)
            await pyfuse3.main()

    try:
        trio.run(_run)
    except KeyboardInterrupt:
        log.info("Interrupted, unmounting...")
    finally:
        pyfuse3.close(unmount=True)
        log.info("Unmounted")


if __name__ == "__main__":
    main()
