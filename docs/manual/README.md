# Knowledge Graph System Manual

This directory contains the complete manual for the Knowledge Graph System.

## Structure

Documentation is organized into numbered directories that follow a natural reading order:

1. **01-getting-started/** - Quick start, CLI usage, ingestion basics
2. **02-configuration/** - AI providers, extraction, embeddings
3. **03-integration/** - MCP setup, vocabulary management
4. **04-security-and-access/** - Authentication, RBAC, security
5. **05-maintenance/** - Backup/restore, database migrations
6. **06-reference/** - Schema, concepts, examples, query patterns

Within each directory, files are numbered to indicate reading order.

## Conventions

### Media Files

Media files (images, diagrams, etc.) for any document are stored in a `/media` subdirectory relative to the markdown file that uses them.

**Example:**
```
02-configuration/
  01-AI_PROVIDERS.md
  media/
    provider-diagram.png
    config-flow.svg
```

Referenced in markdown as:
```markdown
![Provider Diagram](media/provider-diagram.png)
```
