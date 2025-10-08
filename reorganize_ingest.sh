#!/bin/bash
# Reorganize POC code to API-first structure

set -e

echo "🔧 Reorganizing src/ingest/ to src/api/lib/..."

# Create target directory
mkdir -p src/api/lib

# Move library files (keep .py extension)
mv src/ingest/ai_providers.py src/api/lib/
mv src/ingest/checkpoint.py src/api/lib/
mv src/ingest/chunker.py src/api/lib/
mv src/ingest/llm_extractor.py src/api/lib/
mv src/ingest/neo4j_client.py src/api/lib/
mv src/ingest/parser.py src/api/lib/

# Create __init__.py for the lib package
cat > src/api/lib/__init__.py << 'EOF'
"""
Shared library code for API ingestion pipeline.

Extracted from POC code, now maintained as API library.
"""
EOF

echo "✅ Files moved to src/api/lib/"
echo "📝 Next: Extract ChunkedIngestionStats and process_chunk to src/api/lib/ingestion.py"

