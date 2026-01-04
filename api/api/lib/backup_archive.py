"""
Backup Archive Service - Tarball archive with Garage documents

Creates .tar.gz archives containing:
- manifest.json (graph data with document references)
- documents/ (original source documents from Garage)

Archive structure:
    backup_<ontology>_<date>/
    ├── manifest.json
    └── documents/
        ├── sources/
        │   └── <ontology>/
        │       └── <hash>.txt
        └── images/
            └── <ontology>/
                ├── <source_id>.jpg
                └── <source_id>_prose.md
"""

import io
import json
import tarfile
import logging
from datetime import datetime
from typing import Dict, Any, Optional, AsyncGenerator, List

from ...lib.serialization import DataExporter, BackupFormat
from .age_client import AGEClient
from .backup_integrity import check_backup_data
from .garage import get_source_storage, get_image_storage

logger = logging.getLogger(__name__)


def _get_archive_base_name(ontology: Optional[str] = None) -> str:
    """Generate base name for archive directory."""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    if ontology:
        safe_name = ontology.lower().replace(" ", "_").replace("/", "_")
        return f"backup_{safe_name}_{timestamp}"
    else:
        return f"backup_full_{timestamp}"


def _add_document_paths_to_sources(sources: List[Dict[str, Any]], archive_base: str) -> List[Dict[str, Any]]:
    """
    Add document_path field to source entries for archive references.

    Args:
        sources: List of source dictionaries
        archive_base: Base directory name in archive

    Returns:
        Sources with document_path added where garage_key exists
    """
    for source in sources:
        if source.get("garage_key"):
            # Mirror Garage structure in archive
            source["document_path"] = f"{archive_base}/documents/{source['garage_key']}"
        if source.get("storage_key"):
            # For images
            source["image_path"] = f"{archive_base}/documents/{source['storage_key']}"
    return sources


def create_backup_archive(
    client: AGEClient,
    backup_type: str,
    ontology_name: Optional[str] = None
) -> tuple[io.BytesIO, str]:
    """
    Create a complete backup archive with Garage documents.

    Args:
        client: AGEClient instance
        backup_type: "full" or "ontology"
        ontology_name: Required if backup_type is "ontology"

    Returns:
        Tuple of (archive bytes buffer, filename)

    Raises:
        ValueError: If parameters invalid or backup fails validation
    """
    if backup_type == "ontology" and not ontology_name:
        raise ValueError("ontology_name required for ontology backup")

    if backup_type not in ("full", "ontology"):
        raise ValueError(f"Invalid backup_type: {backup_type}")

    # Generate backup data
    logger.info(f"Generating backup data (type={backup_type}, ontology={ontology_name})")
    if backup_type == "full":
        backup_data = DataExporter.export_full_backup(client)
    else:
        backup_data = DataExporter.export_ontology_backup(client, ontology_name)

    # Validate backup
    integrity = check_backup_data(backup_data)
    if not integrity.valid:
        error_msgs = [f"{e.category}: {e.message}" for e in integrity.errors]
        raise ValueError(f"Backup validation failed: {'; '.join(error_msgs)}")

    # Generate archive name
    archive_base = _get_archive_base_name(ontology_name)
    filename = f"{archive_base}.tar.gz"

    # Add document paths to sources
    backup_data["data"]["sources"] = _add_document_paths_to_sources(
        backup_data["data"]["sources"],
        archive_base
    )

    # Create tarball in memory
    buffer = io.BytesIO()

    with tarfile.open(fileobj=buffer, mode='w:gz') as tar:
        # Add manifest.json
        manifest_json = json.dumps(backup_data, indent=2).encode('utf-8')
        manifest_info = tarfile.TarInfo(name=f"{archive_base}/manifest.json")
        manifest_info.size = len(manifest_json)
        tar.addfile(manifest_info, io.BytesIO(manifest_json))
        logger.info(f"Added manifest.json ({len(manifest_json)} bytes)")

        # Fetch and add Garage documents
        source_storage = get_source_storage()
        image_storage = get_image_storage()

        docs_added = 0
        docs_failed = 0

        for source in backup_data["data"]["sources"]:
            # Add source document from Garage
            if source.get("garage_key"):
                try:
                    content = source_storage.get(source["garage_key"])
                    if content:
                        doc_path = f"{archive_base}/documents/{source['garage_key']}"
                        doc_info = tarfile.TarInfo(name=doc_path)
                        doc_info.size = len(content)
                        tar.addfile(doc_info, io.BytesIO(content))
                        docs_added += 1
                    else:
                        logger.warning(f"Document not found in Garage: {source['garage_key']}")
                        docs_failed += 1
                except Exception as e:
                    logger.warning(f"Failed to fetch {source['garage_key']}: {e}")
                    docs_failed += 1

            # Add image from Garage (if content_type is image)
            if source.get("storage_key") and source.get("content_type") == "image":
                try:
                    content = image_storage.base.get_object(source["storage_key"])
                    if content:
                        img_path = f"{archive_base}/documents/{source['storage_key']}"
                        img_info = tarfile.TarInfo(name=img_path)
                        img_info.size = len(content)
                        tar.addfile(img_info, io.BytesIO(content))
                        docs_added += 1
                except Exception as e:
                    logger.warning(f"Failed to fetch image {source['storage_key']}: {e}")
                    docs_failed += 1

        logger.info(f"Added {docs_added} documents to archive ({docs_failed} failed)")

    # Reset buffer position for reading
    buffer.seek(0)

    stats = backup_data.get("statistics", {})
    logger.info(
        f"Created backup archive: {filename} - "
        f"Concepts: {stats.get('concepts', 0)}, "
        f"Sources: {stats.get('sources', 0)}, "
        f"Documents: {docs_added}"
    )

    return buffer, filename


async def stream_backup_archive(
    client: AGEClient,
    backup_type: str,
    ontology_name: Optional[str] = None,
    chunk_size: int = 65536
) -> tuple[AsyncGenerator[bytes, None], str]:
    """
    Create and stream a backup archive.

    Args:
        client: AGEClient instance
        backup_type: "full" or "ontology"
        ontology_name: Required if backup_type is "ontology"
        chunk_size: Size of chunks to yield (default: 64KB)

    Returns:
        Tuple of (async generator yielding bytes, filename)
    """
    # Create archive in memory
    buffer, filename = create_backup_archive(client, backup_type, ontology_name)

    async def generate():
        while True:
            chunk = buffer.read(chunk_size)
            if not chunk:
                break
            yield chunk

    return generate(), filename


def get_archive_size(buffer: io.BytesIO) -> int:
    """Get size of archive buffer in bytes."""
    current_pos = buffer.tell()
    buffer.seek(0, 2)  # Seek to end
    size = buffer.tell()
    buffer.seek(current_pos)  # Restore position
    return size
