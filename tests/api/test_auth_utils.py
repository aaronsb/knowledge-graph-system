"""
Authentication Utility Functions Tests (ADR-054, ADR-027)

Unit tests for authentication utilities in src/api/lib/auth.py.

Tests pure functions with no database or mocking required:
- Password hashing and verification
- Password strength validation
- JWT token creation and decoding
- API key generation and validation
- OAuth configuration validation
"""

import pytest
import re
from datetime import timedelta

from src.api.lib.auth import (
    verify_password,
    get_password_hash,
    create_access_token,
    decode_access_token,
    extract_username_from_token,
    validate_password_strength,
    generate_api_key,
    hash_api_key,
    verify_api_key,
    validate_oauth_configuration,
)


# =============================================================================
# Password Hashing Tests
# =============================================================================

@pytest.mark.unit
@pytest.mark.security
def test_get_password_hash():
    """Test password hashing produces bcrypt hash"""
    password = "SecurePass123!"
    password_hash = get_password_hash(password)

    assert isinstance(password_hash, str)
    # Bcrypt hash format: $2b$12$...
    assert password_hash.startswith("$2b$")
    # Bcrypt hashes are 60 characters
    assert len(password_hash) == 60


@pytest.mark.unit
@pytest.mark.security
def test_verify_password_success():
    """Test password verification succeeds with correct password"""
    password = "MyPassword123!"
    password_hash = get_password_hash(password)

    result = verify_password(password, password_hash)

    assert result is True


@pytest.mark.unit
@pytest.mark.security
def test_verify_password_failure():
    """Test password verification fails with wrong password"""
    password = "MyPassword123!"
    wrong_password = "WrongPassword456!"
    password_hash = get_password_hash(password)

    result = verify_password(wrong_password, password_hash)

    assert result is False


@pytest.mark.unit
@pytest.mark.security
def test_password_hash_uniqueness():
    """Test same password produces different hashes (salt)"""
    password = "TestPassword123!"

    hash1 = get_password_hash(password)
    hash2 = get_password_hash(password)

    # Hashes should be different due to random salt
    assert hash1 != hash2
    # But both should verify correctly
    assert verify_password(password, hash1)
    assert verify_password(password, hash2)


# =============================================================================
# Password Strength Validation Tests
# =============================================================================

@pytest.mark.unit
@pytest.mark.security
def test_validate_password_strength_valid():
    """Test password strength validation passes for strong password"""
    is_valid, error = validate_password_strength("SecurePass123!")

    assert is_valid is True
    assert error is None


@pytest.mark.unit
@pytest.mark.security
def test_validate_password_strength_too_short():
    """Test password strength validation fails for short password"""
    is_valid, error = validate_password_strength("Short1!")

    assert is_valid is False
    assert "8 characters" in error


@pytest.mark.unit
@pytest.mark.security
def test_validate_password_strength_no_uppercase():
    """Test password strength validation fails without uppercase"""
    is_valid, error = validate_password_strength("password123!")

    assert is_valid is False
    assert "uppercase" in error.lower()


@pytest.mark.unit
@pytest.mark.security
def test_validate_password_strength_no_lowercase():
    """Test password strength validation fails without lowercase"""
    is_valid, error = validate_password_strength("PASSWORD123!")

    assert is_valid is False
    assert "lowercase" in error.lower()


@pytest.mark.unit
@pytest.mark.security
def test_validate_password_strength_no_digit():
    """Test password strength validation fails without digit"""
    is_valid, error = validate_password_strength("PasswordABC!")

    assert is_valid is False
    assert "digit" in error.lower()


@pytest.mark.unit
@pytest.mark.security
def test_validate_password_strength_no_special():
    """Test password strength validation fails without special character"""
    is_valid, error = validate_password_strength("Password123")

    assert is_valid is False
    assert "special" in error.lower()


# =============================================================================
# JWT Token Tests
# =============================================================================

@pytest.mark.unit
@pytest.mark.security
def test_create_access_token():
    """Test JWT access token creation"""
    data = {"sub": "testuser", "role": "contributor"}

    token = create_access_token(data)

    assert isinstance(token, str)
    # JWT tokens have 3 parts separated by dots
    assert token.count('.') == 2


@pytest.mark.unit
@pytest.mark.security
def test_decode_access_token():
    """Test JWT token decoding"""
    data = {"sub": "alice", "role": "curator"}
    token = create_access_token(data)

    payload = decode_access_token(token)

    assert payload is not None
    assert payload["sub"] == "alice"
    assert payload["role"] == "curator"
    assert "exp" in payload  # Expiration should be added


@pytest.mark.unit
@pytest.mark.security
def test_decode_access_token_expired():
    """Test JWT token decoding fails for expired token"""
    data = {"sub": "testuser", "role": "contributor"}
    # Create token that expires immediately
    token = create_access_token(data, expires_delta=timedelta(seconds=-1))

    payload = decode_access_token(token)

    # Should return None for expired token
    assert payload is None


@pytest.mark.unit
@pytest.mark.security
def test_decode_access_token_invalid():
    """Test JWT token decoding fails for invalid token"""
    invalid_token = "invalid.jwt.token"

    payload = decode_access_token(invalid_token)

    assert payload is None


