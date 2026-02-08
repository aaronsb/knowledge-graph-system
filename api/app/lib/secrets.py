"""
Secrets management with Docker/Podman secrets support (ADR-031).

Provides fallback chain for loading secrets:
1. Docker/Podman secrets (/run/secrets/<name>)
2. Environment variable file paths (e.g., OAUTH_SIGNING_KEY_FILE)
3. Direct environment variables (e.g., OAUTH_SIGNING_KEY)
4. .env file (development fallback)

This maintains backward compatibility while supporting production secret management.
"""

import os
from pathlib import Path
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class SecretManager:
    """Load secrets from multiple sources with fallback chain"""

    @staticmethod
    def load_secret(secret_name: str, env_var: Optional[str] = None, required: bool = True) -> Optional[str]:
        """
        Load secret from multiple sources in priority order.

        Args:
            secret_name: Name of the Docker/Podman secret (e.g., "oauth_signing_key")
            env_var: Optional environment variable name (e.g., "OAUTH_SIGNING_KEY")
            required: Whether to raise ValueError if secret not found (default: True)

        Returns:
            Secret value as string, or None if not required and not found

        Raises:
            ValueError: If required=True and secret cannot be found

        Priority order:
        1. Docker/Podman secret file (/run/secrets/<secret_name>)
        2. Environment variable file path (e.g., OAUTH_SIGNING_KEY_FILE)
        3. Environment variable value (e.g., OAUTH_SIGNING_KEY)
        4. .env file (development only)
        """
        # Try Docker/Podman secrets first (production)
        secret_path = Path(f"/run/secrets/{secret_name}")
        if secret_path.exists():
            try:
                value = secret_path.read_text().strip()
                logger.debug(f"Loaded secret '{secret_name}' from Docker/Podman secrets")
                return value
            except Exception as e:
                logger.warning(f"Failed to read secret from {secret_path}: {e}")

        # Try environment variable pointing to file
        env_name_file = env_var or f"{secret_name.upper()}_FILE"
        file_path_str = os.getenv(env_name_file)
        if file_path_str:
            file_path = Path(file_path_str)
            if file_path.exists():
                try:
                    value = file_path.read_text().strip()
                    logger.debug(f"Loaded secret '{secret_name}' from file: {file_path}")
                    return value
                except Exception as e:
                    logger.warning(f"Failed to read secret from {file_path}: {e}")

        # Try environment variable with value directly
        env_name_direct = env_var or secret_name.upper()
        value = os.getenv(env_name_direct)
        if value:
            logger.debug(f"Loaded secret '{secret_name}' from environment variable: {env_name_direct}")
            return value

        # Development fallback: .env file
        if os.path.exists(".env"):
            try:
                from dotenv import load_dotenv
                load_dotenv()
                value = os.getenv(env_name_direct)
                if value:
                    logger.debug(f"Loaded secret '{secret_name}' from .env file")
                    return value
            except ImportError:
                logger.debug("python-dotenv not available, skipping .env file")
            except Exception as e:
                logger.warning(f"Failed to load .env file: {e}")

        # Not found
        if required:
            raise ValueError(
                f"Secret '{secret_name}' not found. Tried:\n"
                f"  - /run/secrets/{secret_name}\n"
                f"  - ${env_name_file}\n"
                f"  - ${env_name_direct}\n"
                f"  - .env file\n"
                f"For production: use Docker/Podman secrets\n"
                f"For development: set ${env_name_direct} or use .env file"
            )

        logger.debug(f"Secret '{secret_name}' not found (optional)")
        return None


# Lazy loading of secrets - only loaded when accessed
_secrets_cache = {}


def get_oauth_signing_key() -> str:
    """Get OAuth signing key for access token generation (ADR-054)"""
    if 'oauth_signing_key' not in _secrets_cache:
        _secrets_cache['oauth_signing_key'] = SecretManager.load_secret("oauth_signing_key", "OAUTH_SIGNING_KEY")
    return _secrets_cache['oauth_signing_key']


