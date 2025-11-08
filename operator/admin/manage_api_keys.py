#!/usr/bin/env python3
"""
API Key Management Script (ADR-031)

Manages encrypted API keys for AI providers (OpenAI, Anthropic).
Works with both Docker and non-Docker PostgreSQL deployments.

Usage:
    # Interactive mode - configure needed keys
    python3 manage_api_keys.py --interactive

    # List configured keys
    python3 manage_api_keys.py --list

    # Add specific key
    python3 manage_api_keys.py --add openai --key sk-...

    # Delete key
    python3 manage_api_keys.py --delete openai

Environment Variables:
    POSTGRES_HOST, POSTGRES_PORT, POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD
    ENCRYPTION_KEY - Master encryption key for encrypting API keys
"""

import sys
import os
import argparse
import getpass
from pathlib import Path

# Add project root to path
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from api.api.lib.age_client import AGEClient
from api.api.lib.encrypted_keys import EncryptedKeyStore, mask_api_key


def validate_api_key(provider: str, api_key: str) -> tuple[bool, str]:
    """
    Validate API key by making a minimal API call.

    Args:
        provider: 'openai' or 'anthropic'
        api_key: The API key to validate

    Returns:
        (is_valid, error_message)
    """
    try:
        if provider == "openai":
            # Validate OpenAI key format
            if not api_key.startswith("sk-"):
                return False, "Invalid OpenAI API key format (must start with 'sk-')"

            # Try making a simple API call
            import openai
            client = openai.OpenAI(api_key=api_key, max_retries=0, timeout=10.0)
            client.models.list()
            return True, ""

        elif provider == "anthropic":
            # Validate Anthropic key format
            if not api_key.startswith("sk-ant-"):
                return False, "Invalid Anthropic API key format (must start with 'sk-ant-')"

            # Try making a simple API call
            import anthropic
            client = anthropic.Anthropic(api_key=api_key, max_retries=0, timeout=10.0)
            client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=1,
                messages=[{"role": "user", "content": "test"}]
            )
            return True, ""

        else:
            return False, f"Unknown provider: {provider}"

    except ImportError as e:
        return False, f"Provider SDK not installed: {e}"
    except Exception as e:
        error_str = str(e)
        # Extract meaningful error message
        if "401" in error_str or "Unauthorized" in error_str or "authentication" in error_str.lower():
            return False, "Invalid API key (authentication failed)"
        elif "404" in error_str or "Not Found" in error_str:
            return False, "API endpoint not found (check provider SDK version)"
        elif "timeout" in error_str.lower():
            return False, "Request timed out (check network connection)"
        else:
            return False, f"Validation failed: {error_str}"


def list_keys(key_store: EncryptedKeyStore) -> None:
    """List configured API keys with masked values."""
    providers = key_store.list_providers(include_masked_keys=True)

    if not providers:
        print("No API keys configured")
        return

    print("\nConfigured API Keys:")
    print("-" * 60)
    for info in providers:
        provider = info['provider']
        masked_key = info.get('masked_key', '***')
        status = info.get('validation_status', 'unknown')
        updated = info.get('updated_at', 'unknown')

        print(f"  {provider.upper()}")
        print(f"    Key:        {masked_key}")
        print(f"    Status:     {status}")
        print(f"    Updated:    {updated}")
        print()


def add_key_interactive(key_store: EncryptedKeyStore, provider: str) -> bool:
    """
    Interactively prompt for API key and store it.

    Args:
        key_store: EncryptedKeyStore instance
        provider: 'openai' or 'anthropic'

    Returns:
        True if successful, False otherwise
    """
    print(f"\nConfigure {provider.upper()} API Key")
    print("-" * 60)

    # Check if key already exists
    if key_store.has_key(provider):
        print(f"⚠  {provider.upper()} API key already configured")
        try:
            existing_key = key_store.get_key(provider)
            masked = mask_api_key(existing_key)
            print(f"   Current key: {masked}")
        except Exception:
            print("   (Unable to retrieve existing key)")

        response = input("Replace existing key? [y/N]: ").strip().lower()
        if response not in ['y', 'yes']:
            print("Skipped")
            return False
        print()

    # Prompt for API key
    while True:
        api_key = getpass.getpass(f"Enter {provider.upper()} API key: ").strip()

        if not api_key:
            print("ERROR: API key cannot be empty")
            continue

        # Confirm key
        api_key_confirm = getpass.getpass(f"Confirm {provider.upper()} API key: ").strip()

        if api_key != api_key_confirm:
            print("ERROR: Keys do not match. Try again.\n")
            continue

        break

    # Validate key
    print(f"→ Validating {provider.upper()} API key...")
    is_valid, error_msg = validate_api_key(provider, api_key)

    if not is_valid:
        print(f"✗ Validation failed: {error_msg}")
        return False

    print("✓ API key validated")

    # Store encrypted key
    print(f"→ Storing encrypted key...")
    try:
        key_store.store_key(provider, api_key)
        key_store.update_validation_status(provider, "valid")
        print(f"✓ {provider.upper()} API key stored successfully")
        return True
    except Exception as e:
        print(f"✗ Failed to store key: {e}")
        return False


