"""
Vocabulary Configuration Routes

API endpoints for vocabulary configuration management.

Public endpoints:
- GET /vocabulary/config - Get vocabulary configuration summary

Admin endpoints:
- GET /admin/vocabulary/config - Get full configuration details
- PUT /admin/vocabulary/config - Update configuration
- GET /admin/vocabulary/profiles - List aggressiveness profiles
- GET /admin/vocabulary/profiles/{name} - Get specific profile
- POST /admin/vocabulary/profiles - Create custom profile
- DELETE /admin/vocabulary/profiles/{name} - Delete custom profile
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, status
from typing import Optional

from ..dependencies.auth import CurrentUser, require_role
from ..models.vocabulary import (
    VocabularyConfigResponse,
    VocabularyConfigDetail,
    UpdateConfigRequest,
    UpdateConfigResponse,
    AggressivenessProfile,
    ProfileListResponse,
    CreateProfileRequest,
    DeleteProfileResponse
)
from ..lib.vocabulary_config import (
    load_vocabulary_config,
    load_vocabulary_config_detail,
    update_vocabulary_config,
    list_aggressiveness_profiles,
    get_aggressiveness_profile,
    create_aggressiveness_profile,
    delete_aggressiveness_profile
)

# Public router (no auth)
public_router = APIRouter(prefix="/vocabulary", tags=["vocabulary"])

# Admin router (requires auth in production)
admin_router = APIRouter(prefix="/admin/vocabulary", tags=["admin", "vocabulary"])

logger = logging.getLogger(__name__)


# =============================================================================
# Public Configuration Endpoints
# =============================================================================

@public_router.get("/config", response_model=VocabularyConfigResponse)
async def get_vocabulary_config():
    """
    Get current vocabulary configuration (public endpoint).

    Returns summary information suitable for clients to determine:
    - Vocabulary size thresholds (min, max, emergency)
    - Pruning mode and aggressiveness profile
    - Synonym detection thresholds
    - Auto-expand settings

    This endpoint does not require authentication.
    """
    try:
        config = load_vocabulary_config()
        return config
    except Exception as e:
        logger.error(f"Failed to get vocabulary config: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get vocabulary config: {str(e)}"
        )


# =============================================================================
# Admin Configuration Endpoints
# =============================================================================

@admin_router.get("/config", response_model=VocabularyConfigDetail)
async def get_vocabulary_config_detail(
    current_user: CurrentUser,
    _: None = Depends(require_role("admin"))
):
    """
    Get full vocabulary configuration details (Admin only - ADR-060)

    **Authentication:** Requires admin role

    Returns complete configuration including:
    - All threshold settings
    - Current vocabulary size and zone
    - Computed aggressiveness percentage
    - Metadata (updated_at, updated_by, etc.)
    """
    try:
        config = load_vocabulary_config_detail()
        return config
    except Exception as e:
        logger.error(f"Failed to get vocabulary config details: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get vocabulary config details: {str(e)}"
        )


@admin_router.put("/config", response_model=UpdateConfigResponse)
async def update_vocabulary_config_endpoint(
    request: UpdateConfigRequest,
    current_user: CurrentUser,
    _: None = Depends(require_role("admin"))
):
    """
    Update vocabulary configuration (Admin only - ADR-060)

    **Authentication:** Requires admin role

    Updates configuration values in the database. Only provided fields are updated.

    Request body:
        - vocab_min (optional): Minimum vocabulary size (e.g., 30)
        - vocab_max (optional): Maximum vocabulary size (e.g., 225-275)
        - vocab_emergency (optional): Emergency threshold (e.g., 300-400)
        - pruning_mode (optional): Decision mode (naive, hitl, aitl)
        - aggressiveness_profile (optional): Profile name
        - auto_expand_enabled (optional): Enable automatic expansion
        - synonym_threshold_strong (optional): Strong synonym threshold (0.7-1.0)
        - synonym_threshold_moderate (optional): Moderate synonym threshold (0.5-0.9)
        - low_value_threshold (optional): Low value score threshold (0.0-10.0)
        - consolidation_similarity_threshold (optional): Auto-merge threshold (0.5-1.0)
        - updated_by (required): Username making the update

    Returns:
        Updated configuration with metadata
    """
    try:
        # Build updates dictionary (only non-None fields)
        updates = {}
        if request.vocab_min is not None:
            updates['vocab_min'] = request.vocab_min
        if request.vocab_max is not None:
            updates['vocab_max'] = request.vocab_max
        if request.vocab_emergency is not None:
            updates['vocab_emergency'] = request.vocab_emergency
        if request.pruning_mode is not None:
            updates['pruning_mode'] = request.pruning_mode.value
        if request.aggressiveness_profile is not None:
            updates['aggressiveness_profile'] = request.aggressiveness_profile
        if request.auto_expand_enabled is not None:
            updates['auto_expand_enabled'] = request.auto_expand_enabled
        if request.synonym_threshold_strong is not None:
            updates['synonym_threshold_strong'] = request.synonym_threshold_strong
        if request.synonym_threshold_moderate is not None:
            updates['synonym_threshold_moderate'] = request.synonym_threshold_moderate
        if request.low_value_threshold is not None:
            updates['low_value_threshold'] = request.low_value_threshold
        if request.consolidation_similarity_threshold is not None:
            updates['consolidation_similarity_threshold'] = request.consolidation_similarity_threshold

        if not updates:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No configuration fields provided for update"
            )

        # Update configuration
        updated_config = update_vocabulary_config(updates, request.updated_by)

        return UpdateConfigResponse(
            success=True,
            updated_fields=list(updates.keys()),
            config=updated_config,
            message=f"Updated {len(updates)} configuration fields"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update vocabulary config: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update vocabulary config: {str(e)}"
        )


# =============================================================================
# Aggressiveness Profile Endpoints
# =============================================================================

@admin_router.get("/profiles", response_model=ProfileListResponse)
async def list_profiles(
    current_user: CurrentUser,
    _: None = Depends(require_role("admin"))
):
    """
    List all aggressiveness profiles (Admin only - ADR-060)

    **Authentication:** Requires admin role

    Returns:
        List of all profiles (builtin and custom) with Bezier curve parameters
    """
    try:
        profiles = list_aggressiveness_profiles()

        builtin_count = sum(1 for p in profiles if p.is_builtin)
        custom_count = len(profiles) - builtin_count

        return ProfileListResponse(
            total=len(profiles),
            builtin=builtin_count,
            custom=custom_count,
            profiles=profiles
        )
    except Exception as e:
        logger.error(f"Failed to list aggressiveness profiles: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list aggressiveness profiles: {str(e)}"
        )


@admin_router.get("/profiles/{profile_name}", response_model=AggressivenessProfile)
async def get_profile(
    profile_name: str,
    current_user: CurrentUser,
    _: None = Depends(require_role("admin"))
):
    """
    Get specific aggressiveness profile details (Admin only - ADR-060)

    **Authentication:** Requires admin role

    Args:
        profile_name: Name of the profile

    Returns:
        Profile with Bezier curve parameters and metadata
    """
    try:
        profile = get_aggressiveness_profile(profile_name)

        if not profile:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Profile not found: {profile_name}"
            )

        return profile
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get aggressiveness profile: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get aggressiveness profile: {str(e)}"
        )


@admin_router.post("/profiles", response_model=AggressivenessProfile, status_code=status.HTTP_201_CREATED)
async def create_profile(
    request: CreateProfileRequest,
    current_user: CurrentUser,
    _: None = Depends(require_role("admin"))
):
    """
    Create custom aggressiveness profile (Admin only - ADR-060)

    **Authentication:** Requires admin role

    Creates a new Bezier curve profile for vocabulary aggressiveness control.

    Request body:
        - profile_name: Unique name (3-50 chars)
        - control_x1: First control point X (0.0-1.0)
        - control_y1: First control point Y (-2.0 to 2.0)
        - control_x2: Second control point X (0.0-1.0)
        - control_y2: Second control point Y (-2.0 to 2.0)
        - description: Profile behavior description (min 10 chars)

    Returns:
        Created profile with metadata
    """
    try:
        profile = create_aggressiveness_profile(
            profile_name=request.profile_name,
            control_x1=request.control_x1,
            control_y1=request.control_y1,
            control_x2=request.control_x2,
            control_y2=request.control_y2,
            description=request.description
        )

        return profile
    except Exception as e:
        logger.error(f"Failed to create aggressiveness profile: {e}", exc_info=True)

        # Handle duplicate profile name
        if "duplicate key" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Profile already exists: {request.profile_name}"
            )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create aggressiveness profile: {str(e)}"
        )


@admin_router.delete("/profiles/{profile_name}", response_model=DeleteProfileResponse)
async def delete_profile(
    profile_name: str,
    current_user: CurrentUser,
    _: None = Depends(require_role("admin"))
):
    """
    Delete custom aggressiveness profile (Admin only - ADR-060)

    **Authentication:** Requires admin role

    Args:
        profile_name: Name of the profile to delete

    Returns:
        Deletion confirmation

    Note:
        Builtin profiles cannot be deleted (protected by database trigger)
    """
    try:
        deleted = delete_aggressiveness_profile(profile_name)

        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Profile not found: {profile_name}"
            )

        return DeleteProfileResponse(
            success=True,
            profile_name=profile_name,
            message=f"Successfully deleted profile: {profile_name}"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete aggressiveness profile: {e}", exc_info=True)

        # Handle builtin profile protection
        if "cannot delete builtin" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Cannot delete builtin profile: {profile_name}"
            )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete aggressiveness profile: {str(e)}"
        )
