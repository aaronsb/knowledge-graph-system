"""
API Key Validation at Startup

Validates configured API keys during API startup and updates validation status
in the database (ADR-041). Validation failures are logged but do not block startup.
"""

import logging
from typing import Dict, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


def validate_openai_key(api_key: str) -> tuple[bool, Optional[str]]:
    """
    Validate OpenAI API key by making a minimal API call.

    Args:
        api_key: The OpenAI API key to validate

    Returns:
        Tuple of (is_valid, error_message)
        - (True, None) if key is valid
        - (False, error_message) if key is invalid
    """
    try:
        import openai
        client = openai.OpenAI(api_key=api_key)

        # Make minimal API call (1 token)
        client.chat.completions.create(
            model="gpt-4o-mini",
            max_tokens=1,
            messages=[{"role": "user", "content": "test"}]
        )

        return (True, None)

    except openai.AuthenticationError as e:
        return (False, f"Authentication failed: {str(e)}")
    except openai.PermissionDeniedError as e:
        return (False, f"Permission denied: {str(e)}")
    except openai.RateLimitError as e:
        # Rate limit means the key is valid, just throttled
        logger.warning(f"OpenAI rate limit hit during validation: {e}")
        return (True, None)
    except Exception as e:
        return (False, f"Validation error: {str(e)}")


def validate_anthropic_key(api_key: str) -> tuple[bool, Optional[str]]:
    """
    Validate Anthropic API key by making a minimal API call.

    Args:
        api_key: The Anthropic API key to validate

    Returns:
        Tuple of (is_valid, error_message)
        - (True, None) if key is valid
        - (False, error_message) if key is invalid
    """
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)

        # Make minimal API call (1 token)
        client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=1,
            messages=[{"role": "user", "content": "test"}]
        )

        return (True, None)

    except anthropic.AuthenticationError as e:
        return (False, f"Authentication failed: {str(e)}")
    except anthropic.PermissionDeniedError as e:
        return (False, f"Permission denied: {str(e)}")
    except anthropic.RateLimitError as e:
        # Rate limit means the key is valid, just throttled
        logger.warning(f"Anthropic rate limit hit during validation: {e}")
        return (True, None)
    except Exception as e:
        return (False, f"Validation error: {str(e)}")


def validate_api_keys_at_startup() -> Dict[str, bool]:
    """
    Validate all configured API keys at startup (ADR-041).

    This function:
    1. Loads all configured API keys from the database
    2. Validates each key by making a minimal API call
    3. Updates validation_status in the database
    4. Logs results clearly
    5. Does NOT block startup on invalid keys (graceful degradation)

    Returns:
        Dict mapping provider names to validation status (True/False)
        Example: {'openai': True, 'anthropic': False}
    """
    from .age_client import AGEClient
    from .encrypted_keys import EncryptedKeyStore

    logger.info("🔐 Validating API keys at startup...")

    validation_results = {}

    try:
        client = AGEClient()
        conn = client.pool.getconn()

        try:
            # Initialize key store
            try:
                key_store = EncryptedKeyStore(conn)
            except ValueError as e:
                logger.warning(f"⚠️  Encryption key not configured: {e}")
                logger.info("   Skipping API key validation")
                return validation_results

            # Get list of configured providers
            providers = key_store.list_providers(include_masked_keys=False)

            if not providers:
                logger.info("   No API keys configured")
                return validation_results

            # Validate each provider's key
            for provider_info in providers:
                provider = provider_info['provider']

                try:
                    # Get decrypted key
                    api_key = key_store.get_key(provider)

                    # Validate based on provider
                    if provider == 'openai':
                        is_valid, error_msg = validate_openai_key(api_key)
                    elif provider == 'anthropic':
                        is_valid, error_msg = validate_anthropic_key(api_key)
                    else:
                        logger.warning(f"   Unknown provider: {provider}, skipping validation")
                        continue

                    # Update validation status in database
                    status = 'valid' if is_valid else 'invalid'
                    key_store.update_validation_status(provider, status, error_msg)

                    # Log result
                    if is_valid:
                        logger.info(f"   ✅ {provider}: API key validated successfully")
                    else:
                        logger.warning(f"   ❌ {provider}: API key validation failed")
                        logger.warning(f"      Error: {error_msg}")
                        logger.warning(f"      System will continue but {provider} operations may fail")

                    validation_results[provider] = is_valid

                except ValueError as e:
                    logger.error(f"   ❌ {provider}: Failed to retrieve key - {e}")
                    validation_results[provider] = False
                except Exception as e:
                    logger.error(f"   ❌ {provider}: Validation error - {e}")
                    validation_results[provider] = False

        finally:
            client.pool.putconn(conn)

    except Exception as e:
        logger.error(f"⚠️  API key validation failed: {e}")
        logger.info("   System will continue without validated keys")

    # Summary
    if validation_results:
        valid_count = sum(1 for v in validation_results.values() if v)
        total_count = len(validation_results)
        logger.info(f"🔐 API key validation complete: {valid_count}/{total_count} valid")

    return validation_results
