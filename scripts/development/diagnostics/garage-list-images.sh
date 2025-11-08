#!/usr/bin/env bash
# ============================================================================
# Garage List Images - Browse stored images by ontology
# ============================================================================
# List all images in Garage storage with metadata and optionally filter by
# ontology name.
#
# Usage:
#   ./scripts/diagnostics/garage-list-images.sh [ontology-name]
#
# Examples:
#   ./scripts/diagnostics/garage-list-images.sh              # List all images
#   ./scripts/diagnostics/garage-list-images.sh "Garage Test"  # Filter by ontology
# ============================================================================

set -e

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

ONTOLOGY="${1:-}"

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
if [ -n "$ONTOLOGY" ]; then
    echo -e "${BLUE}Images in Ontology: ${CYAN}${ONTOLOGY}${NC}"
else
    echo -e "${BLUE}All Images in Garage Storage${NC}"
fi
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Check if Garage is running
if ! docker ps | grep -q knowledge-graph-garage; then
    echo -e "${RED}✗ Garage container not running${NC}"
    echo ""
    echo "Start Garage:"
    echo "  ./scripts/services/start-garage.sh"
    exit 1
fi

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/../.." && pwd )"

if [ -d "$PROJECT_ROOT/venv" ]; then
    source "$PROJECT_ROOT/venv/bin/activate"
fi

python3 << EOF
try:
    from src.api.lib.garage_client import get_garage_client

    ontology = "${ONTOLOGY}" if "${ONTOLOGY}" else None
    client = get_garage_client()

    images = client.list_images(ontology=ontology)

    if not images:
        print("  No images found")
    else:
        total_size = sum(img['size'] for img in images)
        total_size_mb = total_size / (1024 * 1024)

        print(f"Found {len(images)} images (Total: {total_size_mb:.2f} MB)\n")

        # Group by ontology
        by_ontology = {}
        for img in images:
            # Extract ontology from object key (format: Ontology_Name/source_id.ext)
            ontology_name = img['object_name'].split('/')[0].replace('_', ' ')
            if ontology_name not in by_ontology:
                by_ontology[ontology_name] = []
            by_ontology[ontology_name].append(img)

        for ont, imgs in sorted(by_ontology.items()):
            ont_size = sum(i['size'] for i in imgs)
            ont_size_mb = ont_size / (1024 * 1024)

            print(f"📁 {ont}")
            print(f"   {len(imgs)} images, {ont_size_mb:.2f} MB")
            print("")

            for img in sorted(imgs, key=lambda x: x['last_modified'], reverse=True):
                size_kb = img['size'] / 1024
                modified = img['last_modified'].strftime('%Y-%m-%d %H:%M')
                source_id = img['object_name'].split('/')[-1].split('.')[0]

                print(f"   🖼️  {source_id}")
                print(f"      Path: {img['object_name']}")
                print(f"      Size: {size_kb:.1f} KB")
                print(f"      Modified: {modified}")
                print("")

except Exception as e:
    import sys
    print(f"Error: {e}", file=sys.stderr)
    sys.exit(1)
EOF

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
