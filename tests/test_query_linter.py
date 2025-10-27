"""
Unit tests for query safety linter.

Tests the query linter's ability to detect unsafe Cypher patterns
that could cause namespace collisions (ADR-048).
"""

import pytest
from pathlib import Path
from scripts.lint_queries import QueryLinter, UnsafeQuery


class TestQueryLinter:
    """Test QueryLinter class."""

    @pytest.fixture
    def linter(self):
        """Provide QueryLinter instance."""
        return QueryLinter(verbose=False)

    # =========================================================================
    # Unsafe Pattern Detection
    # =========================================================================

    def test_detect_unsafe_match(self, linter, tmp_path):
        """Test detection of MATCH without explicit label."""
        test_file = tmp_path / "test.py"
        test_file.write_text(
            'client._execute_cypher("MATCH (n) RETURN n")'
        )

        findings = linter.lint_file(test_file)

        assert len(findings) == 1
        assert findings[0].severity == 'error'
        assert 'MATCH (n)' in findings[0].issue
        assert 'explicit label' in findings[0].issue

    def test_detect_unsafe_create(self, linter, tmp_path):
        """Test detection of CREATE without explicit label."""
        test_file = tmp_path / "test.py"
        test_file.write_text(
            'client._execute_cypher("CREATE (n) SET n.prop = \'value\'")'
        )

        findings = linter.lint_file(test_file)

        assert len(findings) == 1
        assert findings[0].severity == 'error'
        assert 'CREATE (n)' in findings[0].issue

    def test_detect_unsafe_merge(self, linter, tmp_path):
        """Test detection of MERGE without explicit label."""
        test_file = tmp_path / "test.py"
        test_file.write_text(
            'client._execute_cypher("MERGE (n) SET n.prop = \'value\'")'
        )

        findings = linter.lint_file(test_file)

        assert len(findings) == 1
        assert findings[0].severity == 'error'
        assert 'MERGE (n)' in findings[0].issue

    def test_detect_multiple_unsafe_patterns(self, linter, tmp_path):
        """Test detection of multiple unsafe patterns in one file."""
        test_file = tmp_path / "test.py"
        test_file.write_text("""
def unsafe_operations():
    client._execute_cypher("MATCH (n) RETURN n")
    client._execute_cypher("CREATE (m) SET m.prop = 'value'")
    client._execute_cypher("MERGE (x) SET x.prop = 'value'")
""")

        findings = linter.lint_file(test_file)

        assert len(findings) == 3
        assert all(f.severity == 'error' for f in findings)

    # =========================================================================
    # Safe Pattern Acceptance
    # =========================================================================

    def test_accept_safe_match_with_label(self, linter, tmp_path):
        """Test that MATCH with explicit label is safe."""
        test_file = tmp_path / "test.py"
        test_file.write_text(
            'client._execute_cypher("MATCH (n:Concept) RETURN n")'
        )

        findings = linter.lint_file(test_file)

        assert len(findings) == 0

    def test_accept_safe_create_with_label(self, linter, tmp_path):
        """Test that CREATE with explicit label is safe."""
        test_file = tmp_path / "test.py"
        test_file.write_text(
            'client._execute_cypher("CREATE (n:Concept) SET n.prop = \'value\'")'
        )

        findings = linter.lint_file(test_file)

        assert len(findings) == 0

    def test_accept_safe_merge_with_label(self, linter, tmp_path):
        """Test that MERGE with explicit label is safe."""
        test_file = tmp_path / "test.py"
        test_file.write_text(
            'client._execute_cypher("MERGE (n:VocabType) SET n.prop = \'value\'")'
        )

        findings = linter.lint_file(test_file)

        assert len(findings) == 0

    def test_accept_relationship_patterns(self, linter, tmp_path):
        """Test that relationship patterns with labels are safe."""
        test_file = tmp_path / "test.py"
        test_file.write_text(
            'client._execute_cypher("MATCH (c1:Concept)-[r:IMPLIES]->(c2:Concept) RETURN r")'
        )

        findings = linter.lint_file(test_file)

        assert len(findings) == 0

    # =========================================================================
    # Whitelist Patterns
    # =========================================================================

    def test_whitelist_match_by_id(self, linter, tmp_path):
        """Test that MATCH by ID is whitelisted."""
        test_file = tmp_path / "test.py"
        test_file.write_text(
            'client._execute_cypher("MATCH (n) WHERE id(n) = $id RETURN n", params={"id": 123})'
        )

        findings = linter.lint_file(test_file)

        assert len(findings) == 0

    def test_whitelist_match_by_property(self, linter, tmp_path):
        """Test that MATCH by property is whitelisted."""
        test_file = tmp_path / "test.py"
        test_file.write_text(
            'client._execute_cypher("MATCH (n) WHERE n.concept_id = $cid RETURN n")'
        )

        findings = linter.lint_file(test_file)

        assert len(findings) == 0

    # =========================================================================
    # Query Snippet Extraction
    # =========================================================================

    def test_query_snippet_extraction(self, linter, tmp_path):
        """Test that query snippets are extracted correctly."""
        test_file = tmp_path / "test.py"
        test_file.write_text(
            'client._execute_cypher("MATCH (n) WHERE n.long_property_name = \'value\' AND n.other = \'test\' RETURN n")'
        )

        findings = linter.lint_file(test_file)

        assert len(findings) == 1
        assert 'MATCH (n)' in findings[0].query_snippet
        # Snippet should be truncated for readability
        assert len(findings[0].query_snippet) < 200

    # =========================================================================
    # Line Number Tracking
    # =========================================================================

    def test_line_number_tracking(self, linter, tmp_path):
        """Test that line numbers are tracked correctly."""
        test_file = tmp_path / "test.py"
        test_file.write_text("""# Line 1
# Line 2
def foo():  # Line 3
    # Line 4
    client._execute_cypher("MATCH (n) RETURN n")  # Line 5
""")

        findings = linter.lint_file(test_file)

        assert len(findings) == 1
        assert findings[0].line_number == 5

    # =========================================================================
    # Directory Scanning
    # =========================================================================

    def test_lint_directory(self, linter, tmp_path):
        """Test linting entire directory."""
        # Create test files
        (tmp_path / "file1.py").write_text(
            'client._execute_cypher("MATCH (n) RETURN n")'
        )
        (tmp_path / "file2.py").write_text(
            'client._execute_cypher("MATCH (n:Concept) RETURN n")'
        )
        (tmp_path / "file3.py").write_text(
            'client._execute_cypher("CREATE (n) SET n.prop = \'value\'")'
        )

        findings = linter.lint_directory(tmp_path)

        # Should find 2 unsafe queries (file1 and file3)
        assert len(findings) == 2

    # =========================================================================
    # Report Formatting
    # =========================================================================

    def test_print_report_no_findings(self, linter, capsys):
        """Test report with no findings."""
        linter.print_report([])

        captured = capsys.readouterr()
        assert "✓ No unsafe queries found!" in captured.out

    def test_print_report_with_findings(self, linter, tmp_path, capsys):
        """Test report with findings."""
        findings = [
            UnsafeQuery(
                file_path=str(tmp_path / "test.py"),
                line_number=5,
                query_snippet="MATCH (n) RETURN n",
                issue="MATCH (n) missing explicit label",
                severity="error"
            )
        ]

        linter.print_report(findings)

        captured = capsys.readouterr()
        assert "Found 1 unsafe query pattern" in captured.out
        assert "test.py" in captured.out
        assert "Line 5" in captured.out
        assert "ADR-048" in captured.out


