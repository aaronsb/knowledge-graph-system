"""
Vocabulary Configuration Management

Handles reading and writing vocabulary configuration from database (ADR-032 + Migration 017).
Provides functions for managing thresholds, profiles, and aggressiveness curves.
"""

import logging
from typing import Dict, List, Optional
from datetime import datetime

from ..lib.age_client import AGEClient
from ..lib.aggressiveness_curve import calculate_aggressiveness
from ..models.vocabulary import (
    VocabularyConfigResponse,
    VocabularyConfigDetail,
    AggressivenessProfile,
    ZoneEnum,
    PruningModeEnum
)

logger = logging.getLogger(__name__)


def load_vocabulary_config() -> VocabularyConfigResponse:
    """
    Load current vocabulary configuration (public view).

    Returns:
        VocabularyConfigResponse with current settings

    Raises:
        Exception: If unable to load configuration from database
    """
    client = AGEClient()
    try:
        return VocabularyConfigResponse(
            vocab_min=int(client.get_vocab_config('vocab_min', '30')),
            vocab_max=int(client.get_vocab_config('vocab_max', '90')),
            vocab_emergency=int(client.get_vocab_config('vocab_emergency', '300')),
            pruning_mode=PruningModeEnum(client.get_vocab_config('pruning_mode', 'hitl')),
            aggressiveness_profile=client.get_vocab_config('aggressiveness_profile', 'aggressive'),
            auto_expand_enabled=client.get_vocab_config('auto_expand_enabled', 'false').lower() == 'true',
            synonym_threshold_strong=float(client.get_vocab_config('synonym_threshold_strong', '0.90')),
            synonym_threshold_moderate=float(client.get_vocab_config('synonym_threshold_moderate', '0.70')),
            low_value_threshold=float(client.get_vocab_config('low_value_threshold', '1.0')),
            consolidation_similarity_threshold=float(client.get_vocab_config('consolidation_similarity_threshold', '0.90')),
            embedding_model=client.get_vocab_config('embedding_model', 'text-embedding-ada-002')
        )
    finally:
        client.close()


def load_vocabulary_config_detail() -> VocabularyConfigDetail:
    """
    Load full vocabulary configuration with computed fields (admin view).

    Returns:
        VocabularyConfigDetail with metadata and current state

    Raises:
        Exception: If unable to load configuration from database
    """
    client = AGEClient()
    try:
        # Load base configuration
        vocab_min = int(client.get_vocab_config('vocab_min', '30'))
        vocab_max = int(client.get_vocab_config('vocab_max', '90'))
        vocab_emergency = int(client.get_vocab_config('vocab_emergency', '300'))
        profile = client.get_vocab_config('aggressiveness_profile', 'aggressive')

        # Get current vocabulary size
        current_size = client.get_vocabulary_size()

        # Calculate current aggressiveness and zone
        aggressiveness, zone = calculate_aggressiveness(
            current_size=current_size,
            vocab_min=vocab_min,
            vocab_max=vocab_max,
            vocab_emergency=vocab_emergency,
            profile=profile
        )

        return VocabularyConfigDetail(
            vocab_min=vocab_min,
            vocab_max=vocab_max,
            vocab_emergency=vocab_emergency,
            pruning_mode=client.get_vocab_config('pruning_mode', 'hitl'),
            aggressiveness_profile=profile,
            auto_expand_enabled=client.get_vocab_config('auto_expand_enabled', 'false').lower() == 'true',
            synonym_threshold_strong=float(client.get_vocab_config('synonym_threshold_strong', '0.90')),
            synonym_threshold_moderate=float(client.get_vocab_config('synonym_threshold_moderate', '0.70')),
            low_value_threshold=float(client.get_vocab_config('low_value_threshold', '1.0')),
            consolidation_similarity_threshold=float(client.get_vocab_config('consolidation_similarity_threshold', '0.90')),
            embedding_model=client.get_vocab_config('embedding_model', 'text-embedding-ada-002'),
            current_size=current_size,
            zone=ZoneEnum(zone),
            aggressiveness=aggressiveness
        )
    finally:
        client.close()


def update_vocabulary_config(updates: Dict[str, any], updated_by: str) -> VocabularyConfigDetail:
    """
    Update vocabulary configuration in database.

    Args:
        updates: Dictionary of field names to new values
        updated_by: Username making the update

    Returns:
        Updated VocabularyConfigDetail

    Raises:
        Exception: If unable to update configuration
    """
    client = AGEClient()
    try:
        conn = client.pool.getconn()
        try:
            with conn.cursor() as cur:
                for key, value in updates.items():
                    # Convert boolean to string for database
                    if isinstance(value, bool):
                        value = 'true' if value else 'false'

                    # Update config in database
                    cur.execute("""
                        UPDATE kg_api.vocabulary_config
                        SET value = %s,
                            updated_at = NOW(),
                            updated_by = %s
                        WHERE key = %s
                    """, (str(value), updated_by, key))

                conn.commit()

                logger.info(f"Updated vocabulary config: {list(updates.keys())} by {updated_by}")

                # Return updated config
                return load_vocabulary_config_detail()
        finally:
            client.pool.putconn(conn)
    finally:
        client.close()


