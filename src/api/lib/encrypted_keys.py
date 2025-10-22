"""
System API key storage with encryption at rest (ADR-031).

Manages shard-scoped LLM API keys (OpenAI, Anthropic) with Fernet encryption.
Keys are encrypted using the master key from Docker/Podman secrets and stored
in PostgreSQL. This protects against database dumps and backup theft.

Architecture:
- One shard = one set of system-wide API keys
- Admin-managed via API endpoints
- Encrypted at rest with Fernet (AES-128-CBC + HMAC-SHA256)
- Master key stored in container secrets (not in database)
"""

import logging
from datetime import datetime
from typing import Optional, List, Dict
from cryptography.fernet import Fernet, InvalidToken
import psycopg2
from psycopg2.extensions import connection as PgConnection

from .secrets import get_encryption_key

logger = logging.getLogger(__name__)


def mask_api_key(plaintext_key: str) -> str:
    """
    Mask API key for display, showing only prefix and last 6 characters (ADR-041).

    Examples:
        "sk-proj-abc123def456ghi789" → "sk-proj-...ghi789"
        "sk-ant-abc123def456ghi789" → "sk-ant-...ghi789"
        "sk-abc123def456ghi789" → "sk-...ghi789"

    Args:
        plaintext_key: The plaintext API key

    Returns:
        Masked key showing prefix + "..." + last 6 chars
    """
    if not plaintext_key or len(plaintext_key) < 10:
        return "***"

    # Determine prefix
    if plaintext_key.startswith("sk-ant-"):
        prefix = "sk-ant-"
    elif plaintext_key.startswith("sk-proj-"):
        prefix = "sk-proj-"
    elif plaintext_key.startswith("sk-"):
        prefix = "sk-"
    else:
        prefix = ""

    # Get last 6 characters
    suffix = plaintext_key[-6:]

    return f"{prefix}...{suffix}"


