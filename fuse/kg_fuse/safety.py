"""
Safety fences for kg-fuse.

Mountpoint validation, PID verification, orphaned mount detection,
and RC file management with backup/restore.
"""

import errno
import logging
import os
import shutil
import signal
import stat
import subprocess
from pathlib import Path
from typing import Optional

from .config import get_fuse_state_dir

log = logging.getLogger(__name__)

# System paths that must never be used as mountpoints
BLOCKED_PATHS = frozenset({
    "/", "/home", "/etc", "/usr", "/var", "/tmp", "/boot",
    "/bin", "/sbin", "/lib", "/lib64", "/dev", "/proc", "/sys",
    "/root", "/opt", "/srv", "/run", "/mnt",
})

# Delimiters for RC file blocks
RC_BEGIN = "# >>> kg-fuse >>>"
RC_END = "# <<< kg-fuse <<<"


# --- Mountpoint validation ---

def validate_mountpoint(path: str) -> Optional[str]:
    """Validate a mountpoint path. Returns error message or None if OK."""
    resolved = os.path.realpath(path)

    # Block system paths
    if resolved in BLOCKED_PATHS:
        return (
            f"Refusing to mount at {resolved} — this is a system directory.\n"
            f"\n"
            f"Use a dedicated empty directory instead:\n"
            f"  kg-fuse init /mnt/knowledge\n"
            f"  kg-fuse init ~/kg"
        )

    # Check for existing FUSE mount at this path (collision with other FUSE drivers)
    all_fuse = find_all_fuse_mounts()
    for m in all_fuse:
        if os.path.realpath(m["mountpoint"]) == resolved:
            source = m["source"]
            if m["is_ours"]:
                return (
                    f"{resolved} already has a kg-fuse mount active.\n"
                    f"Unmount first: kg-fuse unmount {resolved}"
                )
            return (
                f"{resolved} is already a FUSE mount ({source}, type {m['fstype']}).\n"
                f"\n"
                f"Mounting over an existing FUSE mount will cause conflicts.\n"
                f"Choose a different path, or unmount the existing mount first."
            )

    # Check for non-empty existing directory
    if os.path.isdir(resolved):
        try:
            contents = os.listdir(resolved)
        except PermissionError:
            return f"Cannot read {resolved} — permission denied."

        if contents:
            count = len(contents)
            return (
                f"{resolved} is not empty (contains {count} item{'s' if count != 1 else ''}).\n"
                f"\n"
                f"FUSE mounts shadow existing directory contents — your files would be\n"
                f"hidden (not deleted) until unmount, but this is confusing and risky.\n"
                f"\n"
                f"Use an empty or new directory instead:\n"
                f"  kg-fuse init /mnt/knowledge\n"
                f"  kg-fuse init ~/kg"
            )

    return None


def ensure_mountpoint(path: str) -> Optional[str]:
    """Create mountpoint directory if needed. Returns error message or None."""
    if os.path.isdir(path):
        return None

    try:
        os.makedirs(path, exist_ok=True)
        return None
    except PermissionError:
        return (
            f"Cannot create {path} — permission denied.\n"
            f"\n"
            f"Try:\n"
            f"  sudo mkdir -p {path}\n"
            f"  sudo chown $USER {path}"
        )
    except OSError as e:
        return f"Cannot create {path}: {e}"


# --- PID file management ---

def get_pid_path(mountpoint: str) -> Path:
    """Get PID file path for a mountpoint."""
    from .config import get_mount_id
    state_dir = get_fuse_state_dir()
    state_dir.mkdir(parents=True, exist_ok=True)
    return state_dir / f"{get_mount_id(mountpoint)}.pid"


def write_pid(mountpoint: str, pid: int) -> None:
    """Write PID file for a mount."""
    pid_path = get_pid_path(mountpoint)
    pid_path.parent.mkdir(parents=True, exist_ok=True)
    pid_path.write_text(str(pid))


def read_pid(mountpoint: str) -> Optional[int]:
    """Read PID from file. Returns None if missing or invalid."""
    pid_path = get_pid_path(mountpoint)
    if not pid_path.exists():
        return None
    try:
        return int(pid_path.read_text().strip())
    except (ValueError, OSError):
        return None


def clear_pid(mountpoint: str) -> None:
    """Remove PID file for a mount."""
    pid_path = get_pid_path(mountpoint)
    pid_path.unlink(missing_ok=True)


