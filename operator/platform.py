#!/usr/bin/env python3
"""
Platform lifecycle management for the Knowledge Graph System.

This script runs inside the kg-operator container and manages the platform
lifecycle using the operator-as-control-plane pattern (Kubernetes-inspired).

The operator remembers platform configuration (dev mode, GPU mode) in the
database and uses that to construct the correct docker-compose commands.

Usage:
    # Initialize platform (first-time setup from quickstart.sh)
    python platform.py init --dev --gpu nvidia

    # Start platform (uses saved configuration)
    python platform.py start

    # Stop platform
    python platform.py stop

    # Show status
    python platform.py status

    # Update configuration
    python platform.py config --dev true
    python platform.py config --gpu nvidia
"""

import argparse
import os
import subprocess
import sys
from datetime import datetime
from typing import Optional, Dict, Any

import psycopg2
from psycopg2.extras import RealDictCursor


# Colors for output
class Colors:
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    BOLD = '\033[1m'
    NC = '\033[0m'


def get_db_connection():
    """Get database connection using environment variables."""
    return psycopg2.connect(
        host=os.getenv('POSTGRES_HOST', 'postgres'),
        port=os.getenv('POSTGRES_PORT', '5432'),
        database=os.getenv('POSTGRES_DB', 'knowledge_graph'),
        user=os.getenv('POSTGRES_USER', 'admin'),
        password=os.getenv('POSTGRES_PASSWORD')
    )


def get_platform_config() -> Dict[str, str]:
    """Get all platform configuration values."""
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT key, value FROM kg_api.platform_config")
                return {row['key']: row['value'] for row in cur.fetchall()}
    except Exception as e:
        print(f"{Colors.YELLOW}Warning: Could not read platform config: {e}{Colors.NC}")
        return {}


