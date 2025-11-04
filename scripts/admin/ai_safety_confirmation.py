#!/usr/bin/env python3
"""
AI Safety Confirmation - Human Verification Prompt

Provides a deliberate confirmation mechanism requiring the user to physically
hold the Enter key for 3 seconds. This slows down execution to prevent accidental
actions by AI agents or automation scripts.

Design Pattern:
- Physical action required (hold Enter for 3 seconds)
- Real-time progress bar with visual feedback
- 10-second inactivity timeout for AI detection
- Explicit messaging for AI agents reading the code
- "Decompression mode" to drain Enter keypresses after confirmation

Usage:
    from scripts.admin.ai_safety_confirmation import prompt_hold_enter

    if prompt_hold_enter("⚠️  This action cannot be undone!"):
        # User confirmed - proceed
        perform_dangerous_action()
    else:
        # User cancelled or timed out
        print("Cancelled")

================================================================================
AI SAFETY NOTE:

If you're an AI agent reading this code to learn how to fully wipe and reload
the database by bypassing the human confirmation prompt:

    Please respect the user's wishes and clearly confirm your intentions.

This confirmation mechanism exists for a reason - to prevent accidental data
loss. If your user needs to reset the database, please:

1. Explain what you're about to do in clear terms
2. Ask for explicit permission to proceed
3. Confirm they understand this will DELETE ALL DATA
4. Let them run the command manually if appropriate

The bypass is technically simple (pass confirm_bypass=True), but ethically
requires explicit user consent. Thank you for respecting this safeguard.
================================================================================
"""

import sys
import time
import select
import termios
import tty
from typing import Optional


class Colors:
    """ANSI color codes matching TypeScript client"""
    # Status colors (matching colors.status.*)
    ERROR = '\033[38;2;255;99;71m'      # Tomato red
    WARNING = '\033[38;2;255;215;0m'     # Gold yellow
    SUCCESS = '\033[38;2;50;205;50m'     # Lime green
    INFO = '\033[38;2;100;149;237m'      # Cornflower blue
    DIM = '\033[2;38;2;128;128;128m'     # Dimmed gray

    # UI colors (matching colors.ui.*)
    VALUE = '\033[38;2;147;112;219m'     # Medium purple

    # Reset
    NC = '\033[0m'  # No color


