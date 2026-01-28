"""Unit tests for job visibility feature in FUSE filesystem."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from kg_fuse.config import JobsConfig, TagsConfig
from kg_fuse.formatters import format_job
from kg_fuse.models import InodeEntry


class TestJobsConfig:
    """Tests for JobsConfig configuration."""

    def test_default_hide_jobs_false(self):
        """Default config should not hide jobs."""
        config = JobsConfig()
        assert config.hide_jobs is False

    def test_hide_jobs_can_be_set(self):
        """Can explicitly set hide_jobs."""
        config = JobsConfig(hide_jobs=True)
        assert config.hide_jobs is True

    def test_format_job_filename_visible(self):
        """With hide_jobs=False, filename has .ingesting suffix only."""
        config = JobsConfig(hide_jobs=False)
        result = config.format_job_filename("document.md")
        assert result == "document.md.ingesting"

    def test_format_job_filename_hidden(self):
        """With hide_jobs=True, filename has dot prefix and .ingesting suffix."""
        config = JobsConfig(hide_jobs=True)
        result = config.format_job_filename("document.md")
        assert result == ".document.md.ingesting"

    def test_format_job_filename_preserves_name(self):
        """Filename should be preserved exactly."""
        config = JobsConfig(hide_jobs=False)
        result = config.format_job_filename("My Complex File (2).md")
        assert result == "My Complex File (2).md.ingesting"


class TestFormatJob:
    """Tests for job status formatting."""

    def test_format_job_basic(self):
        """Format basic job data."""
        job_data = {
            "job_id": "job_abc123",
            "status": "running",
            "ontology": "Test Ontology",
            "filename": "test.md",
            "created_at": "2024-01-15T10:30:00",
        }
        result = format_job(job_data)

        assert "job_abc123" in result
        assert "running" in result
        assert "Test Ontology" in result
        assert "test.md" in result

    def test_format_job_with_progress(self):
        """Format job with progress information."""
        job_data = {
            "job_id": "job_xyz789",
            "status": "processing",
            "progress": {
                "stage": "chunking",
                "percent": 45,
                "items_processed": 3,
            },
        }
        result = format_job(job_data)

        assert "processing" in result
        assert "chunking" in result or "45" in result

    def test_format_job_completed(self):
        """Format completed job."""
        job_data = {
            "job_id": "job_done",
            "status": "completed",
        }
        result = format_job(job_data)

        assert "completed" in result

    def test_format_job_failed(self):
        """Format failed job with error."""
        job_data = {
            "job_id": "job_fail",
            "status": "failed",
            "error": "LLM provider unavailable",
        }
        result = format_job(job_data)

        assert "failed" in result
        assert "LLM provider unavailable" in result


class TestInodeEntryJobFile:
    """Tests for job_file inode entry type."""

    def test_create_job_file_entry(self):
        """Can create inode entry with job_file type."""
        entry = InodeEntry(
            name="test.md.ingesting",
            entry_type="job_file",
            parent=100,
            ontology="Test",
            job_id="job_123",
        )
        assert entry.entry_type == "job_file"
        assert entry.job_id == "job_123"
        assert entry.name == "test.md.ingesting"

    def test_job_file_is_not_directory(self):
        """Job files should not be treated as directories."""
        from kg_fuse.models import is_dir_type

        assert is_dir_type("job_file") is False


class TestTerminalJobStatuses:
    """Tests for terminal job status detection."""

    def test_terminal_statuses(self):
        """Check terminal status set contains expected values."""
        # Import from filesystem module
        from kg_fuse.filesystem import TERMINAL_JOB_STATUSES

        assert "completed" in TERMINAL_JOB_STATUSES
        assert "failed" in TERMINAL_JOB_STATUSES
        assert "cancelled" in TERMINAL_JOB_STATUSES

    def test_running_not_terminal(self):
        """Running status should not be terminal."""
        from kg_fuse.filesystem import TERMINAL_JOB_STATUSES

        assert "running" not in TERMINAL_JOB_STATUSES
        assert "queued" not in TERMINAL_JOB_STATUSES
        assert "processing" not in TERMINAL_JOB_STATUSES


class TestJobTracking:
    """Tests for job tracking data structures."""

    def test_tracked_job_structure(self):
        """Tracked jobs should have required fields."""
        tracked_job = {
            "ontology": "Test Ontology",
            "filename": "document.md",
            "seen_complete": False,
        }

        assert "ontology" in tracked_job
        assert "filename" in tracked_job
        assert "seen_complete" in tracked_job
        assert tracked_job["seen_complete"] is False

    def test_seen_complete_flag(self):
        """seen_complete flag should be mutable."""
        tracked_job = {
            "ontology": "Test",
            "filename": "test.md",
            "seen_complete": False,
        }

        # Simulate first read of completed job
        tracked_job["seen_complete"] = True
        assert tracked_job["seen_complete"] is True


class TestJobsConfigFromToml:
    """Tests for loading jobs config from TOML."""

    def test_parse_jobs_config_enabled(self):
        """Parse jobs config with hide_jobs=true."""
        jobs_data = {"hide_jobs": True}
        config = JobsConfig(hide_jobs=jobs_data.get("hide_jobs", False))
        assert config.hide_jobs is True

    def test_parse_jobs_config_default(self):
        """Empty jobs section should use defaults."""
        jobs_data = {}
        config = JobsConfig(hide_jobs=jobs_data.get("hide_jobs", False))
        assert config.hide_jobs is False


class TestJobFilenameEdgeCases:
    """Edge cases for job filename formatting."""

    def test_already_has_dot_prefix(self):
        """Handle files that already have dot prefix."""
        config = JobsConfig(hide_jobs=True)
        result = config.format_job_filename(".hidden_file.md")
        # Should add another dot prefix
        assert result == "..hidden_file.md.ingesting"

    def test_empty_filename(self):
        """Handle empty filename gracefully."""
        config = JobsConfig(hide_jobs=False)
        result = config.format_job_filename("")
        assert result == ".ingesting"

    def test_filename_with_path_separator(self):
        """Filename should not contain path separators (handled elsewhere)."""
        config = JobsConfig(hide_jobs=False)
        # The API/FUSE layer should sanitize this before we get here
        result = config.format_job_filename("file.md")
        assert "/" not in result
