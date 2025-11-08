"""
Checkpoint management for incremental document ingestion.

Tracks progress through large documents to enable resuming after interruption.
"""

import json
import hashlib
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from .datetime_utils import utcnow, to_iso

logger = logging.getLogger(__name__)


class IngestionCheckpoint:
    """Manages checkpoint state for document ingestion."""

    def __init__(self, checkpoint_dir: str = ".checkpoints"):
        """
        Initialize checkpoint manager.

        Args:
            checkpoint_dir: Directory to store checkpoint files
        """
        self.checkpoint_dir = Path(checkpoint_dir)
        self.checkpoint_dir.mkdir(exist_ok=True)

    def _get_checkpoint_path(self, document_name: str) -> Path:
        """Get path for checkpoint file based on document name."""
        safe_name = document_name.replace(" ", "_").replace("/", "_").lower()
        return self.checkpoint_dir / f"{safe_name}.json"

    def _compute_file_hash(self, filepath: str) -> str:
        """Compute SHA256 hash of file to detect changes."""
        sha256 = hashlib.sha256()
        with open(filepath, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                sha256.update(chunk)
        return sha256.hexdigest()

    def save(
        self,
        document_name: str,
        file_path: str,
        char_position: int,
        chunks_processed: int,
        recent_concept_ids: List[str],
        stats: Dict[str, int]
    ) -> None:
        """
        Save checkpoint state.

        Args:
            document_name: Name of the document being processed
            file_path: Path to source file
            char_position: Character position in file where we stopped
            chunks_processed: Number of chunks processed so far
            recent_concept_ids: List of recent concept IDs for context
            stats: Ingestion statistics dictionary
        """
        checkpoint_data = {
            "document_name": document_name,
            "file_path": file_path,
            "file_hash": self._compute_file_hash(file_path),
            "char_position": char_position,
            "chunks_processed": chunks_processed,
            "recent_concept_ids": recent_concept_ids[-50:],  # Keep last 50
            "timestamp": to_iso(utcnow()),
            "stats": stats
        }

        checkpoint_path = self._get_checkpoint_path(document_name)
        with open(checkpoint_path, 'w') as f:
            json.dump(checkpoint_data, f, indent=2)

        logger.info(f"💾 Checkpoint saved: {chunks_processed} chunks, position {char_position}")

    def load(self, document_name: str) -> Optional[Dict[str, Any]]:
        """
        Load checkpoint state if it exists.

        Args:
            document_name: Name of the document

        Returns:
            Checkpoint data dict or None if no checkpoint exists
        """
        checkpoint_path = self._get_checkpoint_path(document_name)

        if not checkpoint_path.exists():
            return None

        with open(checkpoint_path, 'r') as f:
            return json.load(f)

    def validate(self, checkpoint_data: Dict[str, Any]) -> bool:
        """
        Validate checkpoint against current file state.

        Args:
            checkpoint_data: Loaded checkpoint data

        Returns:
            True if checkpoint is valid (file unchanged), False otherwise
        """
        file_path = checkpoint_data["file_path"]

        if not Path(file_path).exists():
            logger.warning(f"⚠ Checkpoint invalid: File not found at {file_path}")
            return False

        current_hash = self._compute_file_hash(file_path)
        if current_hash != checkpoint_data["file_hash"]:
            logger.warning(f"⚠ Checkpoint invalid: File has been modified since checkpoint")
            return False

        return True

    def delete(self, document_name: str) -> None:
        """
        Delete checkpoint file.

        Args:
            document_name: Name of the document
        """
        checkpoint_path = self._get_checkpoint_path(document_name)
        if checkpoint_path.exists():
            checkpoint_path.unlink()
            logger.info(f"🗑️  Checkpoint deleted for '{document_name}'")

    def list_checkpoints(self) -> List[Dict[str, Any]]:
        """
        List all available checkpoints.

        Returns:
            List of checkpoint metadata dictionaries
        """
        checkpoints = []

        for checkpoint_file in self.checkpoint_dir.glob("*.json"):
            with open(checkpoint_file, 'r') as f:
                data = json.load(f)
                checkpoints.append({
                    "document_name": data["document_name"],
                    "chunks_processed": data["chunks_processed"],
                    "timestamp": data["timestamp"],
                    "file_path": data["file_path"]
                })

        return sorted(checkpoints, key=lambda x: x["timestamp"], reverse=True)
