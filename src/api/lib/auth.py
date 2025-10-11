"""
Authentication Utilities (ADR-027)

Core utilities for password hashing and JWT token management.

Dependencies:
- passlib[bcrypt] - Password hashing
- python-jose[cryptography] - JWT token generation/validation
"""

import os
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

from passlib.context import CryptContext
from jose import JWTError, jwt


# =============================================================================
# Configuration
# =============================================================================

# JWT Configuration
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "CHANGE_THIS_IN_PRODUCTION_GENERATE_WITH_openssl_rand_hex_32")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))

# Password Hashing Configuration
pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__rounds=12  # Cost factor: 2^12 iterations (~300ms on modern CPU)
)


# =============================================================================
# Password Hashing Functions
# =============================================================================

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a plain text password against a bcrypt hash.

    Args:
        plain_password: User-provided password
        hashed_password: Bcrypt hash from database (e.g., $2b$12$...)

    Returns:
        True if password matches, False otherwise

    Example:
        >>> hashed = "$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5GyYzpLHJ4tNi"
        >>> verify_password("admin", hashed)
        True
    """
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """
    Hash a plain text password using bcrypt.

    Args:
        password: Plain text password to hash

    Returns:
        Bcrypt hash string (e.g., $2b$12$...)

    Example:
        >>> hash = get_password_hash("SecurePass123!")
        >>> hash.startswith("$2b$12$")
        True
        >>> len(hash)
        60
    """
    return pwd_context.hash(password)


# =============================================================================
# JWT Token Functions
# =============================================================================

def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a JWT access token.

    Args:
        data: Payload data to encode (typically {"sub": username, "role": role})
        expires_delta: Optional custom expiration time (default: ACCESS_TOKEN_EXPIRE_MINUTES)

    Returns:
        Encoded JWT token string

    Token Payload Structure:
        {
            "sub": "username",      # Subject (username)
            "role": "admin",        # User role for permission checks
            "exp": 1696876543       # Expiration timestamp (Unix epoch)
        }

    Example:
        >>> token = create_access_token({"sub": "alice", "role": "curator"})
        >>> len(token) > 100  # JWT tokens are typically 200-500 bytes
        True
    """
    to_encode = data.copy()

    # Set expiration time
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire})

    # Encode JWT token
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Decode and validate a JWT access token.

    Args:
        token: Encoded JWT token string

    Returns:
        Decoded payload dict if valid, None if invalid or expired

    Validation Checks:
        - Signature is valid (using SECRET_KEY)
        - Token has not expired
        - Token structure is correct

    Example:
        >>> token = create_access_token({"sub": "alice", "role": "curator"})
        >>> payload = decode_access_token(token)
        >>> payload["sub"]
        'alice'
        >>> payload["role"]
        'curator'
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        # Invalid signature, expired token, or malformed token
        return None


def extract_username_from_token(token: str) -> Optional[str]:
    """
    Extract username (subject) from JWT token.

    Args:
        token: Encoded JWT token string

    Returns:
        Username if token is valid, None otherwise

    Example:
        >>> token = create_access_token({"sub": "alice", "role": "curator"})
        >>> extract_username_from_token(token)
        'alice'
    """
    payload = decode_access_token(token)
    if payload is None:
        return None

    username: str = payload.get("sub")
    return username


# =============================================================================
# Password Validation
# =============================================================================

def validate_password_strength(password: str) -> tuple[bool, Optional[str]]:
    """
    Validate password meets minimum security requirements.

    Requirements (per ADR-027):
    - Minimum 8 characters
    - At least one uppercase letter
    - At least one lowercase letter
    - At least one digit
    - At least one special character

    Args:
        password: Plain text password to validate

    Returns:
        Tuple of (is_valid, error_message)
        - (True, None) if password is valid
        - (False, "error message") if password is invalid

    Example:
        >>> validate_password_strength("weak")
        (False, 'Password must be at least 8 characters long')
        >>> validate_password_strength("SecurePass123!")
        (True, None)
    """
    if len(password) < 8:
        return False, "Password must be at least 8 characters long"

    if not any(c.isupper() for c in password):
        return False, "Password must contain at least one uppercase letter"

    if not any(c.islower() for c in password):
        return False, "Password must contain at least one lowercase letter"

    if not any(c.isdigit() for c in password):
        return False, "Password must contain at least one digit"

    # Check for special characters
    special_chars = "!@#$%^&*()_+-=[]{}|;:,.<>?"
    if not any(c in special_chars for c in password):
        return False, "Password must contain at least one special character"

    return True, None


