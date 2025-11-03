"""
OAuth 2.0 Utilities (ADR-054)

Helper functions for OAuth token generation, validation, and PKCE.
"""

import hashlib
import secrets
import string
from datetime import datetime, timedelta, timezone
from typing import Tuple


# =============================================================================
# Token Generation
# =============================================================================

def generate_oauth_token(length: int = 43) -> str:
    """
    Generate a cryptographically secure random token.

    Args:
        length: Token length in characters (default: 43 for URL-safe tokens)

    Returns:
        URL-safe random token string

    Example:
        >>> token = generate_oauth_token()
        >>> len(token)
        43
    """
    return secrets.token_urlsafe(length)


def generate_authorization_code() -> str:
    """
    Generate an authorization code for OAuth authorization code flow.

    Returns:
        Random 43-character URL-safe string
    """
    return generate_oauth_token(43)


def generate_device_code() -> str:
    """
    Generate a device code for OAuth device authorization flow.

    Returns:
        Random 43-character URL-safe string
    """
    return generate_oauth_token(43)


def generate_user_code(length: int = 8) -> str:
    """
    Generate a human-friendly user code for device authorization.

    Format: ABCD-1234 (uppercase letters and digits with hyphen)

    Args:
        length: Total character length (default: 8, produces XXXX-XXXX format)

    Returns:
        Human-friendly code string

    Example:
        >>> code = generate_user_code()
        >>> len(code)
        9  # 8 chars + 1 hyphen
        >>> '-' in code
        True
    """
    # Use uppercase letters and digits (avoid ambiguous characters like 0, O, 1, I, l)
    alphabet = string.ascii_uppercase.replace('O', '').replace('I', '') + string.digits.replace('0', '').replace('1', '')

    # Generate random characters
    half = length // 2
    code = ''.join(secrets.choice(alphabet) for _ in range(length))

    # Insert hyphen in the middle
    return f"{code[:half]}-{code[half:]}"


def generate_access_token() -> str:
    """
    Generate an OAuth access token.

    Returns:
        Random 43-character URL-safe string
    """
    return generate_oauth_token(43)


def generate_refresh_token() -> str:
    """
    Generate an OAuth refresh token.

    Returns:
        Random 43-character URL-safe string
    """
    return generate_oauth_token(43)


def generate_client_secret() -> str:
    """
    Generate a client secret for confidential OAuth clients.

    Returns:
        Random 64-character URL-safe string
    """
    return generate_oauth_token(64)


# =============================================================================
# Token Hashing
# =============================================================================

def hash_token(token: str) -> str:
    """
    Hash a token for secure storage using SHA-256.

    Tokens are hashed before database storage to prevent exposure if database is compromised.

    Args:
        token: Plain token string

    Returns:
        SHA-256 hex digest (64 characters)

    Example:
        >>> token_hash = hash_token("my-secret-token")
        >>> len(token_hash)
        64
    """
    return hashlib.sha256(token.encode()).hexdigest()


# =============================================================================
# PKCE (Proof Key for Code Exchange) Functions
# =============================================================================

def validate_pkce_challenge(code_verifier: str, code_challenge: str, method: str) -> bool:
    """
    Validate PKCE code challenge against code verifier.

    Args:
        code_verifier: Plain code verifier from client
        code_challenge: Code challenge from authorization request
        method: Challenge method ('S256' or 'plain')

    Returns:
        True if challenge matches verifier, False otherwise

    PKCE Flow:
        1. Client generates code_verifier (random string)
        2. Client computes code_challenge = hash(code_verifier) or plain
        3. Client sends code_challenge to authorization endpoint
        4. Server stores code_challenge
        5. Client sends code_verifier to token endpoint
        6. Server validates: hash(code_verifier) == stored code_challenge

    Example:
        >>> verifier = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"
        >>> challenge = "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM"
        >>> validate_pkce_challenge(verifier, challenge, "S256")
        True
    """
    if method == "plain":
        # Plain method: verifier must equal challenge
        return code_verifier == code_challenge

    elif method == "S256":
        # S256 method: SHA256(verifier) base64url-encoded must equal challenge
        import base64

        # Compute SHA256 hash of verifier
        digest = hashlib.sha256(code_verifier.encode('ascii')).digest()

        # Base64 URL-safe encode (no padding)
        computed_challenge = base64.urlsafe_b64encode(digest).rstrip(b'=').decode('ascii')

        return computed_challenge == code_challenge

    else:
        # Invalid method
        return False


