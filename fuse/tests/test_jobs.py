"""Unit tests for job visibility feature in FUSE filesystem."""

import pytest
import time
from unittest.mock import AsyncMock, MagicMock, patch

from kg_fuse.config import JobsConfig, TagsConfig
from kg_fuse.formatters import format_job
from kg_fuse.job_tracker import JobTracker, TrackedJob, TERMINAL_JOB_STATUSES, STALE_JOB_TIMEOUT
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

    def test_format_job_none_data(self):
        """Handle None job data gracefully."""
        result = format_job(None)

        assert "error" in result.lower()
        assert "no job data" in result.lower()


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
        assert "completed" in TERMINAL_JOB_STATUSES
        assert "failed" in TERMINAL_JOB_STATUSES
        assert "cancelled" in TERMINAL_JOB_STATUSES

    def test_running_not_terminal(self):
        """Running status should not be terminal."""
        assert "running" not in TERMINAL_JOB_STATUSES
        assert "queued" not in TERMINAL_JOB_STATUSES
        assert "processing" not in TERMINAL_JOB_STATUSES


class TestTrackedJob:
    """Tests for TrackedJob dataclass."""

    def test_tracked_job_creation(self):
        """TrackedJob should have all required fields."""
        job = TrackedJob(
            job_id="job_123",
            ontology="Test Ontology",
            filename="document.md",
        )
        assert job.job_id == "job_123"
        assert job.ontology == "Test Ontology"
        assert job.filename == "document.md"
        assert job.seen_complete is False
        assert job.marked_for_removal is False

    def test_tracked_job_staleness(self):
        """TrackedJob.is_stale() should detect old jobs."""
        job = TrackedJob(
            job_id="job_123",
            ontology="Test",
            filename="test.md",
            created_at=time.time() - STALE_JOB_TIMEOUT - 1,  # Over timeout
        )
        assert job.is_stale() is True

    def test_tracked_job_not_stale(self):
        """Fresh jobs should not be stale."""
        job = TrackedJob(
            job_id="job_123",
            ontology="Test",
            filename="test.md",
        )
        assert job.is_stale() is False


class TestJobTracker:
    """Tests for JobTracker class."""

    def test_track_job(self):
        """Can track a new job."""
        tracker = JobTracker()
        tracker.track_job("job_123", "Test", "doc.md")

        assert tracker.is_tracking("job_123")
        assert tracker.job_count == 1

    def test_get_jobs_for_ontology(self):
        """Can filter jobs by ontology."""
        tracker = JobTracker()
        tracker.track_job("job_1", "Ontology A", "doc1.md")
        tracker.track_job("job_2", "Ontology B", "doc2.md")
        tracker.track_job("job_3", "Ontology A", "doc3.md")

        jobs_a = tracker.get_jobs_for_ontology("Ontology A")
        assert len(jobs_a) == 2
        assert all(j.ontology == "Ontology A" for j in jobs_a)

    def test_mark_job_status_first_completion(self):
        """First completion marks seen_complete=True."""
        tracker = JobTracker()
        tracker.track_job("job_123", "Test", "doc.md")

        tracker.mark_job_status("job_123", "completed")

        job = tracker.get_job("job_123")
        assert job.seen_complete is True
        assert job.marked_for_removal is False

    def test_mark_job_status_second_completion(self):
        """Second completion marks for removal."""
        tracker = JobTracker()
        tracker.track_job("job_123", "Test", "doc.md")

        tracker.mark_job_status("job_123", "completed")  # First
        tracker.mark_job_status("job_123", "completed")  # Second

        job = tracker.get_job("job_123")
        assert job.seen_complete is True
        assert job.marked_for_removal is True

    def test_mark_job_not_found(self):
        """mark_job_not_found marks for removal."""
        tracker = JobTracker()
        tracker.track_job("job_123", "Test", "doc.md")

        tracker.mark_job_not_found("job_123")

        job = tracker.get_job("job_123")
        assert job.marked_for_removal is True

    def test_atomic_cleanup_on_get_jobs(self):
        """get_jobs_for_ontology atomically cleans up removed jobs."""
        tracker = JobTracker()
        tracker.track_job("job_1", "Test", "doc1.md")
        tracker.track_job("job_2", "Test", "doc2.md")

        # Mark job_1 for removal
        tracker.mark_job_status("job_1", "completed")
        tracker.mark_job_status("job_1", "completed")

        # Get jobs should clean up job_1
        jobs = tracker.get_jobs_for_ontology("Test")
        assert len(jobs) == 1
        assert jobs[0].job_id == "job_2"
        assert tracker.job_count == 1

    def test_stale_job_cleanup(self):
        """Stale jobs are cleaned up on get_jobs_for_ontology."""
        tracker = JobTracker()

        # Add a stale job directly
        stale_job = TrackedJob(
            job_id="stale_job",
            ontology="Test",
            filename="old.md",
            created_at=time.time() - STALE_JOB_TIMEOUT - 100,
        )
        tracker._jobs["stale_job"] = stale_job

        # Add a fresh job
        tracker.track_job("fresh_job", "Test", "new.md")

        # Get jobs should clean up stale job
        jobs = tracker.get_jobs_for_ontology("Test")
        assert len(jobs) == 1
        assert jobs[0].job_id == "fresh_job"

    def test_clear(self):
        """clear() removes all tracked jobs."""
        tracker = JobTracker()
        tracker.track_job("job_1", "Test", "doc1.md")
        tracker.track_job("job_2", "Test", "doc2.md")

        tracker.clear()

        assert tracker.job_count == 0

    def test_running_status_not_terminal(self):
        """Running status doesn't mark for removal."""
        tracker = JobTracker()
        tracker.track_job("job_123", "Test", "doc.md")

        tracker.mark_job_status("job_123", "running")

        job = tracker.get_job("job_123")
        assert job.seen_complete is False
        assert job.marked_for_removal is False


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
