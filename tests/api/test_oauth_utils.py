"""
OAuth Utility Functions Tests (ADR-054)

Unit tests for OAuth 2.0 utility functions in api/app/lib/oauth_utils.py.

Tests pure functions with no database or mocking required:
- Token generation (various types)
- Token hashing
- PKCE validation
- Token expiration logic
- Scope validation and parsing
"""

import pytest
import re
from datetime import datetime, timedelta, timezone

from api.app.lib.oauth_utils import (
    generate_oauth_token,
    generate_authorization_code,
    generate_device_code,
    generate_user_code,
    generate_access_token,
    generate_refresh_token,
    generate_client_secret,
    hash_token,
    validate_pkce_challenge,
    get_authorization_code_expiry,
    get_device_code_expiry,
    get_access_token_expiry,
    get_refresh_token_expiry,
    is_token_expired,
    validate_scopes,
    parse_scope_string,
    format_scope_list,
)


# =============================================================================
# Token Generation Tests
# =============================================================================

@pytest.mark.unit
@pytest.mark.security
def test_generate_oauth_token_default_length():
    """Test OAuth token generation with default length"""
    token = generate_oauth_token()

    assert isinstance(token, str)
    assert len(token) > 0
    # URL-safe tokens should contain only alphanumeric, -, and _
    assert re.match(r'^[A-Za-z0-9_-]+$', token)


@pytest.mark.unit
@pytest.mark.security
def test_generate_oauth_token_custom_length():
    """Test OAuth token generation with custom length"""
    token = generate_oauth_token(length=32)

    assert isinstance(token, str)
    assert len(token) > 0


@pytest.mark.unit
@pytest.mark.security
def test_generate_oauth_token_uniqueness():
    """Test that generated tokens are unique"""
    tokens = {generate_oauth_token() for _ in range(100)}

    # All 100 tokens should be unique
    assert len(tokens) == 100


@pytest.mark.unit
@pytest.mark.security
def test_generate_authorization_code():
    """Test authorization code generation"""
    code = generate_authorization_code()

    assert isinstance(code, str)
    assert len(code) > 0
    assert re.match(r'^[A-Za-z0-9_-]+$', code)


@pytest.mark.unit
@pytest.mark.security
def test_generate_device_code():
    """Test device code generation"""
    code = generate_device_code()

    assert isinstance(code, str)
    assert len(code) > 0
    assert re.match(r'^[A-Za-z0-9_-]+$', code)


@pytest.mark.unit
@pytest.mark.security
def test_generate_user_code_format():
    """Test user code generation has correct format (XXXX-XXXX)"""
    code = generate_user_code()

    assert isinstance(code, str)
    # Should have hyphen
    assert '-' in code
    # Should be 9 characters total (4 + hyphen + 4)
    assert len(code) == 9
    # Should match pattern
    assert re.match(r'^[A-Z2-9]{4}-[A-Z2-9]{4}$', code)


@pytest.mark.unit
@pytest.mark.security
def test_generate_user_code_no_ambiguous_chars():
    """Test user code does not contain ambiguous characters (0, O, 1, I)"""
    # Generate many codes and check none contain ambiguous chars
    for _ in range(100):
        code = generate_user_code()
        # Should not contain 0, O, 1, I, l
        assert '0' not in code
        assert 'O' not in code
        assert '1' not in code
        assert 'I' not in code
        assert 'l' not in code


@pytest.mark.unit
@pytest.mark.security
def test_generate_access_token():
    """Test access token generation"""
    token = generate_access_token()

    assert isinstance(token, str)
    assert len(token) > 0
    assert re.match(r'^[A-Za-z0-9_-]+$', token)


@pytest.mark.unit
@pytest.mark.security
def test_generate_refresh_token():
    """Test refresh token generation"""
    token = generate_refresh_token()

    assert isinstance(token, str)
    assert len(token) > 0
    assert re.match(r'^[A-Za-z0-9_-]+$', token)


@pytest.mark.unit
@pytest.mark.security
def test_generate_client_secret():
    """Test client secret generation (longer than tokens)"""
    secret = generate_client_secret()

    assert isinstance(secret, str)
    assert len(secret) > 43  # Should be longer than regular tokens
    assert re.match(r'^[A-Za-z0-9_-]+$', secret)


# =============================================================================
# Token Hashing Tests
# =============================================================================

@pytest.mark.unit
@pytest.mark.security
def test_hash_token():
    """Test token hashing produces SHA-256 hex digest"""
    token = "my-secret-token-12345"
    token_hash = hash_token(token)

    assert isinstance(token_hash, str)
    # SHA-256 hex digest is always 64 characters
    assert len(token_hash) == 64
    # Should be hex (0-9, a-f)
    assert re.match(r'^[0-9a-f]{64}$', token_hash)


