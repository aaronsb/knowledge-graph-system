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


# --- ANSI formatting helpers ---

def _supports_color() -> bool:
    """Check if terminal supports ANSI colors."""
    if os.environ.get("NO_COLOR"):
        return False
    if not hasattr(sys.stdout, "isatty") or not sys.stdout.isatty():
        return False
    return True

_COLOR = _supports_color()

def _bold(text: str) -> str:
    return f"\033[1m{text}\033[0m" if _COLOR else text

def _green(text: str) -> str:
    return f"\033[32m{text}\033[0m" if _COLOR else text

def _yellow(text: str) -> str:
    return f"\033[33m{text}\033[0m" if _COLOR else text

def _red(text: str) -> str:
    return f"\033[31m{text}\033[0m" if _COLOR else text

def _dim(text: str) -> str:
    return f"\033[2m{text}\033[0m" if _COLOR else text


def _systemd_unit_active() -> bool:
    """Check if kg-fuse systemd user service is active."""
    try:
        result = subprocess.run(
            ["systemctl", "--user", "is-active", "kg-fuse"],
            capture_output=True, text=True, timeout=5,
        )
        return result.stdout.strip() == "active"
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def _systemd_unit_enabled() -> bool:
    """Check if kg-fuse systemd user service is enabled."""
    try:
        result = subprocess.run(
            ["systemctl", "--user", "is-enabled", "kg-fuse"],
            capture_output=True, text=True, timeout=5,
        )
        return result.stdout.strip() == "enabled"
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


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

    print(f"\n{_bold(f'kg-fuse {ver}')}\n")

    # Check if fuse.json exists
    fuse_path = get_fuse_config_path()
    if not fuse_path.exists():
        kg_path = get_kg_config_path()
        print("No configuration found. Run:")
        print(f"  {_bold('kg-fuse init /mnt/knowledge')}\n")
        if not kg_path.exists():
            print("Prerequisites:")
            print(f"  {_dim('npm install -g @aaronsb/kg-cli')}")
            print(f"  {_dim('kg login')}")
            print(f"  {_dim('kg oauth create')}")
        return

    # Detect daemonization method
    unit_path = get_systemd_unit_path()
    systemd_enabled = _systemd_unit_enabled()
    systemd_active = _systemd_unit_active()

    # Scan for all running kg-fuse daemon processes
    all_procs = find_kg_fuse_processes()
    my_pid = os.getpid()
    daemon_procs = [p for p in all_procs if p["pid"] != my_pid]

    # Collect PIDs that are accounted for by configured mounts
    accounted_pids = set()

    # Show mounts
    if config.mounts:
        print(f"{_bold('Mounts:')}")
        for mount_path, mount_cfg in config.mounts.items():
            status = mount_status(mount_path)
            if status["pid"]:
                accounted_pids.add(status["pid"])
            if status["orphaned"]:
                state = _red("ORPHANED") + _dim(" (run: kg-fuse repair)")
            elif status["running"]:
                state = _green("mounted") + f"    pid {status['pid']}"
            else:
                state = _dim("stopped")
            print(f"  {mount_path:<30s} {state}")
    else:
        print(f"{_bold('Mounts:')} {_dim('(none configured)')}")
        print(f"  Add one with: {_bold('kg-fuse init /mnt/knowledge')}")

    # Check for unaccounted daemon processes (not tied to any configured mount)
    rogue_procs = [p for p in daemon_procs if p["pid"] not in accounted_pids]
    if rogue_procs:
        print(f"\n  {_yellow('WARNING:')} {len(rogue_procs)} kg-fuse process(es) not in config:")
        for p in rogue_procs:
            print(f"    pid {p['pid']}: {_dim(p['cmdline'][:80])}")
        print(f"  Run {_bold('kg-fuse repair')} to investigate.")

    # Daemon management summary
    print()
    running_count = sum(
        1 for mp in config.mounts
        if mount_status(mp)["running"]
    )
    total_daemon_count = len(daemon_procs)

    if systemd_enabled:
        if systemd_active:
            mgmt = _green("systemd user service") + " (enabled, active)"
        else:
            mgmt = _yellow("systemd user service") + " (enabled, inactive)"
    elif unit_path.exists():
        mgmt = _dim("systemd user service") + " (installed, not enabled)"
    else:
        if total_daemon_count > 0:
            mgmt = _dim("session daemon") + " (manual / shell RC)"
        else:
            mgmt = _dim("none")

    print(f"{_bold('Managed by:')} {mgmt}")

    if total_daemon_count == 0:
        print(f"{_bold('Daemons:')}  {_dim('none running')}")
    else:
        print(f"{_bold('Daemons:')}  {total_daemon_count} process(es)"
              f" ({running_count} configured mount(s) active)")

    # Auth info
    print()
    if config.client_id:
        print(f"{_bold('Auth:')}    {config.client_id} {_dim(f'(via {get_kg_config_path()})')}")
    else:
        print(f"{_bold('Auth:')}    {_red('not configured')}")

    # API
    reachable, api_info = _test_api(config.api_url)
    if reachable:
        print(f"{_bold('API:')}     {config.api_url} {_green(f'(v{api_info})')}")
    else:
        print(f"{_bold('API:')}     {config.api_url} {_red(f'({api_info})')}")

    # FUSE library
    fuse3_available = shutil.which("fusermount3") or shutil.which("fusermount")
    fuse_state = _green("present") if fuse3_available else _red("NOT FOUND")
    print(f"{_bold('FUSE:')}    {fuse_state}")

    # Show other FUSE mounts on the system (collision awareness)
    all_fuse = find_all_fuse_mounts()
    other_fuse = [m for m in all_fuse if not m["is_ours"] and not m["is_system"]]
    if other_fuse:
        print(f"\n{_bold('Other FUSE mounts:')}")
        for m in other_fuse:
            detail = f"{m['source']} ({m['fstype']})"
            print(f"  {m['mountpoint']:<30s} {_dim(detail)}")

    # Commands hint
    print(f"\n{_dim('Commands:')}")
    print(f"  {_dim('kg-fuse mount              Mount all configured filesystems')}")
    print(f"  {_dim('kg-fuse unmount            Unmount all')}")
    print(f"  {_dim('kg-fuse init [path]        Add a new mount')}")
    print(f"  {_dim('kg-fuse repair             Fix orphaned mounts / stale state')}")
    print(f"  {_dim('kg-fuse config             Show configuration')}")
    print(f"  {_dim('kg-fuse update             Update kg-fuse via pipx')}")
    print(f"  {_dim('kg-fuse --help             Full help')}")
    print()


