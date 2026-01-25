"""
Garage Client - Backward compatibility re-export (ADR-080).

This file exists for backward compatibility with existing imports.
All functionality has been refactored into the modular garage package:

    api.app/lib/garage/
    ├── base.py              - GarageBaseClient
    ├── image_storage.py     - ImageStorageService
    ├── projection_storage.py - ProjectionStorageService
    ├── source_storage.py    - SourceDocumentService
    └── retention.py         - RetentionPolicyManager

New code should import from the garage package:

    # Preferred
    from api.app.lib.garage import get_image_storage, get_projection_storage

    # Also available
    from api.app.lib.garage import GarageClient, get_garage_client
"""

# Re-export everything from the new package for backward compatibility
from .garage import (
    # Base client
    GarageBaseClient,
    sanitize_path_component,

    # Services
    ImageStorageService,
    ProjectionStorageService,
    SourceDocumentService,
    RetentionPolicyManager,

    # Data classes
    DocumentIdentity,
    CleanupResult,
    StorageStats,

    # Factory functions
    get_base_client,
    get_image_storage,
    get_projection_storage,
    get_source_storage,
    get_retention_manager,

    # Backward compatibility
    GarageClient,
    get_garage_client,
)

# Re-export the internal credential function for tests
from .garage.base import _get_garage_credentials

__all__ = [
    'GarageBaseClient',
    'sanitize_path_component',
    'ImageStorageService',
    'ProjectionStorageService',
    'SourceDocumentService',
    'RetentionPolicyManager',
    'DocumentIdentity',
    'CleanupResult',
    'StorageStats',
    'get_base_client',
    'get_image_storage',
    'get_projection_storage',
    'get_source_storage',
    'get_retention_manager',
    'GarageClient',
    'get_garage_client',
    '_get_garage_credentials',
]
