# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **CHANGELOG.md** - Started maintaining a changelog to document notable changes
  - Follows [Keep a Changelog](https://keepachangelog.com) format
  - Documents implementation details for squash-merged PRs
  - Preserves granular development history
  - Links to detailed PR comments for multi-phase features

- **ADR-070: Polarity Axis Analysis for Bidirectional Semantic Dimensions** ([#153](https://github.com/aaronsb/knowledge-graph-system/pull/153))
  - New query capability to project concepts onto bidirectional semantic dimensions (polarity axes)
  - Direct query pattern (~2-3 seconds) for exploring conceptual spectrums (e.g., Modern ↔ Traditional)
  - API endpoint: `POST /query/polarity-axis` with auto-discovery of related concepts
  - CLI command: `kg polarity analyze` with colored output and JSON mode
  - MCP tool: `analyze_polarity_axis` for Claude Desktop integration
  - Web UI: Polarity Explorer workspace in Explorers category with pole selection, analysis options, and results visualization
  - Comprehensive documentation: ADR-070 updated, 700+ line usage guide created
  - Automated tests: 25+ tests for vector mathematics and API integration
  - Implementation phases:
    1. Core analysis function with vector projection mathematics (419 lines)
    2. MCP integration with token-efficient markdown formatter
    3. CLI command with formatted tables by direction
    4. Documentation: ADR updates + usage guide (POLARITY_AXIS_ANALYSIS.md)
    5. Code review fixes: Query safety (ADR-048), automated tests, cleanup
    6. Web UI workspace: Interactive pole selection, settings panel, results display with grounding correlation
  - Performance: ~2.36 seconds for 20 concepts with 768-dimensional embeddings
  - Use cases: Semantic exploration, finding synthesis concepts, validating relationships, pedagogical ordering
  - See [detailed implementation history](https://github.com/aaronsb/knowledge-graph-system/pull/153#issuecomment-3593644834) in PR comment

## [0.4.0] - 2025-11-29

### Added

- **ADR-068 Phase 5: Source Text Embeddings for Grounding Truth Retrieval** ([#152](https://github.com/aaronsb/knowledge-graph-system/pull/152))
  - Source search interfaces (CLI, MCP, Web UI)
  - Direct source passage search capabilities
  - Completes LCM foundation with embeddings for all graph elements

### Changed

- Improved ADR readability with Overview sections across all 66 ADRs

## [0.3.0] - Previous Release

_Release notes to be backfilled_

---

**Note:** This CHANGELOG was started on 2025-11-30. Previous releases (0.3.0 and earlier) can be found in [GitHub Releases](https://github.com/aaronsb/knowledge-graph-system/releases).