def get_encryption_key() -> str:
    """Get master encryption key for API keys (ADR-031)"""
    if 'encryption_key' not in _secrets_cache:
        _secrets_cache['encryption_key'] = SecretManager.load_secret("encryption_master_key", "ENCRYPTION_KEY")
    return _secrets_cache['encryption_key']


def get_postgres_password() -> str:
    """Get PostgreSQL password"""
    if 'postgres_password' not in _secrets_cache:
        _secrets_cache['postgres_password'] = SecretManager.load_secret("postgres_password", "POSTGRES_PASSWORD")
    return _secrets_cache['postgres_password']


def get_internal_key_service_secret() -> str:
    """Get internal key service authorization token (ADR-031)"""
    if 'internal_key_service_secret' not in _secrets_cache:
        _secrets_cache['internal_key_service_secret'] = SecretManager.load_secret(
            "internal_key_service_secret",
            "INTERNAL_KEY_SERVICE_SECRET"
        )
    return _secrets_cache['internal_key_service_secret']


# Backward compatibility: module-level variables
# These will raise ValueError on import if secrets not available
# For optional loading, use the get_*() functions instead
try:
    OAUTH_SIGNING_KEY = get_oauth_signing_key()
except ValueError:
    # Allow import to succeed even if OAuth not configured (for setup scripts)
    logger.warning("OAUTH_SIGNING_KEY not configured - authentication will not work")
    OAUTH_SIGNING_KEY = None

try:
    ENCRYPTION_KEY = get_encryption_key()
except ValueError:
    # Development fallback: generate a temporary encryption key
    # This allows testing without Docker secrets configured
    import base64
    import secrets as crypto_secrets

    logger.warning(
        "ENCRYPTION_KEY not configured - generating temporary key for development. "
        "For production, configure Docker/Podman secrets or set ENCRYPTION_KEY env var."
    )
    # Generate a Fernet-compatible key (32 bytes, base64-encoded)
    temp_key = base64.urlsafe_b64encode(crypto_secrets.token_bytes(32))
    ENCRYPTION_KEY = temp_key.decode()
    # Store in cache so get_encryption_key() returns this value
    _secrets_cache['encryption_key'] = ENCRYPTION_KEY
    logger.info(f"Generated temporary encryption key (will be different on restart)")

try:
    POSTGRES_PASSWORD = get_postgres_password()
except ValueError:
    # Try direct env var without secrets manager (development without Docker secrets)
    POSTGRES_PASSWORD = os.environ.get("POSTGRES_PASSWORD")
    if POSTGRES_PASSWORD is None:
        raise ValueError(
            "POSTGRES_PASSWORD is not set. Configure via Docker/Podman secrets "
            "or set the POSTGRES_PASSWORD environment variable."
        )
    logger.warning("Using fallback PostgreSQL password from POSTGRES_PASSWORD env var")

try:
    INTERNAL_KEY_SERVICE_SECRET = get_internal_key_service_secret()
except ValueError:
    # Development fallback: generate a temporary service token
    # This allows testing without Docker secrets configured
    import base64
    import secrets as crypto_secrets

    logger.warning(
        "INTERNAL_KEY_SERVICE_SECRET not configured - generating temporary token for development. "
        "For production, configure Docker/Podman secrets or set INTERNAL_KEY_SERVICE_SECRET env var."
    )
    # Generate a secure random token
    temp_token = base64.urlsafe_b64encode(crypto_secrets.token_bytes(32))
    INTERNAL_KEY_SERVICE_SECRET = temp_token.decode()
    # Store in cache so get_internal_key_service_secret() returns this value
    _secrets_cache['internal_key_service_secret'] = INTERNAL_KEY_SERVICE_SECRET
    logger.info(f"Generated temporary internal service token (will be different on restart)")
