#!/usr/bin/env python3
"""
Knowledge Graph FUSE Driver

Mounts the knowledge graph as a filesystem.

Usage:
    kg-fuse /mnt/knowledge --api-url http://localhost:8000 --client-id fuse --client-secret secret
"""

import argparse
import logging
import sys

import pyfuse3
import trio

from .filesystem import KnowledgeGraphFS

log = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Mount knowledge graph as FUSE filesystem"
    )
    parser.add_argument(
        "mountpoint",
        help="Directory to mount the filesystem",
    )
    parser.add_argument(
        "--api-url",
        default="http://localhost:8000",
        help="Knowledge graph API URL (default: http://localhost:8000)",
    )
    parser.add_argument(
        "--client-id",
        required=True,
        help="OAuth client ID",
    )
    parser.add_argument(
        "--client-secret",
        required=True,
        help="OAuth client secret",
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

    # Setup logging
    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    # Create filesystem
    fs = KnowledgeGraphFS(
        api_url=args.api_url,
        client_id=args.client_id,
        client_secret=args.client_secret,
    )

    # FUSE options
    fuse_options = set(pyfuse3.default_options)
    fuse_options.add("fsname=kg-fuse")
    if args.debug:
        fuse_options.add("debug")

    log.info(f"Mounting knowledge graph at {args.mountpoint}")
    log.info(f"API: {args.api_url}")

    pyfuse3.init(fs, args.mountpoint, fuse_options)

    try:
        trio.run(pyfuse3.main)
    except KeyboardInterrupt:
        log.info("Interrupted, unmounting...")
    finally:
        pyfuse3.close(unmount=True)
        log.info("Unmounted")


if __name__ == "__main__":
    main()