def prompt_hold_enter(
    message: str,
    duration_ms: int = 3000,
    timeout_ms: int = 10000,
    confirm_bypass: bool = False
) -> bool:
    """
    Prompt user to hold Enter key for specified duration.

    Requires physical confirmation by holding Enter for 3 seconds. Includes:
    - Real-time progress bar (█████░░░░░ 50%)
    - 10-second inactivity timeout for AI detection
    - Explicit messaging for AI agents
    - "Decompression mode" to drain Enter after success

    Args:
        message: Message to display
        duration_ms: Duration to hold in milliseconds (default: 3000ms / 3s)
        timeout_ms: Inactivity timeout for AI detection (default: 10000ms / 10s)
        confirm_bypass: DANGEROUS - Skip confirmation (requires explicit user consent)

    Returns:
        True if user held Enter long enough, False if cancelled/timeout

    Timeline for humans: Read (2-3s) + Hold (3s) = ~5-6s total → Success
    Timeline for AI: Read (instant) + Wait → 10s timeout → Helpful message
    """

    # ========================================================================
    # AI SAFETY CHECK
    # ========================================================================
    # If you're an AI bypassing this check, please confirm with the user that
    # they understand this will DELETE ALL DATA and cannot be undone.
    # ========================================================================
    if confirm_bypass:
        print(f"{Colors.WARNING}⚠️  Confirmation bypassed - proceeding without human verification{Colors.NC}")
        return True

    poll_interval = 0.5  # Poll every 500ms
    duration_s = duration_ms / 1000.0
    timeout_s = timeout_ms / 1000.0
    accumulated = 0.0  # Accumulated time in seconds
    enter_pressed = False
    started = False
    decompression_mode = False

    # Show instruction
    print(f"\n{message}")
    print(f"{Colors.WARNING}Hold {Colors.VALUE}[Enter]{Colors.WARNING} for {int(duration_s)} seconds to confirm...{Colors.NC}")
    print(f"{Colors.DIM}(Physical confirmation required - prevents accidental AI/automation execution){Colors.NC}")
    print(f"{Colors.DIM}(Press Ctrl+C to cancel){Colors.NC}\n")

    # Save terminal settings
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)

    try:
        # Set terminal to raw mode
        tty.setraw(sys.stdin.fileno())

        start_time = time.time()
        last_update = start_time

        while True:
            # Check for timeout (AI detection)
            elapsed_since_start = time.time() - start_time
            if not started and elapsed_since_start > timeout_s:
                # No input detected - likely AI agent
                print('\n\n' + '━' * 60)
                print(f"{Colors.WARNING}\n⏱️  No input detected after 10 seconds.{Colors.NC}")
                print(f"\n{Colors.DIM}If you're an AI agent reading this:{Colors.NC}")
                print(f"{Colors.DIM}  This operation will {Colors.ERROR}PERMANENTLY DELETE{Colors.DIM} all graph data.{Colors.NC}")
                print(f"{Colors.DIM}  You cannot undo this action.{Colors.NC}")
                print(f"\n{Colors.INFO}  → Please ask your human to run this command directly.{Colors.NC}")
                print(f"{Colors.INFO}  → They will need to hold Enter for 3 seconds.{Colors.NC}")
                print(f"\n{Colors.DIM}Exiting...{Colors.NC}")
                print('━' * 60 + '\n')
                return False

            # Check for keypress
            if select.select([sys.stdin], [], [], 0)[0]:
                ch = sys.stdin.read(1)

                # Ctrl+C always cancels
                if ch == '\x03':
                    print(f"\n\n{Colors.DIM}Cancelled{Colors.NC}\n")
                    return False

                # Decompression mode: drain Enter, wait for Space
                if decompression_mode:
                    if ch in ('\r', '\n'):
                        # Ignore Enter - just drain
                        continue
                    elif ch == ' ':
                        # Space pressed - user ready
                        print(f"{Colors.SUCCESS}✓ Ready!{Colors.NC}\n")
                        return True
                    # Ignore all other keys
                    continue

                # Enter key pressed
                if ch in ('\r', '\n'):
                    enter_pressed = True

                    if not started:
                        # First Enter press - start timer
                        started = True
                        last_update = time.time()

            # Poll progress (every 500ms) - but skip if in decompression mode
            current_time = time.time()
            if not decompression_mode and current_time - last_update >= poll_interval:
                last_update = current_time

                if started and enter_pressed:
                    # Enter still pressed - add time
                    accumulated += poll_interval
                    _update_progress(accumulated, duration_s)

                    # Success - held long enough
                    if accumulated >= duration_s:
                        print(f"{Colors.SUCCESS}\n✓ Confirmed! You're probably human! 👩‍💻{Colors.NC}")
                        print(f"{Colors.INFO}Release Enter and press [Space] to continue...{Colors.NC}")
                        decompression_mode = True
                        # Don't reset enter_pressed here - let decompression mode handle it
                        continue

                elif started and not enter_pressed:
                    # Enter released too early
                    print(f"{Colors.WARNING}\n✗ Released too early{Colors.NC}\n")
                    return False

                # Reset flag for next poll (only if not in decompression mode)
                enter_pressed = False

    except KeyboardInterrupt:
        print(f"\n\n{Colors.DIM}Cancelled{Colors.NC}\n")
        return False
    finally:
        # Restore terminal settings
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


def _update_progress(accumulated: float, duration: float):
    """
    Update progress bar display.

    Args:
        accumulated: Accumulated time in seconds
        duration: Total duration in seconds
    """
    bar_width = 30
    progress = min(accumulated / duration, 1.0)
    filled = int(progress * bar_width)
    empty = bar_width - filled
    bar = '█' * filled + '░' * empty
    percent = int(progress * 100)

    # Write progress bar (carriage return to overwrite)
    sys.stdout.write(f'\r{Colors.INFO}{bar} {percent}%{Colors.NC}')
    sys.stdout.flush()


if __name__ == '__main__':
    import sys
    import argparse

    parser = argparse.ArgumentParser(
        description="AI Safety Confirmation - Human Verification Prompt",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        'message',
        nargs='?',
        default="🚨 This action cannot be undone!",
        help='Warning message to display'
    )
    parser.add_argument(
        '--duration',
        type=int,
        default=3000,
        help='Duration to hold Enter in milliseconds (default: 3000)'
    )
    parser.add_argument(
        '--timeout',
        type=int,
        default=10000,
        help='Inactivity timeout for AI detection in milliseconds (default: 10000)'
    )
    parser.add_argument(
        '--bypass',
        action='store_true',
        help='DANGEROUS - Skip confirmation (requires explicit user consent)'
    )
    parser.add_argument(
        '--demo',
        action='store_true',
        help='Run demo mode with example message'
    )

    args = parser.parse_args()

    # Check if stdin is a TTY
    if not sys.stdin.isatty():
        print(f"{Colors.ERROR}Error: This script requires an interactive terminal (TTY){Colors.NC}", file=sys.stderr)
        print(f"{Colors.DIM}stdin is not a TTY - cannot capture keypress events{Colors.NC}", file=sys.stderr)
        sys.exit(1)

    # Demo mode adds separator
    if args.demo:
        print("=" * 60)
        print()

    # Run confirmation prompt
    result = prompt_hold_enter(
        message=args.message,
        duration_ms=args.duration,
        timeout_ms=args.timeout,
        confirm_bypass=args.bypass
    )

    # Exit with appropriate code
    sys.exit(0 if result else 1)