class TestQueryLinterIntegration:
    """Integration tests for query linter."""

    def test_baseline_audit_on_real_codebase(self):
        """
        Test baseline audit on actual codebase.

        This test documents the current technical debt.
        """
        linter = QueryLinter(verbose=False)
        findings = linter.lint_directory(Path("src/api"))

        # As of Phase 1 implementation, we have 3 known unsafe queries
        # (documented in QUERY_SAFETY_BASELINE.md)
        assert len(findings) >= 3

        # Check expected files are flagged
        file_paths = [f.file_path for f in findings]
        assert any("database.py" in path for path in file_paths)
        assert any("restore_worker.py" in path for path in file_paths)

    @pytest.mark.parametrize("safe_pattern", [
        "MATCH (c:Concept) RETURN c",
        "MATCH (v:VocabType) WHERE v.is_active = true RETURN v",
        "CREATE (c:Concept {label: $label}) RETURN c",
        "MERGE (c:Concept {concept_id: $id}) RETURN c",
        "MATCH (c1:Concept)-[r:IMPLIES]->(c2:Concept) RETURN r",
    ])
    def test_safe_patterns(self, safe_pattern, tmp_path):
        """Test various safe query patterns."""
        linter = QueryLinter(verbose=False)
        test_file = tmp_path / "test.py"
        test_file.write_text(f'client._execute_cypher("{safe_pattern}")')

        findings = linter.lint_file(test_file)

        assert len(findings) == 0, f"Safe pattern flagged as unsafe: {safe_pattern}"

    @pytest.mark.parametrize("unsafe_pattern,expected_issue", [
        ("MATCH (n) RETURN n", "MATCH (n) missing explicit label"),
        ("CREATE (n) RETURN n", "CREATE (n) missing explicit label"),
        ("MERGE (n) RETURN n", "MERGE (n) missing explicit label"),
    ])
    def test_unsafe_patterns(self, unsafe_pattern, expected_issue, tmp_path):
        """Test various unsafe query patterns."""
        linter = QueryLinter(verbose=False)
        test_file = tmp_path / "test.py"
        test_file.write_text(f'client._execute_cypher("{unsafe_pattern}")')

        findings = linter.lint_file(test_file)

        assert len(findings) == 1
        assert expected_issue in findings[0].issue
