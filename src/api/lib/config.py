"""
Centralized configuration module for runtime mode detection.

This module provides a single source of truth for determining whether the system
is running in development mode (.env configuration) or production mode (database
configuration).

ADR-041: AI Extraction Provider Configuration
"""

import os
import logging

logger = logging.getLogger(__name__)

# ============================================================================
# Development Mode Flag
# ============================================================================
# Controls configuration source:
#   - DEVELOPMENT_MODE=true  → Use .env configuration (development)
#   - DEVELOPMENT_MODE=false → Use database configuration (production)
#
# This affects ALL configuration sources:
#   - AI provider selection (OpenAI, Anthropic, Local)
#   - Model selection (gpt-4o, claude-sonnet-4, llama-3.1)
#   - Embedding configuration
#   - API keys (if providers need them)
#
# Default: false (production mode)
# ============================================================================

DEVELOPMENT_MODE = os.getenv('DEVELOPMENT_MODE', 'false').lower() == 'true'


def is_development_mode() -> bool:
    """
    Check if the system is running in development mode.

    Returns:
        True if DEVELOPMENT_MODE=true in environment, False otherwise

    Examples:
        >>> is_development_mode()
        False  # Default behavior (production)

        # With DEVELOPMENT_MODE=true
        >>> is_development_mode()
        True
    """
    return DEVELOPMENT_MODE


def get_config_source() -> str:
    """
    Get the current configuration source name.

    Returns:
        'environment' if in development mode, 'database' if in production mode

    Examples:
        >>> get_config_source()
        'database'  # Default (production)

        # With DEVELOPMENT_MODE=true
        >>> get_config_source()
        'environment'
    """
    return 'environment' if DEVELOPMENT_MODE else 'database'


def log_configuration_mode():
    """
    Log the current configuration mode at startup.

    This is called during API initialization to provide visibility
    into which configuration source is being used.
    """
    if DEVELOPMENT_MODE:
        logger.warning("╔════════════════════════════════════════╗")
        logger.warning("║   ⚠️  DEVELOPMENT MODE ACTIVE  ⚠️      ║")
        logger.warning("╚════════════════════════════════════════╝")
        logger.warning("Configuration source: .env file")
        logger.warning("Database configuration will be IGNORED")
        logger.warning("Set DEVELOPMENT_MODE=false for production")
        logger.warning("")
    else:
        logger.info("📍 Configuration mode: PRODUCTION")
        logger.info("   Configuration source: database")
        logger.info("   .env values will be IGNORED (except database credentials)")
        logger.info("")


# ============================================================================
# Startup Warning (Auto-executed on import)
# ============================================================================
# When this module is imported, we immediately log the configuration mode
# to ensure developers are aware of which mode is active.
# ============================================================================

log_configuration_mode()
