"""
Daemon lifecycle management for kg-fuse.

Handles forking mount processes into background, PID tracking,
and clean shutdown via signal handling.
"""

import logging
import os
import signal
import sys
from typing import Callable

from .config import MountConfig, FuseConfig, get_mount_data_dir
from .safety import write_pid, clear_pid, read_pid, is_process_alive, is_kg_fuse_process

log = logging.getLogger(__name__)


def fork_mount(mountpoint: str, config: FuseConfig, run_fn: Callable) -> int:
    """Fork a daemon process that runs a FUSE mount.

    Args:
        mountpoint: Where to mount
        config: Full FUSE config (credentials, mount settings)
        run_fn: Function that performs the actual mount (blocks until unmount)

    Returns:
        Daemon PID (in parent), never returns in child.
    """
    # Use a pipe so daemon can report its PID back to parent
    read_fd, write_fd = os.pipe()

    pid = os.fork()
    if pid > 0:
        # Parent: read daemon PID from pipe
        os.close(write_fd)
        data = b""
        while True:
            chunk = os.read(read_fd, 64)
            if not chunk:
                break
            data += chunk
        os.close(read_fd)

        try:
            daemon_pid = int(data.strip())
        except ValueError:
            daemon_pid = pid

        # Wait for intermediate child to exit
        try:
            os.waitpid(pid, 0)
        except ChildProcessError:
            pass

        return daemon_pid

    # Child: close read end
    os.close(read_fd)

    # New session
    os.setsid()

    # Second fork
    pid2 = os.fork()
    if pid2 > 0:
        # Send daemon PID to parent then exit
        os.write(write_fd, str(pid2).encode())
        os.close(write_fd)
        os._exit(0)

    # Daemon process
    os.close(write_fd)

    # Redirect stdio to /dev/null
    devnull = os.open(os.devnull, os.O_RDWR)
    os.dup2(devnull, 0)
    os.dup2(devnull, 1)
    os.dup2(devnull, 2)
    os.close(devnull)

    # Write PID file
    daemon_pid = os.getpid()
    write_pid(mountpoint, daemon_pid)

    # Setup signal handler — raise KeyboardInterrupt so the FUSE event loop
    # can perform async cleanup (unmount, close connections) rather than
    # sys.exit() which would bypass finally blocks in async contexts.
    def _handle_term(signum, frame):
        log.info(f"Received signal {signum}, requesting shutdown for {mountpoint}")
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, _handle_term)
    signal.signal(signal.SIGINT, _handle_term)

    # Setup logging to file in data dir
    mount_data_dir = get_mount_data_dir(mountpoint)
    mount_data_dir.mkdir(parents=True, exist_ok=True)
    log_path = mount_data_dir / "daemon.log"

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        filename=str(log_path),
        force=True,
    )

    try:
        run_fn(mountpoint, config)
    except Exception as e:
        log.error(f"Mount failed for {mountpoint}: {e}", exc_info=True)
    finally:
        clear_pid(mountpoint)

    os._exit(0)


def mount_status(mountpoint: str) -> dict:
    """Get status of a mount daemon.

    Returns dict with keys: running, pid, orphaned.
    """
    from .safety import is_mount_orphaned, find_mounted_fuse

    pid = read_pid(mountpoint)
    mounted_entries = find_mounted_fuse()
    is_in_proc_mounts = any(m["mountpoint"] == mountpoint for m in mounted_entries)

    if pid and is_process_alive(pid) and is_kg_fuse_process(pid):
        return {"running": True, "pid": pid, "orphaned": False}

    if is_in_proc_mounts:
        orphaned = is_mount_orphaned(mountpoint)
        return {"running": not orphaned, "pid": pid, "orphaned": orphaned}

    # Not running, clean up stale PID
    if pid:
        clear_pid(mountpoint)

    return {"running": False, "pid": None, "orphaned": False}