@pytest.mark.unit
@pytest.mark.security
def test_hash_token_consistency():
    """Test hashing same token produces same hash"""
    token = "consistent-token-xyz"

    hash1 = hash_token(token)
    hash2 = hash_token(token)

    assert hash1 == hash2


@pytest.mark.unit
@pytest.mark.security
def test_hash_token_uniqueness():
    """Test different tokens produce different hashes"""
    token1 = "token-one"
    token2 = "token-two"

    hash1 = hash_token(token1)
    hash2 = hash_token(token2)

    assert hash1 != hash2


# =============================================================================
# PKCE Validation Tests
# =============================================================================

@pytest.mark.unit
@pytest.mark.security
def test_validate_pkce_plain_method_success():
    """Test PKCE plain method validation (verifier equals challenge)"""
    verifier = "my-code-verifier-12345"
    challenge = "my-code-verifier-12345"

    result = validate_pkce_challenge(verifier, challenge, "plain")

    assert result is True


@pytest.mark.unit
@pytest.mark.security
def test_validate_pkce_plain_method_failure():
    """Test PKCE plain method fails with mismatched verifier and challenge"""
    verifier = "my-code-verifier-12345"
    challenge = "different-challenge"

    result = validate_pkce_challenge(verifier, challenge, "plain")

    assert result is False


@pytest.mark.unit
@pytest.mark.security
def test_validate_pkce_s256_method_success():
    """Test PKCE S256 method validation with known test vector"""
    # Known test vector from RFC 7636
    verifier = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"
    challenge = "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM"

    result = validate_pkce_challenge(verifier, challenge, "S256")

    assert result is True


@pytest.mark.unit
@pytest.mark.security
def test_validate_pkce_s256_method_failure():
    """Test PKCE S256 method fails with invalid challenge"""
    verifier = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"
    challenge = "invalid-challenge-hash"

    result = validate_pkce_challenge(verifier, challenge, "S256")

    assert result is False


@pytest.mark.unit
@pytest.mark.security
def test_validate_pkce_invalid_method():
    """Test PKCE validation rejects invalid method"""
    verifier = "test-verifier"
    challenge = "test-challenge"

    result = validate_pkce_challenge(verifier, challenge, "MD5")

    assert result is False


# =============================================================================
# Token Expiration Tests
# =============================================================================

@pytest.mark.unit
@pytest.mark.security
def test_get_authorization_code_expiry():
    """Test authorization code expiry is 10 minutes from now"""
    before = datetime.now(timezone.utc)
    expiry = get_authorization_code_expiry()
    after = datetime.now(timezone.utc)

    # Should be approximately 10 minutes in the future
    expected_min = before + timedelta(minutes=10)
    expected_max = after + timedelta(minutes=10)

    assert expected_min <= expiry <= expected_max


@pytest.mark.unit
@pytest.mark.security
def test_get_device_code_expiry():
    """Test device code expiry is 10 minutes from now"""
    before = datetime.now(timezone.utc)
    expiry = get_device_code_expiry()
    after = datetime.now(timezone.utc)

    # Should be approximately 10 minutes in the future
    expected_min = before + timedelta(minutes=10)
    expected_max = after + timedelta(minutes=10)

    assert expected_min <= expiry <= expected_max


@pytest.mark.unit
@pytest.mark.security
def test_get_access_token_expiry():
    """Test access token expiry is 1 hour from now"""
    before = datetime.now(timezone.utc)
    expiry = get_access_token_expiry()
    after = datetime.now(timezone.utc)

    # Should be approximately 1 hour in the future
    expected_min = before + timedelta(hours=1)
    expected_max = after + timedelta(hours=1)

    assert expected_min <= expiry <= expected_max


@pytest.mark.unit
@pytest.mark.security
def test_get_refresh_token_expiry_confidential():
    """Test confidential client refresh token expiry is 30 days"""
    before = datetime.now(timezone.utc)
    expiry = get_refresh_token_expiry("confidential")
    after = datetime.now(timezone.utc)

    # Should be approximately 30 days in the future
    expected_min = before + timedelta(days=30)
    expected_max = after + timedelta(days=30)

    assert expected_min <= expiry <= expected_max