class EncryptedKeyStore:
    """Manage system-wide API keys with encryption at rest"""

    def __init__(self, db_connection: PgConnection):
        """
        Initialize encrypted key store.

        Args:
            db_connection: PostgreSQL database connection

        Raises:
            ValueError: If encryption key not configured

        Note:
            The system_api_keys table must already exist (created by migration 005).
            See schema/migrations/005_add_api_key_validation.sql
        """
        self.db = db_connection

        # Get encryption key from secrets
        encryption_key = get_encryption_key()
        if not encryption_key:
            raise ValueError(
                "Encryption master key not configured. "
                "Set ENCRYPTION_KEY environment variable or configure Docker/Podman secrets."
            )

        # Initialize Fernet cipher
        try:
            self.cipher = Fernet(encryption_key.encode())
        except Exception as e:
            raise ValueError(f"Invalid encryption key format: {e}")

    def store_key(self, provider: str, plaintext_key: str) -> None:
        """
        Encrypt and store system API key.

        Args:
            provider: Provider name ('openai' or 'anthropic')
            plaintext_key: The actual API key

        Raises:
            ValueError: If encryption fails or database error occurs
        """
        try:
            # Encrypt the key
            encrypted = self.cipher.encrypt(plaintext_key.encode())

            # Store in database
            with self.db.cursor() as cur:
                cur.execute("""
                    INSERT INTO kg_api.system_api_keys (provider, encrypted_key)
                    VALUES (%s, %s)
                    ON CONFLICT (provider)
                    DO UPDATE SET
                        encrypted_key = EXCLUDED.encrypted_key,
                        updated_at = NOW()
                """, (provider, encrypted))
                self.db.commit()

            logger.info(f"Stored encrypted API key for provider: {provider}")

        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to store API key for {provider}: {e}")
            raise ValueError(f"Failed to store API key: {e}")

    def get_key(self, provider: str) -> str:
        """
        Decrypt and return system API key.

        Args:
            provider: Provider name ('openai' or 'anthropic')

        Returns:
            Plaintext API key

        Raises:
            ValueError: If key not found or decryption fails
        """
        try:
            with self.db.cursor() as cur:
                cur.execute("""
                    SELECT encrypted_key
                    FROM kg_api.system_api_keys
                    WHERE provider = %s
                """, (provider,))

                row = cur.fetchone()
                if not row:
                    raise ValueError(f"No {provider} API key configured for this shard")

                encrypted = bytes(row[0])

                # Decrypt the key
                try:
                    plaintext = self.cipher.decrypt(encrypted).decode()
                    return plaintext
                except InvalidToken:
                    raise ValueError(
                        f"Failed to decrypt {provider} API key. "
                        "Master encryption key may have changed."
                    )

        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Failed to retrieve API key for {provider}: {e}")
            raise ValueError(f"Failed to retrieve API key: {e}")

    def delete_key(self, provider: str) -> bool:
        """
        Remove system API key.

        Args:
            provider: Provider name ('openai' or 'anthropic')

        Returns:
            True if key was deleted, False if not found
        """
        try:
            with self.db.cursor() as cur:
                cur.execute("""
                    DELETE FROM kg_api.system_api_keys
                    WHERE provider = %s
                """, (provider,))
                self.db.commit()

                deleted = cur.rowcount > 0
                if deleted:
                    logger.info(f"Deleted API key for provider: {provider}")
                return deleted

        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to delete API key for {provider}: {e}")
            raise ValueError(f"Failed to delete API key: {e}")

    def list_providers(self, include_masked_keys: bool = False) -> List[Dict[str, str]]:
        """
        List configured providers with validation status (ADR-041).

        Args:
            include_masked_keys: If True, decrypt and include masked keys in response

        Returns:
            List of provider info dicts with validation status:
            [
                {
                    'provider': 'openai',
                    'updated_at': '...',
                    'validation_status': 'valid',
                    'last_validated_at': '...',
                    'validation_error': None,
                    'masked_key': 'sk-proj-...abc123'  # Only if include_masked_keys=True
                }
            ]
        """
        try:
            with self.db.cursor() as cur:
                # Check if validation columns exist (migration 005 may not have run yet)
                cur.execute("""
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_schema = 'kg_api'
                      AND table_name = 'system_api_keys'
                      AND column_name = 'validation_status'
                """)
                has_validation = cur.fetchone() is not None

                if has_validation:
                    # Query with validation fields
                    cur.execute("""
                        SELECT provider, updated_at, encrypted_key,
                               validation_status, last_validated_at, validation_error
                        FROM kg_api.system_api_keys
                        ORDER BY provider
                    """)

                    results = []
                    for row in cur.fetchall():
                        provider_info = {
                            'provider': row[0],
                            'updated_at': row[1].isoformat() if row[1] else None,
                            'validation_status': row[3] or 'untested',
                            'last_validated_at': row[4].isoformat() if row[4] else None,
                            'validation_error': row[5]
                        }

                        # Optionally decrypt and mask the key
                        if include_masked_keys:
                            try:
                                encrypted = bytes(row[2])
                                plaintext = self.cipher.decrypt(encrypted).decode()
                                provider_info['masked_key'] = mask_api_key(plaintext)
                            except Exception as e:
                                logger.warning(f"Failed to decrypt key for masking: {e}")
                                provider_info['masked_key'] = '***'

                        results.append(provider_info)

                    return results
                else:
                    # Fallback for when migration 005 hasn't run yet
                    cur.execute("""
                        SELECT provider, updated_at, encrypted_key
                        FROM kg_api.system_api_keys
                        ORDER BY provider
                    """)

                    results = []
                    for row in cur.fetchall():
                        provider_info = {
                            'provider': row[0],
                            'updated_at': row[1].isoformat() if row[1] else None,
                            'validation_status': 'unknown',  # Migration not applied
                            'last_validated_at': None,
                            'validation_error': None
                        }

                        # Optionally decrypt and mask the key
                        if include_masked_keys:
                            try:
                                encrypted = bytes(row[2])
                                plaintext = self.cipher.decrypt(encrypted).decode()
                                provider_info['masked_key'] = mask_api_key(plaintext)
                            except Exception as e:
                                logger.warning(f"Failed to decrypt key for masking: {e}")
                                provider_info['masked_key'] = '***'

                        results.append(provider_info)

                    return results

        except Exception as e:
            logger.error(f"Failed to list providers: {e}")
            return []

    def has_key(self, provider: str) -> bool:
        """
        Check if API key exists for provider.

        Args:
            provider: Provider name ('openai' or 'anthropic')

        Returns:
            True if key exists, False otherwise
        """
        try:
            with self.db.cursor() as cur:
                cur.execute("""
                    SELECT 1
                    FROM kg_api.system_api_keys
                    WHERE provider = %s
                """, (provider,))

                return cur.fetchone() is not None

        except Exception as e:
            logger.error(f"Failed to check key existence for {provider}: {e}")
            return False

    def update_validation_status(
        self,
        provider: str,
        status: str,
        error_message: Optional[str] = None
    ) -> bool:
        """
        Update validation status for an API key (ADR-041).

        Args:
            provider: Provider name ('openai' or 'anthropic')
            status: Validation status ('valid', 'invalid', 'untested')
            error_message: Optional error message if validation failed

        Returns:
            True if updated successfully, False otherwise
        """
        try:
            with self.db.cursor() as cur:
                # Check if validation columns exist (migration 005 may not have run yet)
                cur.execute("""
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_schema = 'kg_api'
                      AND table_name = 'system_api_keys'
                      AND column_name = 'validation_status'
                """)
                has_validation = cur.fetchone() is not None

                if not has_validation:
                    logger.debug(
                        f"Validation columns not available (migration 005 pending). "
                        f"Skipping validation status update for {provider}."
                    )
                    return False

                # Update validation status
                cur.execute("""
                    UPDATE kg_api.system_api_keys
                    SET validation_status = %s,
                        last_validated_at = NOW(),
                        validation_error = %s
                    WHERE provider = %s
                """, (status, error_message, provider))

                self.db.commit()
                updated = cur.rowcount > 0

                if updated:
                    logger.info(
                        f"Updated validation status for {provider}: {status}" +
                        (f" - {error_message}" if error_message else "")
                    )

                return updated

        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to update validation status for {provider}: {e}")
            return False