def is_kg_fuse_process(pid: int) -> bool:
    """Check if a PID belongs to a kg-fuse process via /proc/cmdline."""
    try:
        cmdline = Path(f"/proc/{pid}/cmdline").read_bytes()
        return b"kg-fuse" in cmdline or b"kg_fuse" in cmdline
    except (OSError, PermissionError):
        return False


def find_kg_fuse_processes() -> list[dict]:
    """Scan /proc for running kg-fuse daemon processes owned by current user.

    Only matches processes where 'kg-fuse' or 'kg_fuse' appears as the actual
    command being run (argv[0] or argv[1]), not just in a path component.

    Returns list of {"pid": int, "cmdline": str}.
    """
    uid = os.getuid()
    procs = []
    try:
        for entry in Path("/proc").iterdir():
            if not entry.name.isdigit():
                continue
            pid = int(entry.name)
            try:
                # Only check our own processes
                if entry.stat().st_uid != uid:
                    continue
                cmdline_raw = (entry / "cmdline").read_bytes()
                # Split on null bytes to get argv
                argv = cmdline_raw.split(b"\x00")
                # Check if any argument IS kg-fuse (not just contains it in a path)
                is_kg_fuse = False
                for arg in argv[:3]:  # Only check first few args
                    arg_str = arg.decode(errors="replace")
                    basename = os.path.basename(arg_str)
                    if basename in ("kg-fuse", "kg_fuse"):
                        is_kg_fuse = True
                        break
                    # Also match: python .../kg_fuse/main.py
                    if "kg_fuse/main.py" in arg_str or "kg-fuse" == basename:
                        is_kg_fuse = True
                        break

                if is_kg_fuse:
                    cmdline = cmdline_raw.replace(b"\x00", b" ").decode(errors="replace").strip()
                    procs.append({"pid": pid, "cmdline": cmdline})
            except (OSError, PermissionError):
                continue
    except OSError:
        pass
    return procs


def is_process_alive(pid: int) -> bool:
    """Check if a process is running."""
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def kill_mount_daemon(mountpoint: str) -> tuple[bool, str]:
    """Kill the daemon for a mountpoint. Returns (success, message).

    Verifies the PID is actually a kg-fuse process before sending SIGTERM.
    """
    pid = read_pid(mountpoint)
    if pid is None:
        return False, f"No PID file found for {mountpoint}"

    if not is_process_alive(pid):
        clear_pid(mountpoint)
        return False, f"Process {pid} is not running (stale PID file cleaned up)"

    if not is_kg_fuse_process(pid):
        clear_pid(mountpoint)
        return False, (
            f"PID {pid} is not a kg-fuse process — stale PID file removed.\n"
            f"The original kg-fuse process likely crashed."
        )

    try:
        os.kill(pid, signal.SIGTERM)
        clear_pid(mountpoint)
        return True, f"Sent SIGTERM to pid {pid}"
    except OSError as e:
        return False, f"Failed to kill pid {pid}: {e}"


# --- Orphaned mount detection ---

def find_mounted_fuse() -> list[dict]:
    """Find all kg-fuse entries in /proc/mounts.

    Returns list of {"mountpoint": str, "fstype": str}.
    """
    mounts = []
    try:
        for line in Path("/proc/mounts").read_text().splitlines():
            parts = line.split()
            if len(parts) >= 3 and parts[0] == "kg-fuse":
                mounts.append({
                    "mountpoint": parts[1],
                    "fstype": parts[2],
                })
    except OSError:
        pass
    return mounts


# System FUSE mounts that are kernel/desktop plumbing, not user filesystems
_SYSTEM_FUSE_SOURCES = frozenset({"fusectl", "portal", "gvfsd-fuse"})
_SYSTEM_FUSE_PATHS = frozenset({"/sys/fs/fuse/connections"})