@pytest.mark.unit
@pytest.mark.security
def test_extract_username_from_token():
    """Test username extraction from JWT token"""
    data = {"sub": "bob", "role": "admin"}
    token = create_access_token(data)

    username = extract_username_from_token(token)

    assert username == "bob"


@pytest.mark.unit
@pytest.mark.security
def test_extract_username_from_invalid_token():
    """Test username extraction returns None for invalid token"""
    invalid_token = "invalid.jwt.token"

    username = extract_username_from_token(invalid_token)

    assert username is None


@pytest.mark.unit
@pytest.mark.security
def test_token_expiration_custom():
    """Test JWT token with custom expiration"""
    data = {"sub": "testuser"}
    # Create token that expires in 5 minutes
    token = create_access_token(data, expires_delta=timedelta(minutes=5))

    payload = decode_access_token(token)

    assert payload is not None
    assert "exp" in payload


# =============================================================================
# API Key Tests
# =============================================================================

@pytest.mark.unit
@pytest.mark.security
def test_generate_api_key_format():
    """Test API key generation has correct format"""
    api_key = generate_api_key()

    assert isinstance(api_key, str)
    # Should start with kg_sk_ prefix
    assert api_key.startswith("kg_sk_")
    # Should be hex characters after prefix
    hex_part = api_key.replace("kg_sk_", "")
    assert re.match(r'^[0-9a-f]+$', hex_part)
    # Should be 66 characters total (6 prefix + 64 hex)
    assert len(api_key) == 70  # kg_sk_ + 64 hex chars


@pytest.mark.unit
@pytest.mark.security
def test_generate_api_key_uniqueness():
    """Test generated API keys are unique"""
    keys = {generate_api_key() for _ in range(100)}

    # All 100 keys should be unique
    assert len(keys) == 100


@pytest.mark.unit
@pytest.mark.security
def test_hash_api_key():
    """Test API key hashing"""
    api_key = generate_api_key()

    key_hash = hash_api_key(api_key)

    assert isinstance(key_hash, str)
    # Should be bcrypt hash
    assert key_hash.startswith("$2b$")
    assert len(key_hash) == 60


@pytest.mark.unit
@pytest.mark.security
def test_verify_api_key_success():
    """Test API key verification succeeds with correct key"""
    api_key = generate_api_key()
    key_hash = hash_api_key(api_key)

    result = verify_api_key(api_key, key_hash)

    assert result is True


@pytest.mark.unit
@pytest.mark.security
def test_verify_api_key_failure():
    """Test API key verification fails with wrong key"""
    api_key = generate_api_key()
    wrong_key = generate_api_key()  # Different key
    key_hash = hash_api_key(api_key)

    result = verify_api_key(wrong_key, key_hash)

    assert result is False


# =============================================================================
# OAuth Configuration Validation Tests
# =============================================================================

@pytest.mark.unit
@pytest.mark.security
def test_validate_oauth_configuration():
    """Test OAuth configuration validation function works"""
    # Just verify the function runs and returns expected structure
    # Actual configuration warnings depend on environment settings
    is_valid, warnings = validate_oauth_configuration()

    # Should return tuple of (bool, list)
    assert isinstance(is_valid, bool)
    assert isinstance(warnings, list)
    # All warnings should be strings
    assert all(isinstance(w, str) for w in warnings)


@pytest.mark.unit
@pytest.mark.security
def test_validate_oauth_configuration_secure(monkeypatch):
    """Test OAuth configuration validation passes for secure config"""
    import src.api.lib.auth as auth_module

    # Set secure configuration
    secure_key = "a" * 64  # Long random key
    monkeypatch.setattr(auth_module, "SECRET_KEY", secure_key)
    monkeypatch.setattr(auth_module, "ACCESS_TOKEN_EXPIRE_MINUTES", 60)

    is_valid, warnings = auth_module.validate_oauth_configuration()

    assert is_valid is True
    assert len(warnings) == 0


@pytest.mark.unit
@pytest.mark.security
def test_validate_oauth_configuration_short_key(monkeypatch):
    """Test OAuth configuration validation warns about short key"""
    import src.api.lib.auth as auth_module

    # Set short key (less than 32 chars)
    monkeypatch.setattr(auth_module, "SECRET_KEY", "short_key_12345")
    monkeypatch.setattr(auth_module, "ACCESS_TOKEN_EXPIRE_MINUTES", 60)

    is_valid, warnings = auth_module.validate_oauth_configuration()

    assert is_valid is False
    assert any("too short" in w for w in warnings)


@pytest.mark.unit
@pytest.mark.security
def test_validate_oauth_configuration_long_expiration(monkeypatch):
    """Test OAuth configuration validation warns about long expiration"""
    import src.api.lib.auth as auth_module

    # Set secure key but very long expiration
    secure_key = "a" * 64
    monkeypatch.setattr(auth_module, "SECRET_KEY", secure_key)
    monkeypatch.setattr(auth_module, "ACCESS_TOKEN_EXPIRE_MINUTES", 2880)  # 2 days

    is_valid, warnings = auth_module.validate_oauth_configuration()

    assert is_valid is False
    assert any("too long" in w for w in warnings)
