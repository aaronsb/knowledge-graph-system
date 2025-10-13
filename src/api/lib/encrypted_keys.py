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


class EncryptedKeyStore:
    """Manage system-wide API keys with encryption at rest"""

    def __init__(self, db_connection: PgConnection):
        """
        Initialize encrypted key store.

        Args:
            db_connection: PostgreSQL database connection

        Raises:
            ValueError: If encryption key not configured
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

        # Ensure table exists
        self._ensure_table()

    def _ensure_table(self) -> None:
        """Create system_api_keys table if it doesn't exist"""
        try:
            with self.db.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS system_api_keys (
                        provider VARCHAR(50) PRIMARY KEY,
                        encrypted_key BYTEA NOT NULL,
                        updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                    );

                    CREATE INDEX IF NOT EXISTS idx_system_api_keys_updated
                    ON system_api_keys(updated_at);
                """)
                self.db.commit()
                logger.debug("system_api_keys table ready")
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to create system_api_keys table: {e}")
            raise

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
                    INSERT INTO system_api_keys (provider, encrypted_key)
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
                    FROM system_api_keys
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
                    DELETE FROM system_api_keys
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

    def list_providers(self) -> List[Dict[str, str]]:
        """
        List configured providers.

        Returns:
            List of provider info dicts: [{'provider': 'openai', 'updated_at': '...'}]
        """
        try:
            with self.db.cursor() as cur:
                cur.execute("""
                    SELECT provider, updated_at
                    FROM system_api_keys
                    ORDER BY provider
                """)

                return [
                    {
                        'provider': row[0],
                        'updated_at': row[1].isoformat() if row[1] else None
                    }
                    for row in cur.fetchall()
                ]

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
                    FROM system_api_keys
                    WHERE provider = %s
                """, (provider,))

                return cur.fetchone() is not None

        except Exception as e:
            logger.error(f"Failed to check key existence for {provider}: {e}")
            return False


# Helper function for convenience
def get_system_api_key(db_connection: PgConnection, provider: str) -> Optional[str]:
    """
    Convenience function to get decrypted system API key.

    Args:
        db_connection: PostgreSQL connection
        provider: Provider name ('openai' or 'anthropic')

    Returns:
        Decrypted API key, or None if not found or error
    """
    try:
        store = EncryptedKeyStore(db_connection)
        return store.get_key(provider)
    except ValueError as e:
        logger.debug(f"Could not get API key for {provider}: {e}")
        return None
    except Exception as e:
        logger.error(f"Error getting API key for {provider}: {e}")
        return None