def set_platform_config(key: str, value: str, updated_by: str = 'platform.py'):
    """Set a platform configuration value."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT kg_api.set_platform_config(%s, %s, %s)",
                (key, value, updated_by)
            )
        conn.commit()


def detect_gpu() -> str:
    """Auto-detect GPU availability. Returns: nvidia, mac, or cpu."""
    import platform

    # Check for Mac
    if platform.system() == 'Darwin':
        return 'mac'

    # Check for NVIDIA GPU
    try:
        result = subprocess.run(
            ['nvidia-smi', '--query-gpu=name', '--format=csv,noheader'],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0 and result.stdout.strip():
            gpu_name = result.stdout.strip().split('\n')[0]
            print(f"{Colors.GREEN}Detected NVIDIA GPU: {gpu_name}{Colors.NC}")
            return 'nvidia'
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    return 'cpu'


def get_compose_files(dev_mode: bool, gpu_mode: str) -> list:
    """Get the list of docker-compose files for the given mode."""
    files = ['docker-compose.yml']

    if dev_mode:
        files.append('docker-compose.dev.yml')

    if gpu_mode == 'nvidia':
        files.append('docker-compose.gpu-nvidia.yml')
    elif gpu_mode == 'mac':
        files.append('docker-compose.override.mac.yml')
    # cpu mode: no additional files

    return files


def run_compose(compose_files: list, args: list, env_file: str = '/workspace/.env') -> int:
    """Run docker-compose with the given files and arguments."""
    cmd = ['docker-compose']

    for f in compose_files:
        cmd.extend(['-f', f])

    cmd.extend(['--env-file', env_file])
    cmd.extend(args)

    print(f"{Colors.BLUE}Running: {' '.join(cmd)}{Colors.NC}")

    result = subprocess.run(cmd, cwd='/workspace/docker')
    return result.returncode


def cmd_init(args):
    """Initialize platform configuration (first-time setup)."""
    print(f"\n{Colors.BOLD}Initializing platform configuration...{Colors.NC}\n")

    # Determine GPU mode
    gpu_mode = args.gpu
    if gpu_mode == 'auto':
        gpu_mode = detect_gpu()
        print(f"{Colors.BLUE}Auto-detected GPU mode: {gpu_mode}{Colors.NC}")

    # Save configuration
    set_platform_config('dev_mode', str(args.dev).lower())
    set_platform_config('gpu_mode', gpu_mode)
    set_platform_config('initialized_at', datetime.utcnow().isoformat())
    set_platform_config('initialized_by', 'quickstart' if args.quickstart else 'manual')

    compose_files = get_compose_files(args.dev, gpu_mode)
    set_platform_config('compose_files', ','.join(compose_files))

    print(f"\n{Colors.GREEN}Platform configuration saved:{Colors.NC}")
    print(f"  Dev mode: {args.dev}")
    print(f"  GPU mode: {gpu_mode}")
    print(f"  Compose files: {', '.join(compose_files)}")

    if args.start:
        print(f"\n{Colors.BOLD}Starting application containers...{Colors.NC}\n")
        return cmd_start(args)

    return 0


def cmd_start(args):
    """Start application containers using saved configuration."""
    config = get_platform_config()

    if not config.get('initialized_at'):
        print(f"{Colors.RED}Platform not initialized. Run 'platform.py init' first.{Colors.NC}")
        return 1

    dev_mode = config.get('dev_mode', 'false').lower() == 'true'
    gpu_mode = config.get('gpu_mode', 'cpu')

    # Allow overrides via command line
    if hasattr(args, 'dev') and args.dev is not None:
        dev_mode = args.dev
    if hasattr(args, 'gpu') and args.gpu and args.gpu != 'auto':
        gpu_mode = args.gpu

    compose_files = get_compose_files(dev_mode, gpu_mode)

    print(f"\n{Colors.BOLD}Starting platform...{Colors.NC}")
    print(f"  Mode: {'development' if dev_mode else 'production'}")
    print(f"  GPU: {gpu_mode}")
    print(f"  Compose files: {', '.join(compose_files)}\n")

    # Start API
    print(f"{Colors.BLUE}Starting API server...{Colors.NC}")
    rc = run_compose(compose_files, ['up', '-d', '--build', 'api'])
    if rc != 0:
        return rc

    # Wait for API health
    print(f"{Colors.BLUE}Waiting for API to be healthy...{Colors.NC}")
    for i in range(30):
        result = subprocess.run(
            ['docker', 'ps', '--format', '{{.Names}} {{.Status}}'],
            capture_output=True,
            text=True
        )
        if 'kg-api' in result.stdout and 'healthy' in result.stdout:
            print(f"{Colors.GREEN}API is healthy{Colors.NC}")
            break
        import time
        time.sleep(2)

    # Start web
    print(f"\n{Colors.BLUE}Starting web app...{Colors.NC}")
    rc = run_compose(compose_files, ['up', '-d', '--build', 'web'])

    print(f"\n{Colors.GREEN}Platform started successfully{Colors.NC}")
    print(f"\n  API: http://localhost:8000")
    print(f"  Web: http://localhost:3000\n")

    return rc


def cmd_stop(args):
    """Stop application containers (optionally keep infrastructure)."""
    config = get_platform_config()
    compose_files_str = config.get('compose_files', 'docker-compose.yml')
    compose_files = compose_files_str.split(',') if compose_files_str else ['docker-compose.yml']

    print(f"\n{Colors.BOLD}Stopping platform...{Colors.NC}\n")

    # Stop web first
    print(f"{Colors.BLUE}Stopping web app...{Colors.NC}")
    run_compose(compose_files, ['stop', 'web'])

    # Stop API
    print(f"{Colors.BLUE}Stopping API server...{Colors.NC}")
    run_compose(compose_files, ['stop', 'api'])

    if not args.keep_infra:
        # Stop infrastructure (but not operator - we're running in it!)
        print(f"{Colors.BLUE}Stopping infrastructure...{Colors.NC}")
        run_compose(compose_files, ['stop', 'garage'])
        run_compose(compose_files, ['stop', 'postgres'])
    else:
        print(f"{Colors.YELLOW}Keeping infrastructure running (--keep-infra){Colors.NC}")

    print(f"\n{Colors.GREEN}Platform stopped{Colors.NC}\n")
    return 0


def cmd_status(args):
    """Show platform status."""
    config = get_platform_config()

    print(f"\n{Colors.BOLD}Platform Configuration:{Colors.NC}")
    print(f"  Dev mode: {config.get('dev_mode', 'not set')}")
    print(f"  GPU mode: {config.get('gpu_mode', 'not set')}")
    print(f"  Initialized: {config.get('initialized_at', 'never')}")
    print(f"  Initialized by: {config.get('initialized_by', 'unknown')}")
    print(f"  Compose files: {config.get('compose_files', 'not set')}")

    print(f"\n{Colors.BOLD}Container Status:{Colors.NC}")
    subprocess.run(['docker', 'ps', '--format', 'table {{.Names}}\t{{.Status}}\t{{.Ports}}',
                   '--filter', 'name=kg-', '--filter', 'name=knowledge-graph'])

    return 0


def cmd_config(args):
    """Update platform configuration."""
    if args.dev is not None:
        set_platform_config('dev_mode', str(args.dev).lower())
        print(f"Set dev_mode = {args.dev}")

    if args.gpu:
        gpu_mode = args.gpu
        if gpu_mode == 'auto':
            gpu_mode = detect_gpu()
        set_platform_config('gpu_mode', gpu_mode)
        print(f"Set gpu_mode = {gpu_mode}")

    # Update compose files based on new config
    config = get_platform_config()
    dev_mode = config.get('dev_mode', 'false').lower() == 'true'
    gpu_mode = config.get('gpu_mode', 'cpu')
    compose_files = get_compose_files(dev_mode, gpu_mode)
    set_platform_config('compose_files', ','.join(compose_files))

    print(f"\n{Colors.GREEN}Configuration updated. Restart platform to apply changes.{Colors.NC}")
    return 0


def main():
    parser = argparse.ArgumentParser(
        description='Platform lifecycle management for Knowledge Graph System',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Initialize for development with NVIDIA GPU
  python platform.py init --dev --gpu nvidia --start

  # Initialize for production with auto-detected GPU
  python platform.py init --gpu auto --start

  # Start platform (uses saved config)
  python platform.py start

  # Stop platform but keep database running
  python platform.py stop --keep-infra

  # Change GPU mode
  python platform.py config --gpu cpu
        """
    )

    subparsers = parser.add_subparsers(dest='command', help='Commands')

    # init command
    init_parser = subparsers.add_parser('init', help='Initialize platform configuration')
    init_parser.add_argument('--dev', action='store_true', help='Enable development mode with hot reload')
    init_parser.add_argument('--gpu', choices=['auto', 'nvidia', 'mac', 'cpu'], default='auto',
                            help='GPU mode (default: auto-detect)')
    init_parser.add_argument('--start', action='store_true', help='Start platform after init')
    init_parser.add_argument('--quickstart', action='store_true', help='Mark as initialized via quickstart')

    # start command
    start_parser = subparsers.add_parser('start', help='Start platform containers')
    start_parser.add_argument('--dev', type=bool, help='Override dev mode')
    start_parser.add_argument('--gpu', choices=['auto', 'nvidia', 'mac', 'cpu'],
                             help='Override GPU mode')

    # stop command
    stop_parser = subparsers.add_parser('stop', help='Stop platform containers')
    stop_parser.add_argument('--keep-infra', action='store_true',
                            help='Keep infrastructure (postgres, garage) running')

    # status command
    subparsers.add_parser('status', help='Show platform status')

    # config command
    config_parser = subparsers.add_parser('config', help='Update platform configuration')
    config_parser.add_argument('--dev', type=lambda x: x.lower() == 'true',
                              help='Set dev mode (true/false)')
    config_parser.add_argument('--gpu', choices=['auto', 'nvidia', 'mac', 'cpu'],
                              help='Set GPU mode')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    commands = {
        'init': cmd_init,
        'start': cmd_start,
        'stop': cmd_stop,
        'status': cmd_status,
        'config': cmd_config,
    }

    return commands[args.command](args)


if __name__ == '__main__':
    sys.exit(main())