# =============================================================================
# Token Expiration
# =============================================================================

def get_authorization_code_expiry() -> datetime:
    """
    Get expiration datetime for authorization codes (10 minutes).

    Returns:
        Datetime 10 minutes from now
    """
    return datetime.now(timezone.utc) + timedelta(minutes=10)


def get_device_code_expiry() -> datetime:
    """
    Get expiration datetime for device codes (10 minutes).

    Returns:
        Datetime 10 minutes from now
    """
    return datetime.now(timezone.utc) + timedelta(minutes=10)


def get_access_token_expiry() -> datetime:
    """
    Get expiration datetime for access tokens (1 hour).

    Returns:
        Datetime 1 hour from now
    """
    return datetime.now(timezone.utc) + timedelta(hours=1)


def get_refresh_token_expiry(client_type: str) -> datetime:
    """
    Get expiration datetime for refresh tokens (client-type dependent).

    Args:
        client_type: 'public' (7 days) or 'confidential' (30 days)

    Returns:
        Datetime 7 or 30 days from now
    """
    if client_type == "confidential":
        # Confidential clients get 30-day refresh tokens
        return datetime.now(timezone.utc) + timedelta(days=30)
    else:
        # Public clients get 7-day refresh tokens
        return datetime.now(timezone.utc) + timedelta(days=7)


def is_token_expired(expires_at: datetime) -> bool:
    """
    Check if a token has expired.

    Args:
        expires_at: Token expiration datetime

    Returns:
        True if expired, False otherwise
    """
    return datetime.now(timezone.utc) > expires_at


# =============================================================================
# Scope Validation
# =============================================================================

def validate_scopes(requested_scopes: list[str], allowed_scopes: list[str]) -> Tuple[bool, list[str]]:
    """
    Validate that requested scopes are allowed for the client.

    Args:
        requested_scopes: Scopes requested by client
        allowed_scopes: Scopes allowed for this client

    Returns:
        Tuple of (is_valid, granted_scopes)
        - is_valid: True if all requested scopes are allowed
        - granted_scopes: List of granted scopes (intersection of requested and allowed)

    Wildcard support:
        - '*' matches everything
        - 'read:*' matches all read scopes
        - 'write:*' matches all write scopes

    Example:
        >>> validate_scopes(["read:concepts"], ["read:*", "write:*"])
        (True, ["read:concepts"])
        >>> validate_scopes(["admin:users"], ["read:*"])
        (False, [])
    """
    # If no scopes requested, grant default read scopes
    if not requested_scopes:
        requested_scopes = ["read:*"]

    # If client has wildcard, grant all requested scopes
    if "*" in allowed_scopes or "read:*" in allowed_scopes and "write:*" in allowed_scopes:
        return True, requested_scopes

    granted = []
    for scope in requested_scopes:
        # Check exact match
        if scope in allowed_scopes:
            granted.append(scope)
            continue

        # Check wildcard match (e.g., "read:*" allows "read:concepts")
        scope_prefix = scope.split(':')[0] if ':' in scope else None
        if scope_prefix:
            wildcard = f"{scope_prefix}:*"
            if wildcard in allowed_scopes:
                granted.append(scope)
                continue

    # Valid if all requested scopes were granted
    is_valid = len(granted) == len(requested_scopes)
    return is_valid, granted


def parse_scope_string(scope: str) -> list[str]:
    """
    Parse space-separated scope string into list.

    Args:
        scope: Space-separated scope string (e.g., "read:concepts write:concepts")

    Returns:
        List of individual scopes

    Example:
        >>> parse_scope_string("read:concepts write:concepts")
        ['read:concepts', 'write:concepts']
        >>> parse_scope_string("")
        []
    """
    if not scope:
        return []
    return scope.strip().split()


def format_scope_list(scopes: list[str]) -> str:
    """
    Format scope list as space-separated string.

    Args:
        scopes: List of scopes

    Returns:
        Space-separated scope string

    Example:
        >>> format_scope_list(["read:concepts", "write:concepts"])
        'read:concepts write:concepts'
    """
    return " ".join(scopes)