# =============================================================================
# API Key Utilities
# =============================================================================

def generate_api_key() -> str:
    """
    Generate a random API key.

    Format: kg_sk_<32_random_bytes_hex>
    Example: kg_sk_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1v2w3x4y5z6

    Returns:
        API key string (66 characters total)

    Security Notes:
        - Uses os.urandom() for cryptographically secure random bytes
        - Key is hashed before storage (never store plaintext)
        - Prefix 'kg_sk_' identifies this as a knowledge graph secret key
    """
    import secrets
    random_bytes = secrets.token_hex(32)  # 32 bytes = 64 hex characters
    return f"kg_sk_{random_bytes}"


def hash_api_key(api_key: str) -> str:
    """
    Hash an API key for database storage.

    Args:
        api_key: Plain text API key (e.g., kg_sk_a1b2c3d4...)

    Returns:
        Bcrypt hash of the API key

    Note:
        API keys are hashed the same way as passwords for consistency.
        This allows us to use the same verification function.
    """
    return get_password_hash(api_key)


def verify_api_key(plain_key: str, key_hash: str) -> bool:
    """
    Verify a plain text API key against a hash.

    Args:
        plain_key: User-provided API key
        key_hash: Bcrypt hash from database

    Returns:
        True if key matches, False otherwise
    """
    return verify_password(plain_key, key_hash)


# =============================================================================
# Configuration Validation
# =============================================================================

def validate_jwt_configuration() -> tuple[bool, list[str]]:
    """
    Validate JWT configuration is production-ready.

    Checks:
    - SECRET_KEY is not the default value
    - SECRET_KEY is sufficiently long (>= 32 characters)
    - ACCESS_TOKEN_EXPIRE_MINUTES is reasonable (between 5 and 1440 minutes)

    Returns:
        Tuple of (is_valid, list_of_warnings)

    Example:
        >>> validate_jwt_configuration()
        (False, ['JWT_SECRET_KEY is using default value - INSECURE!'])
    """
    warnings = []

    # Check SECRET_KEY is not default
    if "CHANGE_THIS" in SECRET_KEY:
        warnings.append("JWT_SECRET_KEY is using default value - INSECURE!")

    # Check SECRET_KEY length
    if len(SECRET_KEY) < 32:
        warnings.append(f"JWT_SECRET_KEY is too short ({len(SECRET_KEY)} chars, minimum 32)")

    # Check token expiration is reasonable
    if ACCESS_TOKEN_EXPIRE_MINUTES < 5:
        warnings.append(f"ACCESS_TOKEN_EXPIRE_MINUTES is too short ({ACCESS_TOKEN_EXPIRE_MINUTES} minutes)")

    if ACCESS_TOKEN_EXPIRE_MINUTES > 1440:  # 24 hours
        warnings.append(f"ACCESS_TOKEN_EXPIRE_MINUTES is too long ({ACCESS_TOKEN_EXPIRE_MINUTES} minutes)")

    is_valid = len(warnings) == 0
    return is_valid, warnings


# =============================================================================
# Module Initialization
# =============================================================================

# Validate configuration on module import (development safety check)
if __name__ != "__main__":
    is_valid, warnings = validate_jwt_configuration()
    if not is_valid:
        import logging
        logger = logging.getLogger(__name__)
        for warning in warnings:
            logger.warning(f"⚠️  Auth Configuration: {warning}")
