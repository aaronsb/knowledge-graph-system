"""
Subcommand implementations for kg-fuse CLI.

Commands: init, mount, unmount, status, config, repair, update.
"""

import json
import logging
import os
import shutil
import subprocess
import sys
from argparse import Namespace
from pathlib import Path

import httpx

from .config import (
    FuseConfig, MountConfig,
    get_kg_config_path, get_fuse_config_path, get_mount_data_dir,
    load_config, read_kg_config, read_kg_credentials,
    add_mount_to_config, read_fuse_config, write_fuse_config,
)
from .daemon import fork_mount, mount_status
from .safety import (
    validate_mountpoint, ensure_mountpoint,
    find_mounted_fuse, find_all_fuse_mounts, find_kg_fuse_processes,
    is_mount_orphaned, fusermount_unmount,
    kill_mount_daemon, clear_pid,
    has_systemd, install_systemd_unit, get_systemd_unit_path,
    detect_shell, add_to_rc, remove_from_rc,
    check_config_permissions,
)

log = logging.getLogger(__name__)


def _get_version() -> str:
    """Get package version."""
    from importlib.metadata import version, PackageNotFoundError
    try:
        return version("kg-fuse")
    except PackageNotFoundError:
        return "dev"


def _test_api(api_url: str) -> tuple[bool, str]:
    """Test API connectivity. Returns (reachable, version_or_error)."""
    try:
        resp = httpx.get(f"{api_url}/health", timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            return True, data.get("version", "unknown")
        return False, f"HTTP {resp.status_code}"
    except httpx.ConnectError:
        return False, "connection refused"
    except Exception as e:
        return False, str(e)


def _test_auth(api_url: str, client_id: str, client_secret: str) -> tuple[bool, str]:
    """Test OAuth credentials. Returns (valid, username_or_error)."""
    try:
        resp = httpx.post(
            f"{api_url}/auth/oauth/token",
            data={
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": client_secret,
            },
            timeout=5,
        )
        if resp.status_code == 200:
            data = resp.json()
            return True, data.get("username", "authenticated")
        return False, f"HTTP {resp.status_code}: {resp.text[:100]}"
    except Exception as e:
        return False, str(e)


def _mask_secret(secret: str) -> str:
    """Mask a secret, showing only last 4 chars."""
    if len(secret) <= 4:
        return "****"
    return f"****{secret[-4:]}"


def _prompt_yn(question: str, default: bool = True) -> bool:
    """Prompt user for yes/no. Returns bool."""
    suffix = " [Y/n] " if default else " [y/N] "
    try:
        answer = input(question + suffix).strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return False
    if not answer:
        return default
    return answer in ("y", "yes")


# --- Subcommands ---

def cmd_status(args: Namespace) -> None:
    """Show status of all configured mounts + system info."""
    ver = _get_version()
    config = load_config()

    print(f"\nkg-fuse {ver}\n")

    # Check if fuse.json exists
    fuse_path = get_fuse_config_path()
    if not fuse_path.exists():
        kg_path = get_kg_config_path()
        print("No configuration found. Run:")
        print(f"  kg-fuse init /mnt/knowledge\n")
        if not kg_path.exists():
            print("Prerequisites:")
            print("  npm install -g @aaronsb/kg-cli")
            print("  kg login")
            print("  kg oauth create")
        return

    # Scan for all running kg-fuse daemon processes
    all_procs = find_kg_fuse_processes()
    # Filter out this status process itself
    my_pid = os.getpid()
    daemon_procs = [p for p in all_procs if p["pid"] != my_pid]

    # Collect PIDs that are accounted for by configured mounts
    accounted_pids = set()

    # Show mounts
    if config.mounts:
        print("Mounts:")
        for mount_path, mount_cfg in config.mounts.items():
            status = mount_status(mount_path)
            if status["pid"]:
                accounted_pids.add(status["pid"])
            if status["orphaned"]:
                state = "ORPHANED (run: kg-fuse repair)"
            elif status["running"]:
                state = f"mounted    pid {status['pid']}"
            else:
                state = "stopped"
            print(f"  {mount_path:<30s} {state}")
    else:
        print("Mounts: (none configured)")
        print("  Add one with: kg-fuse init /mnt/knowledge")

    # Check for unaccounted daemon processes (not tied to any configured mount)
    rogue_procs = [p for p in daemon_procs if p["pid"] not in accounted_pids]
    if rogue_procs:
        print(f"\n  WARNING: {len(rogue_procs)} kg-fuse process(es) not in config:")
        for p in rogue_procs:
            print(f"    pid {p['pid']}: {p['cmdline'][:80]}")
        print("  These may be leftover daemons. Use 'kg-fuse repair' to investigate.")

    # Daemon summary
    print()
    running_count = sum(
        1 for mp in config.mounts
        if mount_status(mp)["running"]
    )
    total_daemon_count = len(daemon_procs)
    if total_daemon_count == 0:
        print("Daemons: none running")
    else:
        print(f"Daemons: {total_daemon_count} process(es) running"
              f" ({running_count} configured mount(s) active)")

    # Auth info
    if config.client_id:
        print(f"Auth:   {config.client_id} (via {get_kg_config_path()})")
    else:
        print("Auth:   not configured")

    # API
    reachable, api_info = _test_api(config.api_url)
    if reachable:
        print(f"API:    {config.api_url} (v{api_info})")
    else:
        print(f"API:    {config.api_url} ({api_info})")

    # FUSE library
    fuse3_available = shutil.which("fusermount3") or shutil.which("fusermount")
    print(f"FUSE:   {'present' if fuse3_available else 'NOT FOUND'}")

    # Show other FUSE mounts on the system (collision awareness)
    all_fuse = find_all_fuse_mounts()
    other_fuse = [m for m in all_fuse if not m["is_ours"] and not m["is_system"]]
    if other_fuse:
        print(f"\nOther FUSE mounts on system:")
        for m in other_fuse:
            print(f"  {m['mountpoint']:<30s} {m['source']} ({m['fstype']})")

    # Commands hint
    print("\nCommands:")
    print("  kg-fuse mount              Mount all configured filesystems")
    print("  kg-fuse unmount            Unmount all")
    print("  kg-fuse init [path]        Add a new mount")
    print("  kg-fuse repair             Fix orphaned mounts / stale state")
    print("  kg-fuse config             Show configuration")
    print("  kg-fuse update             Update kg-fuse via pipx")
    print("  kg-fuse --help             Full help")
    print()


def cmd_init(args: Namespace) -> None:
    """Interactive setup: detect auth, configure mount, offer autostart."""
    mountpoint = os.path.realpath(args.mountpoint)
    api_url = args.api_url

    print(f"\nKnowledge Graph FUSE Driver Setup")
    print(f"{'=' * 34}\n")

    # Step 1: Check kg config exists
    kg_config = read_kg_config()
    if kg_config is None:
        kg_path = get_kg_config_path()
        print(f"No kg configuration found at {kg_path}\n")
        print("The kg CLI manages authentication for all kg tools.")
        print("Install and configure it first:\n")
        print("  npm install -g @aaronsb/kg-cli")
        print("  kg login")
        print("  kg oauth create")
        print(f"\nThen run kg-fuse init again.")
        sys.exit(1)

    # Step 2: Resolve API URL
    if not api_url:
        api_url = kg_config.get("api_url", "http://localhost:8000")

    # Step 3: Check API
    print(f"Checking API... ", end="", flush=True)
    reachable, api_info = _test_api(api_url)
    if reachable:
        print(f"OK  {api_url} (v{api_info})")
    else:
        print(f"FAILED  {api_url} ({api_info})")
        print("\nMake sure the knowledge graph platform is running.")
        print("  operator.sh start")
        sys.exit(1)

    # Step 4: Check auth
    print(f"Checking credentials... ", end="", flush=True)
    client_id, client_secret, _ = read_kg_credentials()

    if not client_id or not client_secret:
        print("MISSING\n")
        print(f"  No OAuth credentials in {get_kg_config_path()}\n")
        if _prompt_yn("  Run 'kg oauth create' now?"):
            try:
                subprocess.run(["kg", "oauth", "create"], check=True)
                # Re-read after creation
                client_id, client_secret, _ = read_kg_credentials()
                if not client_id:
                    print("\n  Credentials still missing after creation.")
                    sys.exit(1)
            except FileNotFoundError:
                print("\n  'kg' command not found. Install: npm install -g @aaronsb/kg-cli")
                sys.exit(1)
            except subprocess.CalledProcessError:
                print("\n  'kg oauth create' failed.")
                sys.exit(1)
        else:
            print("\n  Set up credentials first:")
            print("    kg login")
            print("    kg oauth create")
            sys.exit(1)

    # Test credentials
    auth_ok, auth_info = _test_auth(api_url, client_id, client_secret)
    if auth_ok:
        print(f"OK  {client_id}")
    else:
        print(f"FAILED  {auth_info}")
        print("\n  Credentials may be expired. Try:")
        print("    kg oauth create")
        sys.exit(1)

    # Step 5: Check credential permissions
    perm_warning = check_config_permissions(get_kg_config_path())
    if perm_warning:
        print(f"\n  {perm_warning}")

    # Step 6: Validate mountpoint
    print(f"\nMount point: {mountpoint}")

    # Check if already configured
    fuse_data = read_fuse_config() or {}
    if mountpoint in fuse_data.get("mounts", {}):
        print(f"  Already configured in fuse.json")
        if not _prompt_yn("  Reconfigure?", default=False):
            print("  Keeping existing config.")
            return

    error = validate_mountpoint(mountpoint)
    if error:
        print(f"\n  Error: {error}")
        sys.exit(1)

    # Create directory if needed
    err = ensure_mountpoint(mountpoint)
    if err:
        print(f"\n  {err}")
        sys.exit(1)
    print(f"  Directory ready")

    # Step 7: Write fuse.json
    add_mount_to_config(mountpoint)
    print(f"\nConfig written to: {get_fuse_config_path()}")

    # Step 8: Initialize query store directory
    mount_data = get_mount_data_dir(mountpoint)
    mount_data.mkdir(parents=True, exist_ok=True)
    print(f"Data directory: {mount_data}")

    # Step 9: Offer autostart
    print()
    if has_systemd():
        if _prompt_yn("Install systemd user service for auto-mount?"):
            kg_fuse_path = shutil.which("kg-fuse") or "kg-fuse"
            ok, msg = install_systemd_unit(kg_fuse_path)
            if ok:
                print(f"\n  {msg}")
                print(f"\n  Manage with:")
                print(f"    systemctl --user status kg-fuse")
                print(f"    systemctl --user restart kg-fuse")
                print(f"    journalctl --user -u kg-fuse -f")
            else:
                print(f"\n  {msg}")
    else:
        shell_info = detect_shell()
        if shell_info:
            shell_name, rc_path = shell_info
            if _prompt_yn(f"Add auto-mount to {rc_path}?"):
                mount_line = "command -v kg-fuse >/dev/null && kg-fuse mount"
                ok, msg = add_to_rc(rc_path, mount_line)
                print(f"  {msg}")

    # Summary
    print(f"\nReady! Mount with:")
    print(f"  kg-fuse mount {mountpoint}")
    print(f"  kg-fuse mount                # mounts all configured")
    print()


def cmd_mount(args: Namespace) -> None:
    """Mount one or all configured FUSE filesystems."""
    config = load_config(
        cli_client_id=getattr(args, "client_id", None),
        cli_client_secret=getattr(args, "client_secret", None),
        cli_api_url=getattr(args, "api_url", None),
    )

    if not config.client_id or not config.client_secret:
        print("Error: No OAuth credentials found.\n")
        print("Set up credentials:")
        print("  kg login")
        print("  kg oauth create")
        print(f"\nOr pass directly: kg-fuse mount --client-id ID --client-secret SECRET")
        sys.exit(1)

    # Determine which mounts to start
    mountpoint = getattr(args, "mountpoint", None)
    foreground = getattr(args, "foreground", False)
    debug = getattr(args, "debug", False)

    if mountpoint:
        mountpoint = os.path.realpath(mountpoint)
        # Single mount — check if it's configured
        if mountpoint not in config.mounts:
            # Mount anyway with defaults, but warn
            mount_cfg = MountConfig(path=mountpoint)
            print(f"Note: {mountpoint} not in fuse.json — using defaults")
        else:
            mount_cfg = config.mounts[mountpoint]

        _start_mount(mountpoint, config, mount_cfg, foreground=foreground, debug=debug)
    else:
        # Mount all configured
        if not config.mounts:
            print("No mounts configured. Run: kg-fuse init /mnt/knowledge")
            sys.exit(1)

        started = 0
        for mount_path, mount_cfg in config.mounts.items():
            status = mount_status(mount_path)
            if status["running"]:
                print(f"  {mount_path} already mounted (pid {status['pid']})")
                continue
            if status["orphaned"]:
                print(f"  {mount_path} has orphaned mount — run kg-fuse repair first")
                continue

            _start_mount(mount_path, config, mount_cfg, foreground=False, debug=debug)
            started += 1

        if started == 0:
            print("All mounts already running.")
        else:
            print(f"\nStarted {started} mount{'s' if started != 1 else ''}.")


def _start_mount(
    mountpoint: str,
    config: FuseConfig,
    mount_cfg: MountConfig,
    foreground: bool = False,
    debug: bool = False,
) -> None:
    """Start a single FUSE mount (foreground or daemonized)."""
    # Validate mountpoint isn't already mounted
    status = mount_status(mountpoint)
    if status["running"]:
        print(f"Already mounted at {mountpoint} (pid {status['pid']})")
        return

    # Check for collision with other FUSE mounts
    collision = validate_mountpoint(mountpoint)
    if collision:
        print(f"  {mountpoint}: {collision}")
        return

    # Validate directory exists
    if not os.path.isdir(mountpoint):
        err = ensure_mountpoint(mountpoint)
        if err:
            print(f"Error: {err}")
            return

    # Late import to avoid pulling in pyfuse3 for non-mount commands
    import pyfuse3
    import trio
    from .filesystem import KnowledgeGraphFS
    from .query_store import QueryStore

    def run_mount(mp: str, cfg: FuseConfig):
        """Blocking function that runs the FUSE mount."""
        mc = cfg.mounts.get(mp, MountConfig(path=mp))

        # Setup logging for daemon
        if not foreground:
            mount_data = get_mount_data_dir(mp)
            mount_data.mkdir(parents=True, exist_ok=True)
            logging.basicConfig(
                level=logging.DEBUG if debug else logging.INFO,
                format="%(asctime)s %(levelname)s %(name)s: %(message)s",
                filename=str(mount_data / "daemon.log"),
                force=True,
            )

        # Create query store keyed to this mount
        query_data_dir = get_mount_data_dir(mp)
        query_data_dir.mkdir(parents=True, exist_ok=True)
        query_store = QueryStore(data_path=query_data_dir / "queries.toml")

        fs = KnowledgeGraphFS(
            api_url=cfg.api_url,
            client_id=cfg.client_id,
            client_secret=cfg.client_secret,
            tags_config=mc.tags,
            jobs_config=mc.jobs,
            cache_config=mc.cache,
            query_store=query_store,
        )

        fuse_options = set(pyfuse3.default_options)
        fuse_options.add("fsname=kg-fuse")
        if debug:
            fuse_options.add("debug")

        log.info(f"Mounting knowledge graph at {mp}")
        log.info(f"API: {cfg.api_url}")

        pyfuse3.init(fs, mp, fuse_options)

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

    if foreground:
        # Setup console logging
        logging.basicConfig(
            level=logging.DEBUG if debug else logging.INFO,
            format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        )
        from .safety import write_pid, clear_pid
        write_pid(mountpoint, os.getpid())
        try:
            run_mount(mountpoint, config)
        finally:
            clear_pid(mountpoint)
    else:
        pid = fork_mount(mountpoint, config, run_mount)
        print(f"  {mountpoint} mounted (pid {pid})")


def cmd_unmount(args: Namespace) -> None:
    """Unmount one or all FUSE filesystems."""
    config = load_config()
    mountpoint = getattr(args, "mountpoint", None)

    if mountpoint:
        mountpoint = os.path.realpath(mountpoint)
        _stop_mount(mountpoint)
    else:
        # Unmount all configured
        if not config.mounts:
            print("No mounts configured.")
            return

        stopped = 0
        for mount_path in config.mounts:
            status = mount_status(mount_path)
            if not status["running"] and not status["orphaned"]:
                continue
            _stop_mount(mount_path)
            stopped += 1

        if stopped == 0:
            print("No running mounts to stop.")


def _stop_mount(mountpoint: str) -> None:
    """Stop a single mount — kill daemon then fusermount."""
    status = mount_status(mountpoint)

    if status["running"] and status["pid"]:
        ok, msg = kill_mount_daemon(mountpoint)
        if ok:
            print(f"  {mountpoint} stopped ({msg})")
        else:
            print(f"  {mountpoint}: {msg}")

    # Always try fusermount to clean up the mount point
    ok, msg = fusermount_unmount(mountpoint)
    if ok:
        print(f"  {mountpoint} unmounted")
    elif status["running"] or status["orphaned"]:
        print(f"  {mountpoint}: {msg}")

    clear_pid(mountpoint)


def cmd_config(args: Namespace) -> None:
    """Show current configuration with masked secrets."""
    kg_path = get_kg_config_path()
    fuse_path = get_fuse_config_path()

    print(f"\nkg config:   {kg_path} {'(exists)' if kg_path.exists() else '(NOT FOUND)'}")
    print(f"fuse config: {fuse_path} {'(exists)' if fuse_path.exists() else '(NOT FOUND)'}")

    # Show kg config auth (masked)
    kg_data = read_kg_config()
    if kg_data:
        auth = kg_data.get("auth", {})
        print(f"\nAuth (from {kg_path}):")
        print(f"  client_id:     {auth.get('oauth_client_id', '(not set)')}")
        secret = auth.get("oauth_client_secret", "")
        print(f"  client_secret: {_mask_secret(secret) if secret else '(not set)'}")
        print(f"  api_url:       {kg_data.get('api_url', '(not set)')}")

        # Permission check
        warning = check_config_permissions(kg_path)
        if warning:
            print(f"\n  {warning}")

    # Show fuse config
    fuse_data = read_fuse_config()
    if fuse_data:
        print(f"\nFUSE config ({fuse_path}):")
        print(f"  auth_client_id: {fuse_data.get('auth_client_id', '(not set)')}")
        mounts = fuse_data.get("mounts", {})
        if mounts:
            print(f"  mounts:")
            for mp, settings in mounts.items():
                print(f"    {mp}")
                for key, val in settings.items():
                    print(f"      {key}: {val}")
        else:
            print(f"  mounts: (none)")

    print()


def cmd_repair(args: Namespace) -> None:
    """Detect and fix orphaned mounts, stale PIDs, bad config."""
    config = load_config()
    issues = 0

    print(f"\nkg-fuse repair\n")

    # Check for orphaned mounts in /proc/mounts
    mounted = find_mounted_fuse()
    for entry in mounted:
        mp = entry["mountpoint"]
        if is_mount_orphaned(mp):
            issues += 1
            print(f"  ORPHANED: {mp} (transport endpoint not connected)")
            if _prompt_yn(f"  Clean up with fusermount -u?"):
                ok, msg = fusermount_unmount(mp)
                print(f"    {msg}")
                clear_pid(mp)

    # Check configured mounts for stale PIDs
    for mount_path in config.mounts:
        status = mount_status(mount_path)
        if status["pid"] and not status["running"]:
            issues += 1
            print(f"  STALE PID: {mount_path} (pid {status['pid']} not running)")
            clear_pid(mount_path)
            print(f"    Cleaned up PID file")

    # Check for mounts pointing to nonexistent directories
    for mount_path in config.mounts:
        if not os.path.isdir(mount_path):
            issues += 1
            print(f"  MISSING DIR: {mount_path} does not exist")
            if _prompt_yn(f"  Remove from config?"):
                from .config import remove_mount_from_config
                remove_mount_from_config(mount_path)
                print(f"    Removed from fuse.json")

    # Check for rogue kg-fuse processes not tied to any configured mount
    my_pid = os.getpid()
    all_procs = find_kg_fuse_processes()
    daemon_procs = [p for p in all_procs if p["pid"] != my_pid]

    # Collect PIDs accounted for by configured mounts
    accounted_pids = set()
    for mount_path in config.mounts:
        st = mount_status(mount_path)
        if st["pid"]:
            accounted_pids.add(st["pid"])

    rogue_procs = [p for p in daemon_procs if p["pid"] not in accounted_pids]
    if rogue_procs:
        for p in rogue_procs:
            issues += 1
            print(f"  ROGUE PROCESS: pid {p['pid']}")
            print(f"    {p['cmdline'][:100]}")
            if _prompt_yn(f"  Kill this process?"):
                try:
                    import signal
                    os.kill(p["pid"], signal.SIGTERM)
                    print(f"    Sent SIGTERM to pid {p['pid']}")
                except OSError as e:
                    print(f"    Failed to kill: {e}")

    # Check systemd unit
    unit_path = get_systemd_unit_path()
    if unit_path.exists():
        kg_fuse_path = shutil.which("kg-fuse")
        if kg_fuse_path:
            content = unit_path.read_text()
            if kg_fuse_path not in content:
                issues += 1
                print(f"  STALE UNIT: systemd unit references wrong path")
                if _prompt_yn(f"  Update to {kg_fuse_path}?"):
                    ok, msg = install_systemd_unit(kg_fuse_path)
                    print(f"    {msg}")

    if issues == 0:
        print("  No issues found.")
    else:
        print(f"\n  Fixed {issues} issue{'s' if issues != 1 else ''}.")
    print()


def cmd_update(args: Namespace) -> None:
    """Self-update via pipx."""
    current = _get_version()
    print(f"Current version: {current}")
    print("Updating via pipx...\n")

    try:
        result = subprocess.run(
            ["pipx", "upgrade", "kg-fuse"],
            text=True,
        )
        if result.returncode == 0:
            new_ver = _get_version()
            if new_ver != current:
                print(f"\nUpdated: {current} -> {new_ver}")
            else:
                print(f"\nAlready at latest version ({current})")
        else:
            print("\npipx upgrade failed.")
            sys.exit(1)
    except FileNotFoundError:
        print("'pipx' not found. Install: python3 -m pip install pipx")
        sys.exit(1)