def list_aggressiveness_profiles() -> List[AggressivenessProfile]:
    """
    List all aggressiveness profiles.

    Returns:
        List of AggressivenessProfile objects

    Raises:
        Exception: If unable to query profiles
    """
    client = AGEClient()
    try:
        conn = client.pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT profile_name, control_x1, control_y1, control_x2, control_y2,
                           description, is_builtin, created_at, updated_at
                    FROM kg_api.aggressiveness_profiles
                    ORDER BY is_builtin DESC, profile_name ASC
                """)

                profiles = []
                for row in cur.fetchall():
                    profiles.append(AggressivenessProfile(
                        profile_name=row[0],
                        control_x1=row[1],
                        control_y1=row[2],
                        control_x2=row[3],
                        control_y2=row[4],
                        description=row[5],
                        is_builtin=row[6],
                        created_at=row[7],
                        updated_at=row[8]
                    ))

                return profiles
        finally:
            client.pool.putconn(conn)
    finally:
        client.close()


def get_aggressiveness_profile(profile_name: str) -> Optional[AggressivenessProfile]:
    """
    Get a specific aggressiveness profile.

    Args:
        profile_name: Name of the profile

    Returns:
        AggressivenessProfile or None if not found
    """
    client = AGEClient()
    try:
        conn = client.pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT profile_name, control_x1, control_y1, control_x2, control_y2,
                           description, is_builtin, created_at, updated_at
                    FROM kg_api.aggressiveness_profiles
                    WHERE profile_name = %s
                """, (profile_name,))

                row = cur.fetchone()
                if not row:
                    return None

                return AggressivenessProfile(
                    profile_name=row[0],
                    control_x1=row[1],
                    control_y1=row[2],
                    control_x2=row[3],
                    control_y2=row[4],
                    description=row[5],
                    is_builtin=row[6],
                    created_at=row[7],
                    updated_at=row[8]
                )
        finally:
            client.pool.putconn(conn)
    finally:
        client.close()


def create_aggressiveness_profile(
    profile_name: str,
    control_x1: float,
    control_y1: float,
    control_x2: float,
    control_y2: float,
    description: str
) -> AggressivenessProfile:
    """
    Create a new custom aggressiveness profile.

    Args:
        profile_name: Unique name for the profile
        control_x1: First control point X (0.0-1.0)
        control_y1: First control point Y
        control_x2: Second control point X (0.0-1.0)
        control_y2: Second control point Y
        description: Description of the profile behavior

    Returns:
        Created AggressivenessProfile

    Raises:
        Exception: If profile already exists or database error
    """
    client = AGEClient()
    try:
        conn = client.pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO kg_api.aggressiveness_profiles
                        (profile_name, control_x1, control_y1, control_x2, control_y2, description, is_builtin)
                    VALUES (%s, %s, %s, %s, %s, %s, FALSE)
                    RETURNING profile_name, control_x1, control_y1, control_x2, control_y2,
                              description, is_builtin, created_at, updated_at
                """, (profile_name, control_x1, control_y1, control_x2, control_y2, description))

                row = cur.fetchone()
                conn.commit()

                logger.info(f"Created custom aggressiveness profile: {profile_name}")

                return AggressivenessProfile(
                    profile_name=row[0],
                    control_x1=row[1],
                    control_y1=row[2],
                    control_x2=row[3],
                    control_y2=row[4],
                    description=row[5],
                    is_builtin=row[6],
                    created_at=row[7],
                    updated_at=row[8]
                )
        finally:
            client.pool.putconn(conn)
    finally:
        client.close()


def delete_aggressiveness_profile(profile_name: str) -> bool:
    """
    Delete a custom aggressiveness profile.

    Args:
        profile_name: Name of the profile to delete

    Returns:
        True if deleted successfully

    Raises:
        Exception: If profile is builtin or database error

    Note:
        Builtin profiles cannot be deleted (protected by database trigger)
    """
    client = AGEClient()
    try:
        conn = client.pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    DELETE FROM kg_api.aggressiveness_profiles
                    WHERE profile_name = %s
                    RETURNING profile_name
                """, (profile_name,))

                deleted = cur.fetchone() is not None
                conn.commit()

                if deleted:
                    logger.info(f"Deleted custom aggressiveness profile: {profile_name}")

                return deleted
        finally:
            client.pool.putconn(conn)
    finally:
        client.close()