def find_all_fuse_mounts() -> list[dict]:
    """Find ALL FUSE mounts on the system (not just kg-fuse).

    Returns list of {"source": str, "mountpoint": str, "fstype": str,
                     "is_ours": bool, "is_system": bool}.
    """
    mounts = []
    try:
        for line in Path("/proc/mounts").read_text().splitlines():
            parts = line.split()
            if len(parts) >= 3 and "fuse" in parts[2].lower():
                source = parts[0]
                mountpoint = parts[1]
                is_system = (
                    source in _SYSTEM_FUSE_SOURCES
                    or mountpoint in _SYSTEM_FUSE_PATHS
                    or parts[2] == "fusectl"
                )
                mounts.append({
                    "source": source,
                    "mountpoint": mountpoint,
                    "fstype": parts[2],
                    "is_ours": source == "kg-fuse",
                    "is_system": is_system,
                })
    except OSError:
        pass
    return mounts


def is_mount_orphaned(mountpoint: str) -> bool:
    """Check if a FUSE mount is orphaned (transport endpoint not connected)."""
    try:
        os.statvfs(mountpoint)
        return False
    except OSError as e:
        return e.errno == errno.ENOTCONN


def fusermount_unmount(mountpoint: str) -> tuple[bool, str]:
    """Run fusermount -u to clean-unmount a FUSE mount. Returns (success, message)."""
    try:
        result = subprocess.run(
            ["fusermount", "-u", mountpoint],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            return True, f"Unmounted {mountpoint}"
        return False, f"fusermount failed: {result.stderr.strip()}"
    except FileNotFoundError:
        # Try fusermount3 as fallback
        try:
            result = subprocess.run(
                ["fusermount3", "-u", mountpoint],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0:
                return True, f"Unmounted {mountpoint}"
            return False, f"fusermount3 failed: {result.stderr.strip()}"
        except FileNotFoundError:
            return False, "Neither fusermount nor fusermount3 found"
    except subprocess.TimeoutExpired:
        return False, f"fusermount timed out on {mountpoint}"


# --- RC file management ---

def detect_shell() -> Optional[tuple[str, Path]]:
    """Detect the user's shell and RC file.

    Returns (shell_name, rc_path) or None if unrecognized.
    """
    shell = os.environ.get("SHELL", "")
    home = Path.home()

    if "zsh" in shell:
        return ("zsh", home / ".zshrc")
    elif "bash" in shell:
        # .bash_profile for login shell (runs once, not per-subshell)
        profile = home / ".bash_profile"
        if profile.exists():
            return ("bash", profile)
        return ("bash", home / ".profile")
    elif "fish" in shell:
        return ("fish", home / ".config" / "fish" / "config.fish")

    return None


def add_to_rc(rc_path: Path, mount_command: str) -> tuple[bool, str]:
    """Add kg-fuse mount line to shell RC file with backup.

    Uses delimited blocks for clean removal. Backs up RC file first.
    """
    # Backup
    backup_path = rc_path.with_suffix(rc_path.suffix + ".kg-fuse-backup")
    if rc_path.exists() and not backup_path.exists():
        shutil.copy2(rc_path, backup_path)

    # Check if block already exists
    if rc_path.exists():
        content = rc_path.read_text()
        if RC_BEGIN in content:
            return False, f"kg-fuse block already exists in {rc_path}"
    else:
        content = ""

    block = f"\n{RC_BEGIN}\n{mount_command}\n{RC_END}\n"

    with open(rc_path, "a") as f:
        f.write(block)

    return True, f"Added to {rc_path} (backup: {backup_path})"


def remove_from_rc(rc_path: Path) -> tuple[bool, str]:
    """Remove kg-fuse block from shell RC file."""
    if not rc_path.exists():
        return False, f"{rc_path} does not exist"

    content = rc_path.read_text()
    if RC_BEGIN not in content:
        return False, f"No kg-fuse block found in {rc_path}"

    lines = content.splitlines(keepends=True)
    new_lines = []
    inside_block = False
    for line in lines:
        if RC_BEGIN in line:
            inside_block = True
            continue
        if RC_END in line:
            inside_block = False
            continue
        if not inside_block:
            new_lines.append(line)

    rc_path.write_text("".join(new_lines))
    return True, f"Removed kg-fuse block from {rc_path}"


# --- Systemd detection ---

def has_systemd() -> bool:
    """Check if systemd user services are available."""
    return shutil.which("systemctl") is not None and Path("/run/systemd/system").exists()


def get_systemd_unit_path() -> Path:
    """Get path for kg-fuse systemd user unit file."""
    xdg_config = os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config"))
    return Path(xdg_config) / "systemd" / "user" / "kg-fuse.service"


def install_systemd_unit(kg_fuse_path: str, enable: bool = True) -> tuple[bool, str]:
    """Install systemd user service for kg-fuse.

    Uses Type=simple with --foreground so systemd manages the lifecycle
    directly instead of wrapping a double-fork daemon.

    The kg_fuse_path MUST be an absolute path — systemd user units do not
    search $PATH, so bare 'kg-fuse' causes EXEC(203) failures.
    """
    # Ensure we have an absolute path — systemd doesn't search PATH
    if not os.path.isabs(kg_fuse_path):
        import shutil
        resolved = shutil.which(kg_fuse_path)
        if resolved:
            kg_fuse_path = resolved
        # If which() fails too, we proceed with what we have — install_systemd_unit
        # is best-effort and the caller can handle the error.

    unit_path = get_systemd_unit_path()
    unit_path.parent.mkdir(parents=True, exist_ok=True)

    unit_content = f"""\
[Unit]
Description=Knowledge Graph FUSE Driver
After=network-online.target

[Service]
Type=simple
ExecStart={kg_fuse_path} mount --foreground
ExecStop={kg_fuse_path} unmount
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
"""
    unit_path.write_text(unit_content)

    try:
        subprocess.run(
            ["systemctl", "--user", "daemon-reload"],
            capture_output=True, timeout=10,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        return False, f"daemon-reload failed: {e}"

    if not enable:
        return True, f"Installed {unit_path} (not enabled)"

    try:
        result = subprocess.run(
            ["systemctl", "--user", "enable", "kg-fuse"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            return True, f"Installed and enabled {unit_path}"
        return False, f"systemctl enable failed: {result.stderr.strip()}"
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        return False, f"systemctl failed: {e}"


def systemd_start() -> tuple[bool, str]:
    """Start kg-fuse via systemd user service."""
    try:
        result = subprocess.run(
            ["systemctl", "--user", "start", "kg-fuse"],
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode == 0:
            return True, "Started kg-fuse.service"
        return False, f"systemctl start failed: {result.stderr.strip()}"
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        return False, f"systemctl start failed: {e}"


def systemd_stop() -> tuple[bool, str]:
    """Stop kg-fuse via systemd user service."""
    try:
        result = subprocess.run(
            ["systemctl", "--user", "stop", "kg-fuse"],
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode == 0:
            return True, "Stopped kg-fuse.service"
        return False, f"systemctl stop failed: {result.stderr.strip()}"
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        return False, f"systemctl stop failed: {e}"


def systemd_restart() -> tuple[bool, str]:
    """Restart kg-fuse via systemd user service."""
    try:
        result = subprocess.run(
            ["systemctl", "--user", "restart", "kg-fuse"],
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode == 0:
            return True, "Restarted kg-fuse.service"
        return False, f"systemctl restart failed: {result.stderr.strip()}"
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        return False, f"systemctl restart failed: {e}"


def uninstall_systemd_unit() -> tuple[bool, str]:
    """Disable and remove systemd user service."""
    unit_path = get_systemd_unit_path()

    try:
        subprocess.run(
            ["systemctl", "--user", "disable", "--now", "kg-fuse"],
            capture_output=True, timeout=10,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    if unit_path.exists():
        unit_path.unlink()
        subprocess.run(
            ["systemctl", "--user", "daemon-reload"],
            capture_output=True, timeout=10,
        )
        return True, f"Removed {unit_path}"

    return False, "No systemd unit found"


# --- Credential exposure check ---

def check_config_permissions(path: Path) -> Optional[str]:
    """Check if a config file has overly permissive permissions.

    Returns warning message or None if OK.
    """
    if not path.exists():
        return None

    mode = path.stat().st_mode
    if mode & (stat.S_IRGRP | stat.S_IROTH):
        return (
            f"Warning: {path} is readable by group/others (mode {oct(mode)[-3:]}).\n"
            f"This file contains credentials. Fix with:\n"
            f"  chmod 600 {path}"
        )
    return None


def fix_config_permissions(path: Path) -> tuple[bool, str]:
    """Set config file to owner-only permissions (600).

    Returns (success, message).
    """
    if not path.exists():
        return False, f"{path} does not exist"
    try:
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
        return True, f"Set {path} to mode 600"
    except OSError as e:
        return False, f"Could not chmod {path}: {e}"
