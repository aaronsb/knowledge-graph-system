# Claude AI Chat History → Knowledge Graph

Convert your Claude AI chat exports into a searchable knowledge graph using [llmchat-knowledge-converter](https://github.com/aaronsb/llmchat-knowledge-converter).

## Overview

**Workflow:**
```
Claude AI Export (JSON)
  → llmchat-knowledge-converter
  → Markdown files
  → Knowledge Graph System
```

## Prerequisites

- Claude AI chat export (request from Account Settings → "Download Data")
- [llmchat-knowledge-converter](https://github.com/aaronsb/llmchat-knowledge-converter) installed
- Knowledge Graph System running

## Quick Start

### 1. Get Your Chat Export

1. Go to [claude.ai](https://claude.ai) → Account Settings
2. Request "Download Data" export
3. Wait for email notification (usually within minutes)
4. Download the export file(s)

### 2. Place Export Here

```bash
cd examples/use-cases/claude-ai-history
mkdir -p exports
mv ~/Downloads/claude-export-*.json exports/
```

### 3. Convert Using llmchat-knowledge-converter

```bash
# Clone converter if you haven't already
cd /path/to/tools
git clone https://github.com/aaronsb/llmchat-knowledge-converter.git
cd llmchat-knowledge-converter

# Copy export to converter's input directory
cp /path/to/knowledge-graph-system/examples/use-cases/claude-ai-history/exports/*.json input/

# Run conversion
./convert_claude_history.sh
```

This creates an Obsidian vault with your conversations organized by date.

### 4. Extract Conversations for Knowledge Graph

```bash
# Copy generated markdown files back
cd /path/to/knowledge-graph-system/examples/use-cases/claude-ai-history
mkdir -p conversations

# Copy from converter's output (adjust path to wherever the vault was created)
cp /path/to/llmchat-knowledge-converter/vault/conversations/*.md conversations/
```

### 5. Ingest into Knowledge Graph

```bash
# Ingest all conversations
kg ingest file -o "Claude AI Chats" conversations/*.md

# Or organize by date/topic
kg ingest file -o "Claude Chats - 2025-11" conversations/2025-11-*.md
```

### 6. Explore

```bash
# Search concepts
kg search query "knowledge graph"
kg search query "Python"

# View stats
kg ontology stats "Claude AI Chats"

# Web UI
open http://localhost:3000
```

## Directory Structure

```
claude-ai-history/
├── README.md              # This file
├── .gitignore            # Excludes private data
├── exports/              # Place Claude exports here (gitignored)
├── conversations/        # Converted markdown files (gitignored)
└── scripts/              # Helper scripts (optional)
```

## Tips

### Organize by Time

```bash
kg ingest file -o "Claude 2025 Q4" conversations/2025-{10,11,12}-*.md
```

### Organize by Topic

If the converter tags conversations, use those for organization:

```bash
kg ingest file -o "Development" conversations/*development*.md
kg ingest file -o "Research" conversations/*research*.md
```

### Incremental Updates

```bash
# Export again later (gets all conversations including new)
# Re-run converter
# Ingest only new files
kg ingest file -o "Claude AI Chats" conversations/2025-12-*.md
```

## Benefits

✅ **Official Export** - Uses Claude's native export feature
✅ **Structured Parsing** - Converter handles complex JSON
✅ **Rich Content** - Preserves code, formatting, structure
✅ **Dual Use** - Works with Obsidian AND knowledge graph
✅ **No Auth Hassles** - No cookies or API tokens needed

## Next Steps

Waiting for your Claude export? While you wait:

1. Set up the converter tool
2. Create the `exports/` and `conversations/` directories
3. Make sure knowledge graph is running (`kg health`)
4. Plan your ontology organization strategy

Once export arrives:
1. Place in `exports/`
2. Run converter
3. Copy conversations here
4. Ingest
5. Explore!

## Related

- [llmchat-knowledge-converter](https://github.com/aaronsb/llmchat-knowledge-converter) - Your converter tool
- [Knowledge Graph System](../../..) - This project

---

**Status**: Ready for export
**Last Updated**: November 20, 2025
