"""
Secrets management with Docker/Podman secrets support (ADR-031).

Provides fallback chain for loading secrets:
1. Docker/Podman secrets (/run/secrets/<name>)
2. Environment variable file paths (e.g., JWT_SECRET_FILE)
3. Direct environment variables (e.g., JWT_SECRET_KEY)
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
            secret_name: Name of the Docker/Podman secret (e.g., "jwt_secret")
            env_var: Optional environment variable name (e.g., "JWT_SECRET_KEY")
            required: Whether to raise ValueError if secret not found (default: True)

        Returns:
            Secret value as string, or None if not required and not found

        Raises:
            ValueError: If required=True and secret cannot be found

        Priority order:
        1. Docker/Podman secret file (/run/secrets/<secret_name>)
        2. Environment variable file path (e.g., JWT_SECRET_FILE)
        3. Environment variable value (e.g., JWT_SECRET_KEY)
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


def get_jwt_secret() -> str:
    """Get JWT secret for authentication (ADR-027)"""
    if 'jwt_secret' not in _secrets_cache:
        _secrets_cache['jwt_secret'] = SecretManager.load_secret("jwt_secret", "JWT_SECRET_KEY")
    return _secrets_cache['jwt_secret']


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


# Backward compatibility: module-level variables
# These will raise ValueError on import if secrets not available
# For optional loading, use the get_*() functions instead
try:
    JWT_SECRET = get_jwt_secret()
except ValueError:
    # Allow import to succeed even if JWT not configured (for setup scripts)
    logger.warning("JWT_SECRET not configured - authentication will not work")
    JWT_SECRET = None

try:
    ENCRYPTION_KEY = get_encryption_key()
except ValueError:
    # Allow import to succeed - encrypted keys optional until configured
    logger.info("ENCRYPTION_KEY not configured - encrypted key storage not available")
    ENCRYPTION_KEY = None

try:
    POSTGRES_PASSWORD = get_postgres_password()
except ValueError:
    # Try without secrets for development
    POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "password")
    logger.warning(f"Using fallback PostgreSQL password from POSTGRES_PASSWORD env var")
