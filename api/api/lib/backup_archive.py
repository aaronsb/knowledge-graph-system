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

        # Fetch and add Garage documents (deduplicated by key)
        source_storage = get_source_storage()
        image_storage = get_image_storage()

        docs_added = 0
        docs_failed = 0
        added_keys: set = set()  # Track which keys we've already added

        for source in backup_data["data"]["sources"]:
            # Add source document from Garage (skip if already added)
            garage_key = source.get("garage_key")
            if garage_key and garage_key not in added_keys:
                try:
                    content = source_storage.get(garage_key)
                    if content:
                        doc_path = f"{archive_base}/documents/{garage_key}"
                        doc_info = tarfile.TarInfo(name=doc_path)
                        doc_info.size = len(content)
                        tar.addfile(doc_info, io.BytesIO(content))
                        added_keys.add(garage_key)
                        docs_added += 1
                    else:
                        logger.warning(f"Document not found in Garage: {garage_key}")
                        docs_failed += 1
                except Exception as e:
                    logger.warning(f"Failed to fetch {garage_key}: {e}")
                    docs_failed += 1

            # Add image from Garage (if content_type is image, skip if already added)
            storage_key = source.get("storage_key")
            if storage_key and source.get("content_type") == "image" and storage_key not in added_keys:
                try:
                    content = image_storage.base.get_object(storage_key)
                    if content:
                        img_path = f"{archive_base}/documents/{storage_key}"
                        img_info = tarfile.TarInfo(name=img_path)
                        img_info.size = len(content)
                        tar.addfile(img_info, io.BytesIO(content))
                        added_keys.add(storage_key)
                        docs_added += 1
                except Exception as e:
                    logger.warning(f"Failed to fetch image {storage_key}: {e}")
                    docs_failed += 1

        logger.info(f"Added {docs_added} unique documents to archive ({docs_failed} failed)")

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


def extract_backup_archive(archive_path: str) -> tuple[str, str]:
    """
    Extract a backup archive to a temp directory.

    Args:
        archive_path: Path to .tar.gz archive file

    Returns:
        Tuple of (temp_dir, manifest_path)

    Raises:
        ValueError: If archive is invalid or missing manifest.json
    """
    import tempfile
    from pathlib import Path

    # Create temp directory for extraction
    temp_dir = tempfile.mkdtemp(prefix="kg_restore_")

    try:
        with tarfile.open(archive_path, 'r:gz') as tar:
            # Security: Check for path traversal attacks
            for member in tar.getmembers():
                if member.name.startswith('/') or '..' in member.name:
                    raise ValueError(f"Invalid archive: suspicious path {member.name}")

            # Extract all files
            tar.extractall(temp_dir)

        # Find manifest.json
        temp_path = Path(temp_dir)
        manifest_files = list(temp_path.glob("*/manifest.json"))

        if not manifest_files:
            raise ValueError("Invalid archive: missing manifest.json")

        manifest_path = str(manifest_files[0])
        logger.info(f"Extracted archive to {temp_dir}, manifest at {manifest_path}")

        return temp_dir, manifest_path

    except Exception as e:
        # Cleanup on error
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise


def restore_documents_to_garage(
    temp_dir: str,
    manifest_data: Dict[str, Any],
    overwrite: bool = False
) -> Dict[str, int]:
    """
    Upload documents from extracted archive to Garage.

    Args:
        temp_dir: Path to extracted archive directory
        manifest_data: Parsed manifest.json data
        overwrite: Whether to overwrite existing documents in Garage

    Returns:
        Dict with upload statistics: {uploaded, skipped, failed}
    """
    from pathlib import Path

    source_storage = get_source_storage()
    image_storage = get_image_storage()

    stats = {"uploaded": 0, "skipped": 0, "failed": 0}
    processed_keys: set = set()  # Track which keys we've processed

    sources = manifest_data.get("data", {}).get("sources", [])

    for source in sources:
        # Handle source documents
        garage_key = source.get("garage_key")
        document_path = source.get("document_path")

        if garage_key and document_path and garage_key not in processed_keys:
            processed_keys.add(garage_key)

            # Find the file in the extracted archive
            # document_path is relative to archive root: "backup_name/documents/sources/..."
            # temp_dir contains the extracted archive with the backup_name directory
            file_path = Path(temp_dir) / document_path
            logger.info(f"Looking for document: temp_dir={temp_dir}, document_path={document_path}")
            logger.info(f"Trying path: {file_path} (exists: {file_path.exists()})")

            if not file_path.exists():
                # Try without the archive base prefix (if document_path has it)
                parts = document_path.split("/", 1)
                if len(parts) > 1:
                    file_path = Path(temp_dir) / parts[0] / parts[1]
                    logger.info(f"Fallback path: {file_path} (exists: {file_path.exists()})")

            if not file_path.exists():
                logger.warning(f"Document not found in archive: {document_path}")
                stats["failed"] += 1
                continue

            try:
                # Check if already exists in Garage
                if not overwrite:
                    existing = source_storage.get(garage_key)
                    if existing:
                        logger.debug(f"Skipping existing document: {garage_key}")
                        stats["skipped"] += 1
                        continue

                # Upload to Garage using base client (restore bypasses normal store flow)
                with open(file_path, 'rb') as f:
                    content = f.read()

                # Determine content type from extension
                ext = garage_key.rsplit('.', 1)[-1].lower() if '.' in garage_key else 'txt'
                content_type = 'text/plain'
                if ext in ('md', 'markdown'):
                    content_type = 'text/markdown'
                elif ext == 'json':
                    content_type = 'application/json'
                elif ext == 'html':
                    content_type = 'text/html'

                source_storage.base.put_object(garage_key, content, content_type)
                stats["uploaded"] += 1
                logger.debug(f"Uploaded document: {garage_key}")

            except Exception as e:
                logger.warning(f"Failed to upload {garage_key}: {e}")
                stats["failed"] += 1

        # Handle images
        storage_key = source.get("storage_key")
        image_path = source.get("image_path")

        if storage_key and image_path and storage_key not in processed_keys:
            processed_keys.add(storage_key)

            file_path = Path(temp_dir) / image_path

            if not file_path.exists():
                parts = image_path.split("/", 1)
                if len(parts) > 1:
                    file_path = Path(temp_dir) / parts[0] / parts[1]

            if not file_path.exists():
                logger.warning(f"Image not found in archive: {image_path} (tried {file_path})")
                stats["failed"] += 1
                continue

            try:
                if not overwrite:
                    try:
                        existing = image_storage.base.get_object(storage_key)
                        if existing:
                            stats["skipped"] += 1
                            continue
                    except Exception:
                        pass  # Key doesn't exist, proceed with upload

                with open(file_path, 'rb') as f:
                    content = f.read()

                image_storage.base.put_object(storage_key, content)
                stats["uploaded"] += 1

            except Exception as e:
                logger.warning(f"Failed to upload image {storage_key}: {e}")
                stats["failed"] += 1

    logger.info(
        f"Document restore complete: {stats['uploaded']} uploaded, "
        f"{stats['skipped']} skipped, {stats['failed']} failed"
    )

    return stats


def cleanup_extracted_archive(temp_dir: str) -> None:
    """Clean up extracted archive directory."""
    import shutil
    try:
        shutil.rmtree(temp_dir, ignore_errors=True)
        logger.debug(f"Cleaned up temp directory: {temp_dir}")
    except Exception as e:
        logger.warning(f"Failed to cleanup temp directory {temp_dir}: {e}")
