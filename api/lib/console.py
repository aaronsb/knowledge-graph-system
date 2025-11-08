"""
Console output utilities - Colors, formatting, and progress indicators

Provides consistent terminal output formatting across CLI and admin tools.
Extracted from cli.py to enable reuse in GUI/web interfaces.
"""

from typing import Optional


class Colors:
    """ANSI color codes for terminal output"""
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


class Console:
    """Console output helper methods"""

    @staticmethod
    def success(msg: str):
        """Print success message in green"""
        print(f"{Colors.OKGREEN}{msg}{Colors.ENDC}")

    @staticmethod
    def error(msg: str):
        """Print error message in red"""
        print(f"{Colors.FAIL}{msg}{Colors.ENDC}")

    @staticmethod
    def warning(msg: str):
        """Print warning message in yellow"""
        print(f"{Colors.WARNING}{msg}{Colors.ENDC}")

    @staticmethod
    def info(msg: str):
        """Print info message in blue"""
        print(f"{Colors.OKBLUE}{msg}{Colors.ENDC}")

    @staticmethod
    def header(msg: str):
        """Print header in magenta"""
        print(f"{Colors.HEADER}{msg}{Colors.ENDC}")

    @staticmethod
    def bold(msg: str):
        """Print bold text"""
        print(f"{Colors.BOLD}{msg}{Colors.ENDC}")

    @staticmethod
    def section(title: str):
        """Print section header with separator"""
        print(f"\n{Colors.HEADER}{Colors.BOLD}{title}{Colors.ENDC}")
        print(f"{Colors.HEADER}{'=' * len(title)}{Colors.ENDC}\n")

    @staticmethod
    def key_value(key: str, value: str, key_color: str = Colors.BOLD, value_color: str = Colors.OKCYAN):
        """Print key-value pair with formatting"""
        print(f"{key_color}{key}:{Colors.ENDC} {value_color}{value}{Colors.ENDC}")

    @staticmethod
    def progress(current: int, total: int, prefix: str = "Progress"):
        """Print progress indicator"""
        percentage = (current / total) * 100 if total > 0 else 0
        bar_length = 40
        filled = int(bar_length * current / total) if total > 0 else 0
        bar = '█' * filled + '░' * (bar_length - filled)
        print(f"\r{prefix}: {Colors.OKBLUE}{bar}{Colors.ENDC} {percentage:.1f}% ({current}/{total})", end='', flush=True)
        if current >= total:
            print()  # New line when complete

    @staticmethod
    def confirm(prompt: str, auto_yes: bool = False) -> bool:
        """Interactive confirmation prompt"""
        if auto_yes:
            print(f"{prompt} [Y/n]: y (auto-confirmed)")
            return True

        response = input(f"{Colors.WARNING}{prompt} [Y/n]:{Colors.ENDC} ").strip().lower()
        return response in ('', 'y', 'yes')
