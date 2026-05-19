"""
API Key Validation at Startup

Validates configured API keys during API startup and updates validation status
in the database (ADR-041). Validation failures are logged but do not block startup.
"""

import logging
from typing import Dict, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


# Key validation lives in the connector layer (ADR-800). These thin wrappers
# preserve the historical function names while delegating to the single
# source of truth so there is exactly one place that knows how to
# authenticate each provider, model-agnostically.

def validate_openai_key(api_key: str) -> tuple[bool, Optional[str]]:
    """Validate an OpenAI API key. Delegates to the connector layer."""
    from .ai_providers import validate_provider_key
    return validate_provider_key("openai", api_key)


def validate_anthropic_key(api_key: str) -> tuple[bool, Optional[str]]:
    """Validate an Anthropic API key. Delegates to the connector layer."""
    from .ai_providers import validate_provider_key
    return validate_provider_key("anthropic", api_key)


def validate_openrouter_key(api_key: str) -> tuple[bool, Optional[str]]:
    """Validate an OpenRouter API key. Delegates to the connector layer."""
    from .ai_providers import validate_provider_key
    return validate_provider_key("openrouter", api_key)


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
                    elif provider == 'openrouter':
                        is_valid, error_msg = validate_openrouter_key(api_key)
                    elif provider == 'garage':
                        # Garage credentials are "access_key:secret_key" format
                        # No API validation available, just check format
                        if ':' in api_key and len(api_key.split(':', 1)) == 2:
                            logger.info(f"   ✓ {provider}: Credentials retrieved (validation skipped)")
                            is_valid, error_msg = (True, None)
                        else:
                            logger.warning(f"   ⚠ {provider}: Invalid credential format (expected 'access:secret')")
                            is_valid, error_msg = (False, "Invalid format")
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