# Helper function for convenience
def get_system_api_key(
    db_connection: PgConnection,
    provider: str,
    service_token: Optional[str] = None
) -> Optional[str]:
    """
    Get decrypted system API key with service token authorization (ADR-031).

    This implements defense-in-depth by requiring authorized workers to present
    a service token before accessing encrypted keys. The token is stored in
    Docker/Podman secrets and validated on each request.

    Args:
        db_connection: PostgreSQL connection
        provider: Provider name ('openai' or 'anthropic')
        service_token: Internal service authorization token (required)

    Returns:
        Decrypted API key, or None if not found or error

    Raises:
        SecurityError: If service_token is invalid or missing

    Security:
        - Token validation prevents unauthorized code from accessing keys
        - Failed attempts logged as security events
        - Multiple isolation boundaries required for attack (see ADR-031)
    """
    # Import here to avoid circular dependency
    from .secrets import get_internal_key_service_secret
    import inspect

    # Validate service token
    if service_token is None:
        caller_frame = inspect.stack()[1]
        logger.error(
            f"Key access denied: No service token provided for {provider}",
            extra={
                "caller_function": caller_frame.function,
                "caller_file": caller_frame.filename,
                "caller_line": caller_frame.lineno
            }
        )
        raise ValueError("Service token required for key access (ADR-031)")

    expected_token = get_internal_key_service_secret()
    if service_token != expected_token:
        caller_frame = inspect.stack()[1]
        logger.warning(
            f"SECURITY: Invalid service token for {provider} key access",
            extra={
                "caller_function": caller_frame.function,
                "caller_file": caller_frame.filename,
                "caller_line": caller_frame.lineno,
                "provider": provider
            }
        )
        raise ValueError("Invalid service token")

    # Token valid - continue with key retrieval
    try:
        store = EncryptedKeyStore(db_connection)
        key = store.get_key(provider)
        logger.debug(f"Authorized key access for {provider}")
        return key
    except ValueError as e:
        logger.debug(f"Could not get API key for {provider}: {e}")
        return None
    except Exception as e:
        logger.error(f"Error getting API key for {provider}: {e}")
        return None
