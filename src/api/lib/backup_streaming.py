"""
Backup Streaming Service

Implements ADR-015 Phase 2: Streaming backup download with chunked transfer encoding.
Converts backup dictionaries into JSON streams without loading entire backup into memory.

Defense in Depth: Validates backup data before streaming to catch DataExporter bugs
or database inconsistencies early.
"""

import json
import logging
from typing import Dict, Any, AsyncGenerator
from datetime import datetime

from ...lib.serialization import DataExporter
from .age_client import AGEClient
from .backup_integrity import check_backup_data

logger = logging.getLogger(__name__)


async def stream_backup_json(backup_data: Dict[str, Any], chunk_size: int = 8192) -> AsyncGenerator[bytes, None]:
    """
    Stream backup data as JSON chunks

    Args:
        backup_data: Complete backup dictionary
        chunk_size: Size of chunks to yield (default: 8KB)

    Yields:
        JSON bytes in chunks for streaming response
    """
    # Convert to JSON string
    json_str = json.dumps(backup_data, indent=2)
    json_bytes = json_str.encode('utf-8')

    # Yield in chunks
    for i in range(0, len(json_bytes), chunk_size):
        chunk = json_bytes[i:i + chunk_size]
        yield chunk


async def create_backup_stream(
    client: AGEClient,
    backup_type: str,
    ontology_name: str = None
) -> tuple[AsyncGenerator[bytes, None], str]:
    """
    Create streaming backup response

    Args:
        client: AGEClient instance
        backup_type: "full" or "ontology"
        ontology_name: Required if backup_type is "ontology"

    Returns:
        Tuple of (stream generator, filename)

    Raises:
        ValueError: If backup_type is invalid or ontology_name missing
    """
    # Validate request
    if backup_type == "ontology" and not ontology_name:
        raise ValueError("ontology_name required for ontology backup")

    if backup_type not in ("full", "ontology"):
        raise ValueError(f"Invalid backup_type: {backup_type}")

    # Generate backup data
    if backup_type == "full":
        backup_data = DataExporter.export_full_backup(client)
        filename = f"full_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    else:
        backup_data = DataExporter.export_ontology_backup(client, ontology_name)
        # Sanitize ontology name for filename
        safe_name = ontology_name.lower().replace(" ", "_").replace("/", "_")
        filename = f"{safe_name}_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

    # Validate backup before streaming (defense in depth)
    # Catches DataExporter bugs or database inconsistencies early
    integrity = check_backup_data(backup_data)

    if not integrity.valid:
        # Collect all error messages
        error_msgs = [f"{e.category}: {e.message}" for e in integrity.errors]
        error_summary = "; ".join(error_msgs)
        logger.error(f"Backup generation failed validation: {error_summary}")
        raise ValueError(f"Backup generation failed validation: {error_summary}")

    # Log validation success with statistics
    stats = integrity.statistics or {}
    logger.info(
        f"Backup validated successfully - "
        f"Concepts: {stats.get('concepts', 0)}, "
        f"Sources: {stats.get('sources', 0)}, "
        f"Instances: {stats.get('instances', 0)}, "
        f"Relationships: {stats.get('relationships', 0)}, "
        f"Vocabulary: {stats.get('vocabulary', 0)}"
    )

    # Summarize warnings (ADR-032)
    if integrity.warnings:
        from collections import Counter
        warning_categories = Counter(w.category for w in integrity.warnings)

        # Count reference warnings (pre-ADR-032 relationships)
        ref_warnings = sum(1 for w in integrity.warnings if w.category == 'references' and 'which is not in vocabulary table' in w.message)

        # Log pre-ADR-032 relationships as INFO (not a problem, just historical)
        if ref_warnings > 0:
            logger.info(f"Backup contains {ref_warnings} relationships with types not in vocabulary table (pre-ADR-032 data)")

        # Log other warnings normally
        other_warnings = [w for w in integrity.warnings if w.category != 'references' or 'which is not in vocabulary table' not in w.message]
        if other_warnings:
            other_categories = Counter(w.category for w in other_warnings)
            for category, count in other_categories.items():
                logger.warning(f"Backup validation: {count} warnings in category '{category}'")

            # Show examples of actual issues
            examples = other_warnings[:3]
            for warning in examples:
                logger.warning(f"  Example: {warning.message}")

    # Create stream
    stream = stream_backup_json(backup_data)

    return stream, filename


def get_backup_size(backup_data: Dict[str, Any]) -> int:
    """
    Calculate size of backup in bytes

    Args:
        backup_data: Backup dictionary

    Returns:
        Size in bytes
    """
    json_str = json.dumps(backup_data, indent=2)
    return len(json_str.encode('utf-8'))
