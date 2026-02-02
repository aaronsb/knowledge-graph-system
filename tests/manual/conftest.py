"""
Configuration for manual test directory.

Tests in this directory are designed to be run manually inside the API container,
not as part of the automated pytest suite. They may have required parameters
(like file paths) that aren't pytest fixtures.

Use: pytest --collect-only tests/manual/ to see what's available.
Run explicitly: pytest tests/manual/test_preprocessing.py::test_embedded_sample
"""

collect_ignore_glob = ["test_*.py"]
