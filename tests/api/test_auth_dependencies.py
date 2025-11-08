"""
Authentication Dependencies Tests (ADR-054, ADR-060)

Unit tests for authentication dependency injection functions.

Tests:
- get_current_user() - OAuth token validation
- get_current_active_user() - Disabled user handling
- require_role() - Role-based access control
- CurrentUser type alias resolution
"""

import pytest
from fastapi import HTTPException
from src.api.dependencies.auth import (
    get_current_user,
    get_current_active_user,
    require_role,
)
from src.api.models.auth import UserInDB


# =============================================================================
# get_current_user() Tests
# =============================================================================

@pytest.mark.unit
@pytest.mark.security
@pytest.mark.asyncio
async def test_get_current_user_valid_token(mock_oauth_validation, create_test_oauth_token):
    """Test get_current_user returns user with valid OAuth token"""
    token = create_test_oauth_token(user_id=100, role="contributor")

    user = await get_current_user(token)

    assert user is not None
    assert isinstance(user, UserInDB)
    assert user.id == 100
    assert user.role == "contributor"
    assert user.disabled is False


@pytest.mark.unit
@pytest.mark.security
@pytest.mark.asyncio
async def test_get_current_user_admin_token(mock_oauth_validation, create_test_oauth_token):
    """Test get_current_user returns admin user with admin token"""
    token = create_test_oauth_token(user_id=101, role="admin")

    user = await get_current_user(token)

    assert user is not None
    assert user.id == 101
    assert user.role == "admin"


@pytest.mark.unit
@pytest.mark.security
@pytest.mark.asyncio
async def test_get_current_user_expired_token(mock_oauth_validation, create_test_oauth_token):
    """Test get_current_user returns 401 with expired token"""
    token = create_test_oauth_token(user_id=100, role="contributor", expired=True)

    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(token)

    assert exc_info.value.status_code == 401
    assert "Could not validate credentials" in exc_info.value.detail


@pytest.mark.unit
@pytest.mark.security
@pytest.mark.asyncio
async def test_get_current_user_invalid_token(mock_oauth_validation):
    """Test get_current_user returns 401 with invalid token"""
    token = "invalid_token_format"

    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(token)

    assert exc_info.value.status_code == 401


@pytest.mark.unit
@pytest.mark.security
@pytest.mark.asyncio
async def test_get_current_user_malformed_test_token(mock_oauth_validation):
    """Test get_current_user returns 401 with malformed test token"""
    token = "test_oauth_token:malformed"

    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(token)

    assert exc_info.value.status_code == 401


# =============================================================================
# get_current_active_user() Tests
# =============================================================================

@pytest.mark.unit
@pytest.mark.security
@pytest.mark.asyncio
async def test_get_current_active_user_active(mock_oauth_validation, create_test_oauth_token):
    """Test get_current_active_user passes for active user"""
    token = create_test_oauth_token(user_id=100, role="contributor")
    current_user = await get_current_user(token)

    active_user = await get_current_active_user(current_user)

    assert active_user is not None
    assert active_user.disabled is False


@pytest.mark.unit
@pytest.mark.security
@pytest.mark.asyncio
async def test_get_current_active_user_disabled(mock_oauth_validation, test_user_credentials):
    """Test get_current_active_user returns 403 for disabled user"""
    from src.api.models.auth import UserInDB

    # Create disabled user
    disabled_user = UserInDB(**{**test_user_credentials, "disabled": True})

    with pytest.raises(HTTPException) as exc_info:
        await get_current_active_user(disabled_user)

    assert exc_info.value.status_code == 403
    assert "disabled" in exc_info.value.detail.lower()


# =============================================================================
# require_role() Tests
# =============================================================================

@pytest.mark.unit
@pytest.mark.security
@pytest.mark.asyncio
async def test_require_role_correct_role(mock_oauth_validation, create_test_oauth_token):
    """Test require_role passes with correct role"""
    token = create_test_oauth_token(user_id=101, role="admin")
    current_user = await get_current_user(token)

    # Create the role checker
    check_admin = require_role("admin")

    # Should not raise
    result = await check_admin(current_user)
    assert result.role == "admin"


@pytest.mark.unit
@pytest.mark.security
@pytest.mark.asyncio
async def test_require_role_multiple_allowed_roles(mock_oauth_validation, create_test_oauth_token):
    """Test require_role passes when user has one of multiple allowed roles"""
    token = create_test_oauth_token(user_id=100, role="contributor")
    current_user = await get_current_user(token)

    # Create role checker that allows both contributor and admin
    check_role = require_role("contributor", "admin")

    # Should not raise
    result = await check_role(current_user)
    assert result.role == "contributor"