def cmd_init(args: Namespace) -> None:
    """Interactive setup: detect auth, configure mount, offer autostart."""
    mountpoint = os.path.realpath(args.mountpoint)
    api_url = args.api_url

    print(f"\n{_bold('Knowledge Graph FUSE Driver Setup')}")
    print(f"{'=' * 34}\n")

    # Step 1: Check kg config exists
    kg_config = read_kg_config()
    if kg_config is None:
        kg_path = get_kg_config_path()
        print(f"{_red('No kg configuration found')} at {kg_path}\n")
        print("The kg CLI manages authentication for all kg tools.")
        print("Install and configure it first:\n")
        print(f"  {_dim('npm install -g @aaronsb/kg-cli')}")
        print(f"  {_dim('kg login')}")
        print(f"  {_dim('kg oauth create')}")
        print(f"\nThen run {_bold('kg-fuse init')} again.")
        sys.exit(1)

    # Step 2: Resolve API URL
    if not api_url:
        api_url = kg_config.get("api_url", "http://localhost:8000")

    # Step 3: Check API
    print("Checking API... ", end="", flush=True)
    reachable, api_info = _test_api(api_url)
    if reachable:
        print(f"{_green('OK')}  {api_url} (v{api_info})")
    else:
        print(f"{_red('FAILED')}  {api_url} ({api_info})")
        print("\nMake sure the knowledge graph platform is running.")
        print(f"  {_dim('operator.sh start')}")
        sys.exit(1)

    # Step 4: Check auth
    print("Checking credentials... ", end="", flush=True)
    client_id, client_secret, _ = read_kg_credentials()

    if not client_id or not client_secret:
        print(f"{_yellow('MISSING')}\n")
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
        print(f"{_green('OK')}  {client_id}")
    else:
        print(f"{_red('FAILED')}  {auth_info}")
        print("\n  Credentials may be expired. Try:")
        print(f"    {_dim('kg oauth create')}")
        sys.exit(1)

    # Step 5: Check credential permissions
    perm_warning = check_config_permissions(get_kg_config_path())
    if perm_warning:
        print(f"\n  {_yellow(perm_warning)}")

    # Step 6: Validate mountpoint
    print(f"\n{_bold('Mount point:')} {mountpoint}")

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
    systemd_installed = False
    rc_installed = False
    print()
    if has_systemd():
        # Check if systemd unit already exists and is enabled
        if _systemd_unit_enabled():
            print(f"Autostart: {_green('systemd user service already enabled')}")
            systemd_installed = True
        elif _prompt_yn("Install systemd user service for auto-mount?"):
            kg_fuse_path = shutil.which("kg-fuse") or "kg-fuse"
            ok, msg = install_systemd_unit(kg_fuse_path)
            if ok:
                systemd_installed = True
                print(f"\n  {_green(msg)}")
                print(f"\n  Manage with:")
                print(f"    {_dim('systemctl --user status kg-fuse')}")
                print(f"    {_dim('systemctl --user restart kg-fuse')}")
                print(f"    {_dim('journalctl --user -u kg-fuse -f')}")
            else:
                print(f"\n  {_red(msg)}")
    else:
        shell_info = detect_shell()
        if shell_info:
            shell_name, rc_path = shell_info
            if _prompt_yn(f"Add auto-mount to {rc_path}?"):
                mount_line = "command -v kg-fuse >/dev/null && kg-fuse mount"
                ok, msg = add_to_rc(rc_path, mount_line)
                print(f"  {msg}")
                if ok:
                    rc_installed = True

    # Summary — context-aware about autostart
    print()
    if systemd_installed:
        # Systemd handles it — mount is either already active or will start now
        if _systemd_unit_active():
            print(f"{_green('Ready!')} Filesystem is mounted at {_bold(mountpoint)}")
            print(f"Auto-mounts on login via systemd user service.")
        else:
            print(f"{_green('Ready!')} Systemd service will mount {_bold(mountpoint)} shortly.")
            print(f"Auto-mounts on login via systemd user service.")
        print(f"\n  {_dim('kg-fuse status                # check mount status')}")
        print(f"  {_dim('systemctl --user restart kg-fuse  # restart service')}")
    elif rc_installed:
        print(f"{_green('Ready!')} Mount with:")
        print(f"  {_bold(f'kg-fuse mount {mountpoint}')}")
        print(f"\nWill auto-mount on shell login.")
    else:
        print(f"{_green('Ready!')} Mount with:")
        print(f"  {_bold(f'kg-fuse mount {mountpoint}')}")
        print(f"  {_dim(f'kg-fuse mount                # mounts all configured')}")
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

    kg_exists = _green("(exists)") if kg_path.exists() else _red("(NOT FOUND)")
    fuse_exists = _green("(exists)") if fuse_path.exists() else _red("(NOT FOUND)")
    print(f"\n{_bold('kg config:')}   {kg_path} {kg_exists}")
    print(f"{_bold('fuse config:')} {fuse_path} {fuse_exists}")

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

    print(f"\n{_bold('kg-fuse repair')}\n")

    # Check for orphaned mounts in /proc/mounts
    mounted = find_mounted_fuse()
    for entry in mounted:
        mp = entry["mountpoint"]
        if is_mount_orphaned(mp):
            issues += 1
            print(f"  {_red('ORPHANED:')} {mp} (transport endpoint not connected)")
            if _prompt_yn(f"  Clean up with fusermount -u?"):
                ok, msg = fusermount_unmount(mp)
                print(f"    {msg}")
                clear_pid(mp)

    # Check configured mounts for stale PIDs
    for mount_path in config.mounts:
        status = mount_status(mount_path)
        if status["pid"] and not status["running"]:
            issues += 1
            print(f"  {_yellow('STALE PID:')} {mount_path} (pid {status['pid']} not running)")
            clear_pid(mount_path)
            print(f"    Cleaned up PID file")

    # Check for mounts pointing to nonexistent directories
    for mount_path in config.mounts:
        if not os.path.isdir(mount_path):
            issues += 1
            print(f"  {_yellow('MISSING DIR:')} {mount_path} does not exist")
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
            print(f"  {_red('ROGUE PROCESS:')} pid {p['pid']}")
            print(f"    {_dim(p['cmdline'][:100])}")
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
                print(f"  {_yellow('STALE UNIT:')} systemd unit references wrong path")
                if _prompt_yn(f"  Update to {kg_fuse_path}?"):
                    ok, msg = install_systemd_unit(kg_fuse_path)
                    print(f"    {msg}")

    if issues == 0:
        print(f"  {_green('No issues found.')}")
    else:
        print(f"\n  Addressed {issues} issue{'s' if issues != 1 else ''}.")
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