def delete_key(key_store: EncryptedKeyStore, provider: str) -> bool:
    """Delete API key for provider."""
    if not key_store.has_key(provider):
        print(f"No {provider.upper()} API key configured")
        return False

    try:
        key_store.delete_key(provider)
        print(f"✓ Deleted {provider.upper()} API key")
        return True
    except Exception as e:
        print(f"✗ Failed to delete key: {e}")
        return False


def interactive_mode() -> int:
    """
    Interactive mode - prompts for which keys to configure based on provider setup.

    Returns:
        Exit code (0 = success, 1 = error)
    """
    try:
        # Connect to database
        client = AGEClient()
        conn = client.pool.getconn()

        try:
            # Initialize key store
            key_store = EncryptedKeyStore(conn)

            # Query configured providers
            with conn.cursor() as cur:
                cur.execute("SELECT provider FROM kg_config.extraction_config WHERE is_active = true LIMIT 1")
                row = cur.fetchone()
                extraction_provider = row[0] if row else None

                cur.execute("SELECT provider FROM kg_config.embedding_config WHERE is_active = true LIMIT 1")
                row = cur.fetchone()
                embedding_provider = row[0] if row else None

            # Determine which keys are needed
            needs_openai = extraction_provider == "openai" or embedding_provider == "openai"
            needs_anthropic = extraction_provider == "anthropic"

            if not needs_openai and not needs_anthropic:
                print("✓ No API keys needed for current configuration")
                print("  (Ollama/Local providers don't require API keys)")
                return 0

            print("\nAPI Keys Configuration")
            print("=" * 60)
            print(f"Extraction Provider:  {extraction_provider or 'not configured'}")
            print(f"Embedding Provider:   {embedding_provider or 'not configured'}")
            print()

            # Configure needed keys
            success = True

            if needs_openai:
                print("\n" + "=" * 60)
                if not add_key_interactive(key_store, "openai"):
                    success = False

            if needs_anthropic:
                print("\n" + "=" * 60)
                if not add_key_interactive(key_store, "anthropic"):
                    success = False

            print("\n" + "=" * 60)
            if success:
                print("✓ API key configuration complete")
                return 0
            else:
                print("⚠  Some keys were not configured")
                return 1

        finally:
            client.pool.putconn(conn)

    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1


def main():
    parser = argparse.ArgumentParser(
        description="Manage encrypted API keys for AI providers",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Interactive mode (configure needed keys)
  python3 manage_api_keys.py --interactive

  # List configured keys
  python3 manage_api_keys.py --list

  # Add specific key
  python3 manage_api_keys.py --add openai --key sk-...

  # Delete key
  python3 manage_api_keys.py --delete openai
        """
    )

    parser.add_argument(
        '--interactive',
        action='store_true',
        help='Interactive mode - prompt for keys based on provider configuration'
    )
    parser.add_argument(
        '--list',
        action='store_true',
        help='List configured API keys with masked values'
    )
    parser.add_argument(
        '--add',
        metavar='PROVIDER',
        choices=['openai', 'anthropic'],
        help='Add API key for provider (openai, anthropic)'
    )
    parser.add_argument(
        '--key',
        metavar='KEY',
        help='API key to add (use with --add)'
    )
    parser.add_argument(
        '--delete',
        metavar='PROVIDER',
        choices=['openai', 'anthropic'],
        help='Delete API key for provider'
    )

    args = parser.parse_args()

    # Validate arguments
    if not any([args.interactive, args.list, args.add, args.delete]):
        parser.print_help()
        return 1

    if args.add and not args.key:
        print("ERROR: --add requires --key", file=sys.stderr)
        return 1

    try:
        # Interactive mode
        if args.interactive:
            return interactive_mode()

        # Connect to database
        client = AGEClient()
        conn = client.pool.getconn()

        try:
            key_store = EncryptedKeyStore(conn)

            # List keys
            if args.list:
                list_keys(key_store)
                return 0

            # Add key
            if args.add:
                print(f"→ Validating {args.add.upper()} API key...")
                is_valid, error_msg = validate_api_key(args.add, args.key)

                if not is_valid:
                    print(f"✗ Validation failed: {error_msg}", file=sys.stderr)
                    return 1

                print("✓ API key validated")

                print(f"→ Storing encrypted key...")
                key_store.store_key(args.add, args.key)
                key_store.update_validation_status(args.add, "valid")
                print(f"✓ {args.add.upper()} API key stored successfully")
                return 0

            # Delete key
            if args.delete:
                return 0 if delete_key(key_store, args.delete) else 1

        finally:
            client.pool.putconn(conn)

    except ValueError as e:
        # Handle specific errors (like missing encryption key)
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