@pytest.mark.unit
@pytest.mark.security
@pytest.mark.asyncio
async def test_require_role_wrong_role(mock_oauth_validation, create_test_oauth_token):
    """Test require_role returns 403 with wrong role"""
    token = create_test_oauth_token(user_id=100, role="contributor")
    current_user = await get_current_user(token)

    # Create admin-only checker
    check_admin = require_role("admin")

    with pytest.raises(HTTPException) as exc_info:
        await check_admin(current_user)

    assert exc_info.value.status_code == 403
    assert "admin" in exc_info.value.detail.lower()


@pytest.mark.unit
@pytest.mark.security
@pytest.mark.asyncio
async def test_require_role_disabled_user_rejected(mock_oauth_validation, test_user_credentials):
    """Test require_role rejects disabled user even with correct role"""
    from src.api.models.auth import UserInDB

    # Create disabled admin
    disabled_admin = UserInDB(**{**test_user_credentials, "role": "admin", "disabled": True})

    # The get_current_active_user should fail before role check
    with pytest.raises(HTTPException) as exc_info:
        await get_current_active_user(disabled_admin)

    assert exc_info.value.status_code == 403


# =============================================================================
# Type Alias Tests
# =============================================================================

@pytest.mark.unit
@pytest.mark.security
def test_current_user_type_alias_exists():
    """Test CurrentUser type alias is defined"""
    from src.api.dependencies.auth import CurrentUser

    # Should be importable
    assert CurrentUser is not None


@pytest.mark.unit
@pytest.mark.security
def test_token_dep_type_alias_exists():
    """Test TokenDep type alias is defined"""
    from src.api.dependencies.auth import TokenDep

    # Should be importable
    assert TokenDep is not None


# =============================================================================
# Integration Tests (Dependencies Working Together)
# =============================================================================

@pytest.mark.unit
@pytest.mark.security
@pytest.mark.asyncio
async def test_full_auth_chain_user(mock_oauth_validation, create_test_oauth_token):
    """Test full authentication chain for regular user"""
    # 1. Token validation
    token = create_test_oauth_token(user_id=100, role="contributor")
    current_user = await get_current_user(token)

    # 2. Active user check
    active_user = await get_current_active_user(current_user)

    # 3. Role check
    check_user = require_role("contributor", "admin")
    final_user = await check_user(active_user)

    assert final_user.id == 100
    assert final_user.role == "contributor"


@pytest.mark.unit
@pytest.mark.security
@pytest.mark.asyncio
async def test_full_auth_chain_admin(mock_oauth_validation, create_test_oauth_token):
    """Test full authentication chain for admin user"""
    # 1. Token validation
    token = create_test_oauth_token(user_id=101, role="admin")
    current_user = await get_current_user(token)

    # 2. Active user check
    active_user = await get_current_active_user(current_user)

    # 3. Admin role check
    check_admin = require_role("admin")
    final_user = await check_admin(active_user)

    assert final_user.id == 101
    assert final_user.role == "admin"


@pytest.mark.unit
@pytest.mark.security
@pytest.mark.asyncio
async def test_auth_chain_fails_at_token_validation(mock_oauth_validation):
    """Test auth chain fails at first step with invalid token"""
    with pytest.raises(HTTPException) as exc_info:
        await get_current_user("invalid_token")

    assert exc_info.value.status_code == 401


@pytest.mark.unit
@pytest.mark.security
@pytest.mark.asyncio
async def test_auth_chain_fails_at_active_check(mock_oauth_validation, test_user_credentials):
    """Test auth chain fails at active user check for disabled user"""
    from src.api.models.auth import UserInDB

    disabled_user = UserInDB(**{**test_user_credentials, "disabled": True})

    with pytest.raises(HTTPException) as exc_info:
        await get_current_active_user(disabled_user)

    assert exc_info.value.status_code == 403


@pytest.mark.unit
@pytest.mark.security
@pytest.mark.asyncio
async def test_auth_chain_fails_at_role_check(mock_oauth_validation, create_test_oauth_token):
    """Test auth chain fails at role check for insufficient permissions"""
    token = create_test_oauth_token(user_id=100, role="contributor")
    current_user = await get_current_user(token)
    active_user = await get_current_active_user(current_user)

    check_admin = require_role("admin")

    with pytest.raises(HTTPException) as exc_info:
        await check_admin(active_user)

    assert exc_info.value.status_code == 403