@pytest.mark.unit
@pytest.mark.security
def test_get_refresh_token_expiry_public():
    """Test public client refresh token expiry is 7 days"""
    before = datetime.now(timezone.utc)
    expiry = get_refresh_token_expiry("public")
    after = datetime.now(timezone.utc)

    # Should be approximately 7 days in the future
    expected_min = before + timedelta(days=7)
    expected_max = after + timedelta(days=7)

    assert expected_min <= expiry <= expected_max


@pytest.mark.unit
@pytest.mark.security
def test_is_token_expired_future():
    """Test token is not expired if expiry is in future"""
    future_time = datetime.now(timezone.utc) + timedelta(hours=1)

    result = is_token_expired(future_time)

    assert result is False


@pytest.mark.unit
@pytest.mark.security
def test_is_token_expired_past():
    """Test token is expired if expiry is in past"""
    past_time = datetime.now(timezone.utc) - timedelta(hours=1)

    result = is_token_expired(past_time)

    assert result is True


# =============================================================================
# Scope Validation Tests
# =============================================================================

@pytest.mark.unit
@pytest.mark.security
def test_validate_scopes_exact_match():
    """Test scope validation with exact match"""
    requested = ["read:concepts", "write:concepts"]
    allowed = ["read:concepts", "write:concepts", "admin:users"]

    is_valid, granted = validate_scopes(requested, allowed)

    assert is_valid is True
    assert granted == requested


@pytest.mark.unit
@pytest.mark.security
def test_validate_scopes_wildcard_full():
    """Test scope validation with full wildcard"""
    requested = ["read:concepts", "write:concepts", "admin:users"]
    allowed = ["*"]

    is_valid, granted = validate_scopes(requested, allowed)

    assert is_valid is True
    assert granted == requested


@pytest.mark.unit
@pytest.mark.security
def test_validate_scopes_wildcard_prefix():
    """Test scope validation with prefix wildcard"""
    requested = ["read:concepts", "read:users"]
    allowed = ["read:*"]

    is_valid, granted = validate_scopes(requested, allowed)

    assert is_valid is True
    assert granted == requested


@pytest.mark.unit
@pytest.mark.security
def test_validate_scopes_partial_grant():
    """Test scope validation grants only allowed scopes"""
    requested = ["read:concepts", "admin:users"]
    allowed = ["read:*"]

    is_valid, granted = validate_scopes(requested, allowed)

    assert is_valid is False  # Not all requested scopes granted
    assert granted == ["read:concepts"]  # Only read scope granted


@pytest.mark.unit
@pytest.mark.security
def test_validate_scopes_empty_request():
    """Test scope validation defaults to read:* if no scopes requested"""
    requested = []
    allowed = ["read:*"]

    is_valid, granted = validate_scopes(requested, allowed)

    assert is_valid is True
    assert granted == ["read:*"]


@pytest.mark.unit
@pytest.mark.security
def test_validate_scopes_no_match():
    """Test scope validation fails when no scopes match"""
    requested = ["admin:users"]
    allowed = ["read:*"]

    is_valid, granted = validate_scopes(requested, allowed)

    assert is_valid is False
    assert granted == []


# =============================================================================
# Scope Parsing Tests
# =============================================================================

@pytest.mark.unit
@pytest.mark.security
def test_parse_scope_string():
    """Test parsing space-separated scope string"""
    scope_string = "read:concepts write:concepts admin:users"

    result = parse_scope_string(scope_string)

    assert result == ["read:concepts", "write:concepts", "admin:users"]


@pytest.mark.unit
@pytest.mark.security
def test_parse_scope_string_empty():
    """Test parsing empty scope string"""
    result = parse_scope_string("")

    assert result == []


@pytest.mark.unit
@pytest.mark.security
def test_parse_scope_string_whitespace():
    """Test parsing scope string with extra whitespace"""
    scope_string = "  read:concepts   write:concepts  "

    result = parse_scope_string(scope_string)

    assert result == ["read:concepts", "write:concepts"]


@pytest.mark.unit
@pytest.mark.security
def test_format_scope_list():
    """Test formatting scope list as space-separated string"""
    scopes = ["read:concepts", "write:concepts", "admin:users"]

    result = format_scope_list(scopes)

    assert result == "read:concepts write:concepts admin:users"


@pytest.mark.unit
@pytest.mark.security
def test_format_scope_list_empty():
    """Test formatting empty scope list"""
    result = format_scope_list([])

    assert result == ""


@pytest.mark.unit
@pytest.mark.security
def test_parse_format_roundtrip():
    """Test parsing and formatting are inverse operations"""
    original = "read:concepts write:concepts admin:users"

    parsed = parse_scope_string(original)
    formatted = format_scope_list(parsed)

    assert formatted == original
