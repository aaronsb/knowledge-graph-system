#!/usr/bin/env python3
"""
Knowledge Graph FUSE Driver

Multi-command CLI for mounting and managing FUSE filesystems
backed by the knowledge graph API.

Usage:
    kg-fuse                          # Status + help
    kg-fuse init /mnt/knowledge      # Interactive setup
    kg-fuse mount                    # Mount all configured
    kg-fuse mount /mnt/knowledge     # Mount one
    kg-fuse unmount                  # Unmount all
    kg-fuse status                   # Same as bare kg-fuse
    kg-fuse config                   # Show configuration
    kg-fuse repair                   # Fix orphaned mounts
    kg-fuse update                   # Self-update via pipx
"""

import argparse
import sys
from importlib.metadata import version, PackageNotFoundError


def get_version() -> str:
    """Get package version from installed metadata."""
    try:
        return version("kg-fuse")
    except PackageNotFoundError:
        return "dev"


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="kg-fuse",
        description="Knowledge Graph FUSE Driver",
        epilog="Run 'kg-fuse' with no arguments for status overview.",
    )
    parser.add_argument(
        "--version", "-V",
        action="version",
        version=f"kg-fuse {get_version()}",
    )

    subparsers = parser.add_subparsers(dest="command")

    # --- mount ---
    mount_parser = subparsers.add_parser(
        "mount", help="Mount filesystem(s)",
        description="Mount one or all configured FUSE filesystems.",
    )
    mount_parser.add_argument(
        "mountpoint", nargs="?",
        help="Mount point (omit to mount all configured)",
    )
    mount_parser.add_argument("--api-url", help="API URL override")
    mount_parser.add_argument("--client-id", help="OAuth client ID override")
    mount_parser.add_argument("--client-secret", help="OAuth client secret override")
    mount_parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    mount_parser.add_argument(
        "--foreground", "-f", action="store_true",
        help="Run in foreground (don't daemonize)",
    )

    # --- init ---
    init_parser = subparsers.add_parser(
        "init", help="Set up a new FUSE mount",
        description="Interactive setup: detect auth, configure mount, offer autostart.",
    )
    init_parser.add_argument(
        "mountpoint", nargs="?", default="/mnt/knowledge",
        help="Mount point directory (default: /mnt/knowledge)",
    )
    init_parser.add_argument("--api-url", help="API URL override")

    # --- unmount ---
    unmount_parser = subparsers.add_parser(
        "unmount", help="Unmount filesystem(s)",
        description="Unmount one or all FUSE filesystems.",
    )
    unmount_parser.add_argument(
        "mountpoint", nargs="?",
        help="Mount point (omit to unmount all)",
    )

    # --- status ---
    subparsers.add_parser(
        "status", help="Show driver status",
        description="Show status of all configured mounts and system info.",
    )

    # --- config ---
    subparsers.add_parser(
        "config", help="Show configuration",
        description="Show current configuration with masked secrets.",
    )

    # --- repair ---
    subparsers.add_parser(
        "repair", help="Fix orphaned mounts / stale state",
        description="Detect and fix orphaned mounts, stale PIDs, and bad config.",
    )

    # --- update ---
    subparsers.add_parser(
        "update", help="Update kg-fuse via pipx",
    )

    args = parser.parse_args()

    # Bare kg-fuse (no subcommand) = status
    if not args.command:
        from .cli import cmd_status
        cmd_status(args)
        return

    # Dispatch to subcommand
    from .cli import (
        cmd_init, cmd_mount, cmd_unmount,
        cmd_status, cmd_config, cmd_repair, cmd_update,
    )

    commands = {
        "init": cmd_init,
        "mount": cmd_mount,
        "unmount": cmd_unmount,
        "status": cmd_status,
        "config": cmd_config,
        "repair": cmd_repair,
        "update": cmd_update,
    }

    commands[args.command](args)


if __name__ == "__main__":
    main()
