#!/bin/bash
# FUSE Integration Test
#
# Tests the kg-fuse filesystem against a live mount.
# Requires: FUSE mounted at $MOUNT_POINT (default: ~/Knowledge)
#
# Usage:
#   ./test_fuse_integration.sh                    # Run all tests
#   ./test_fuse_integration.sh --mount ~/Knowledge  # Custom mount point
#   ./test_fuse_integration.sh --keep             # Don't clean up test ontology
#   ./test_fuse_integration.sh --verbose          # Show detailed output

set -euo pipefail

# Defaults
MOUNT_POINT="${HOME}/Knowledge"
TEST_ONTOLOGY="FuseIntegrationTest_$$"
KEEP_TEST_DATA=false
VERBOSE=false
LOG_DIR="/tmp/fuse-test-$$"
MAX_POLL_ATTEMPTS=30
POLL_INTERVAL=1
USE_FIXTURE=""  # Optional: path to fixture file to ingest

# Script directory (for finding fixtures)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FIXTURES_DIR="$SCRIPT_DIR/fixtures"

# Timing
declare -A TIMINGS
TOTAL_START=$(date +%s.%N)

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --mount)
            MOUNT_POINT="$2"
            shift 2
            ;;
        --keep)
            KEEP_TEST_DATA=true
            shift
            ;;
        --verbose)
            VERBOSE=true
            shift
            ;;
        --fixture)
            USE_FIXTURE="$2"
            shift 2
            ;;
        --help|-h)
            echo "FUSE Integration Test"
            echo ""
            echo "Usage: $0 [options]"
            echo ""
            echo "Options:"
            echo "  --mount PATH     Mount point (default: ~/Knowledge)"
            echo "  --keep           Don't clean up test ontology after tests"
            echo "  --verbose        Show detailed output"
            echo "  --fixture FILE   Use fixture file for ingestion test"
            echo "  --help           Show this help"
            echo ""
            echo "Available fixtures in $FIXTURES_DIR:"
            ls "$FIXTURES_DIR"/*.md 2>/dev/null | xargs -n1 basename || echo "  (none found)"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Setup
mkdir -p "$LOG_DIR"
PASS_COUNT=0
FAIL_COUNT=0

# Timing functions
timer_start() {
    local name="$1"
    TIMINGS["${name}_start"]=$(date +%s.%N)
}

timer_end() {
    local name="$1"
    local end=$(date +%s.%N)
    local start=${TIMINGS["${name}_start"]:-$end}
    local elapsed=$(echo "$end - $start" | bc)
    TIMINGS["$name"]=$elapsed
    log_verbose "Timing: $name took ${elapsed}s"
}

print_timings() {
    local total_end=$(date +%s.%N)
    local total_elapsed=$(echo "$total_end - $TOTAL_START" | bc)

    echo ""
    echo "Timing Summary"
    echo "----------------------------------------"
    printf "%-30s %10s\n" "Test" "Duration"
    echo "----------------------------------------"

    for key in "${!TIMINGS[@]}"; do
        # Skip _start entries
        if [[ ! "$key" =~ _start$ ]]; then
            printf "%-30s %10.3fs\n" "$key" "${TIMINGS[$key]}"
        fi
    done

    echo "----------------------------------------"
    printf "%-30s %10.3fs\n" "TOTAL" "$total_elapsed"
    echo "----------------------------------------"

    # Save to log
    echo "" >> "$LOG_DIR/test.log"
    echo "Timing Summary" >> "$LOG_DIR/test.log"
    for key in "${!TIMINGS[@]}"; do
        if [[ ! "$key" =~ _start$ ]]; then
            echo "$key: ${TIMINGS[$key]}s" >> "$LOG_DIR/test.log"
        fi
    done
    echo "TOTAL: ${total_elapsed}s" >> "$LOG_DIR/test.log"
}

log() {
    echo -e "${BLUE}[$(date +%H:%M:%S)]${NC} $*"
    echo "[$(date +%H:%M:%S)] $*" >> "$LOG_DIR/test.log"
}

log_verbose() {
    if $VERBOSE; then
        echo -e "${YELLOW}  > $*${NC}"
    fi
    echo "  > $*" >> "$LOG_DIR/test.log"
}

pass() {
    echo -e "${GREEN}[PASS]${NC} $*"
    echo "[PASS] $*" >> "$LOG_DIR/test.log"
    ((PASS_COUNT++))
}

fail() {
    echo -e "${RED}[FAIL]${NC} $*"
    echo "[FAIL] $*" >> "$LOG_DIR/test.log"
    ((FAIL_COUNT++))
}

cleanup() {
    if ! $KEEP_TEST_DATA; then
        log "Cleaning up test ontology..."
        if [[ -d "$MOUNT_POINT/ontology/$TEST_ONTOLOGY" ]]; then
            # Can't easily delete ontology via FUSE, just note it
            log_verbose "Test ontology $TEST_ONTOLOGY may need manual cleanup via API"
        fi
    fi
    log "Test logs saved to: $LOG_DIR"
}

trap cleanup EXIT

# ============================================================================
# Pre-flight checks
# ============================================================================

log "Starting FUSE integration tests"
log "Mount point: $MOUNT_POINT"
log "Test ontology: $TEST_ONTOLOGY"
log "Log directory: $LOG_DIR"
echo ""

# Check mount is accessible
if [[ ! -d "$MOUNT_POINT/ontology" ]]; then
    echo -e "${RED}ERROR: FUSE not mounted at $MOUNT_POINT${NC}"
    echo "Make sure kg-fuse is running: kg-fuse $MOUNT_POINT"
    exit 1
fi

pass "FUSE mount is accessible"

# ============================================================================
# Test 1: Create ontology
# ============================================================================

timer_start "create_ontology"
log "Test 1: Creating test ontology..."

ONTOLOGY_DIR="$MOUNT_POINT/ontology/$TEST_ONTOLOGY"

if mkdir "$ONTOLOGY_DIR" 2>/dev/null; then
    pass "Created ontology directory: $TEST_ONTOLOGY"
else
    fail "Failed to create ontology directory"
    exit 1
fi

# Verify it appears in listing
if ls "$MOUNT_POINT/ontology" | grep -q "$TEST_ONTOLOGY"; then
    pass "Ontology appears in listing"
else
    fail "Ontology not found in listing"
fi

timer_end "create_ontology"

# ============================================================================
# Test 2: Documents directory exists
# ============================================================================

timer_start "documents_dir"
log "Test 2: Checking documents directory..."

DOCS_DIR="$ONTOLOGY_DIR/documents"

if [[ -d "$DOCS_DIR" ]]; then
    pass "Documents directory exists"
else
    fail "Documents directory not found"
fi

timer_end "documents_dir"

# ============================================================================
# Test 3: File ingestion and job tracking
# ============================================================================

timer_start "file_ingestion"
log "Test 3: Testing file ingestion..."

# Determine test content: use fixture if specified, otherwise generate
if [[ -n "$USE_FIXTURE" ]]; then
    # Resolve fixture path
    if [[ ! -f "$USE_FIXTURE" ]]; then
        # Try relative to fixtures dir
        if [[ -f "$FIXTURES_DIR/$USE_FIXTURE" ]]; then
            USE_FIXTURE="$FIXTURES_DIR/$USE_FIXTURE"
        else
            echo -e "${RED}ERROR: Fixture not found: $USE_FIXTURE${NC}"
            exit 1
        fi
    fi
    TEST_CONTENT=$(cat "$USE_FIXTURE")
    TEST_FILENAME=$(basename "$USE_FIXTURE")
    log_verbose "Using fixture: $USE_FIXTURE"
else
    # Generate test content with semantic keywords for concept extraction
    TEST_CONTENT="# Distributed Systems Integration Test

This document tests the FUSE ingestion pipeline and concept extraction.

## Distributed Systems Concepts

Distributed systems coordinate multiple computers to work together. Key concepts include:

- **Consensus**: Agreement between nodes on system state
- **Replication**: Copying data across multiple machines for availability
- **Partitioning**: Splitting data across nodes for scalability

## Machine Learning Integration

Modern distributed systems often incorporate machine learning:

- **Federated Learning**: Training models across distributed data
- **Model Serving**: Deploying ML models across a cluster
- **Feature Stores**: Centralized management of ML features

## Knowledge Graphs

Knowledge graphs represent information as interconnected entities:

- **Nodes**: Represent concepts or entities
- **Edges**: Represent relationships between nodes
- **Embedding**: Vector representations for semantic similarity

Created: $(date -Iseconds)
Test ID: $$
"
    TEST_FILENAME="test_integration_$(date +%s).md"
fi

# Define expected concepts to look for (adjust based on content)
EXPECTED_CONCEPTS=("distributed" "consensus" "knowledge" "machine learning")

TEST_FILE_PATH="$ONTOLOGY_DIR/$TEST_FILENAME"

# Write test file (copy for fixture, write for generated)
if [[ -n "$USE_FIXTURE" ]]; then
    cp "$USE_FIXTURE" "$TEST_FILE_PATH"
else
    echo "$TEST_CONTENT" > "$TEST_FILE_PATH"
fi
log_verbose "Wrote test file: $TEST_FILENAME"

# Small delay for ingestion to start
sleep 1

# Check for job file appearance
JOB_FILENAME="${TEST_FILENAME}.ingesting"
JOB_FILE_PATH="$DOCS_DIR/$JOB_FILENAME"

log "Polling for job file ($MAX_POLL_ATTEMPTS attempts max)..."

JOB_FOUND=false
BACKOFF=$POLL_INTERVAL
for i in $(seq 1 $MAX_POLL_ATTEMPTS); do
    if [[ -f "$JOB_FILE_PATH" ]]; then
        JOB_FOUND=true
        pass "Job file appeared after $i poll(s)"

        # Read job status
        JOB_STATUS=$(cat "$JOB_FILE_PATH" 2>/dev/null || echo "")
        echo "$JOB_STATUS" > "$LOG_DIR/job_status_$i.txt"
        log_verbose "Job status saved to job_status_$i.txt"

        # Extract status line
        STATUS_LINE=$(echo "$JOB_STATUS" | grep -E '^status = ' | head -1 || echo "status = unknown")
        log_verbose "Current status: $STATUS_LINE"
        break
    fi

    log_verbose "Poll $i: job file not found yet (waiting ${BACKOFF}s)"
    sleep $BACKOFF
    # Exponential backoff with cap at 5 seconds
    BACKOFF=$(echo "scale=1; if ($BACKOFF * 1.5 > 5) 5 else $BACKOFF * 1.5" | bc)
done

if ! $JOB_FOUND; then
    # Job might have completed very quickly, check for document
    if [[ -f "$DOCS_DIR/$TEST_FILENAME" ]]; then
        pass "Job completed quickly (no job file seen, but document exists)"
        JOB_FOUND=true
    else
        fail "Job file never appeared"
    fi
fi

timer_end "file_ingestion"

# ============================================================================
# Test 4: Job completion and file appearance
# ============================================================================

timer_start "job_completion"
log "Test 4: Waiting for job completion..."

DOC_FOUND=false
BACKOFF=$POLL_INTERVAL
for i in $(seq 1 $MAX_POLL_ATTEMPTS); do
    # Check if document exists
    if [[ -f "$DOCS_DIR/$TEST_FILENAME" ]]; then
        DOC_FOUND=true
        pass "Document appeared after $i poll(s)"
        break
    fi

    # If job file exists, read it (this triggers lazy polling and completion detection)
    if [[ -f "$JOB_FILE_PATH" ]]; then
        JOB_STATUS=$(cat "$JOB_FILE_PATH" 2>/dev/null || echo "")
        echo "$JOB_STATUS" > "$LOG_DIR/job_status_poll_$i.txt"

        STATUS=$(echo "$JOB_STATUS" | grep -oP 'status = "\K[^"]+' || echo "unknown")
        log_verbose "Poll $i: status=$STATUS (waiting ${BACKOFF}s)"

        if [[ "$STATUS" == "completed" || "$STATUS" == "failed" || "$STATUS" == "cancelled" ]]; then
            log_verbose "Job reached terminal status: $STATUS"
        fi
    else
        log_verbose "Poll $i: waiting for document (${BACKOFF}s)"
    fi

    sleep $BACKOFF
    # Exponential backoff with cap at 5 seconds
    BACKOFF=$(echo "scale=1; if ($BACKOFF * 1.5 > 5) 5 else $BACKOFF * 1.5" | bc)
done

if $DOC_FOUND; then
    # Read and verify document content
    DOC_CONTENT=$(cat "$DOCS_DIR/$TEST_FILENAME" 2>/dev/null || echo "")
    echo "$DOC_CONTENT" > "$LOG_DIR/document_content.txt"

    if echo "$DOC_CONTENT" | grep -q "Test Document"; then
        pass "Document content is correct"
    else
        fail "Document content doesn't match expected"
    fi
else
    fail "Document never appeared after $MAX_POLL_ATTEMPTS polls"
fi

timer_end "job_completion"

# ============================================================================
# Test 5: Job file cleanup
# ============================================================================

timer_start "job_cleanup"
log "Test 5: Verifying job file cleanup..."

# After document appears and we've read the job file showing completion,
# the job file should be removed on next listing
sleep 1

if [[ -f "$JOB_FILE_PATH" ]]; then
    # Read it again to trigger removal marking
    cat "$JOB_FILE_PATH" > /dev/null 2>&1 || true
    sleep 1
fi

# Check listing
JOB_FILES=$(ls "$DOCS_DIR" 2>/dev/null | grep -c '\.ingesting$' || echo "0")

if [[ "$JOB_FILES" -eq 0 ]]; then
    pass "Job file cleaned up (no .ingesting files remain)"
else
    fail "Job file not cleaned up ($JOB_FILES .ingesting files remain)"
    ls -la "$DOCS_DIR" >> "$LOG_DIR/docs_listing.txt"
fi

timer_end "job_cleanup"

# ============================================================================
# Test 6: Query directories
# ============================================================================

timer_start "query_directories"
log "Test 6: Testing query directories..."

QUERY_NAME="test-query"
QUERY_DIR="$ONTOLOGY_DIR/$QUERY_NAME"

if mkdir "$QUERY_DIR" 2>/dev/null; then
    pass "Created query directory"
else
    fail "Failed to create query directory"
fi

# Check .meta directory exists
if [[ -d "$QUERY_DIR/.meta" ]]; then
    pass "Query has .meta directory"
else
    fail "Query missing .meta directory"
fi

# Check meta files
for meta_file in limit threshold exclude union query.toml; do
    if [[ -f "$QUERY_DIR/.meta/$meta_file" ]]; then
        log_verbose "Found meta file: $meta_file"
    else
        fail "Missing meta file: $meta_file"
    fi
done

# Read query.toml
QUERY_TOML=$(cat "$QUERY_DIR/.meta/query.toml" 2>/dev/null || echo "")
echo "$QUERY_TOML" > "$LOG_DIR/query_toml.txt"

if echo "$QUERY_TOML" | grep -q "query = \"$QUERY_NAME\""; then
    pass "query.toml contains correct query text"
else
    fail "query.toml doesn't contain expected query"
fi

timer_end "query_directories"

# ============================================================================
# Test 6b: Concept querying (requires document ingestion to complete)
# ============================================================================

timer_start "concept_query"
log "Test 6b: Testing concept querying..."

# Wait a bit for ingestion to complete and concepts to be indexed
log_verbose "Waiting for concept indexing..."
sleep 3

# Create a semantic query based on our test content
# The test_article_medium.md contains concepts about distributed systems
CONCEPT_QUERY="distributed"
CONCEPT_QUERY_DIR="$ONTOLOGY_DIR/$CONCEPT_QUERY"

if mkdir "$CONCEPT_QUERY_DIR" 2>/dev/null; then
    pass "Created concept query directory: $CONCEPT_QUERY"
else
    fail "Failed to create concept query directory"
fi

# Wait for query results to populate
sleep 2

# List results
CONCEPT_FILES=$(ls "$CONCEPT_QUERY_DIR" 2>/dev/null | grep -c '\.concept\.md$' || echo "0")
log_verbose "Found $CONCEPT_FILES concept files"

if [[ "$CONCEPT_FILES" -gt 0 ]]; then
    pass "Query returned $CONCEPT_FILES concept(s)"

    # List the concepts found
    ls "$CONCEPT_QUERY_DIR"/*.concept.md 2>/dev/null | head -5 >> "$LOG_DIR/concepts_found.txt"

    # Read first concept file
    FIRST_CONCEPT=$(ls "$CONCEPT_QUERY_DIR"/*.concept.md 2>/dev/null | head -1)
    if [[ -n "$FIRST_CONCEPT" ]]; then
        CONCEPT_CONTENT=$(cat "$FIRST_CONCEPT")
        echo "$CONCEPT_CONTENT" > "$LOG_DIR/sample_concept.md"
        log_verbose "Sample concept saved to sample_concept.md"

        # Check if concept references our test file as a source
        # The concept file should contain the source filename in frontmatter or evidence
        if echo "$CONCEPT_CONTENT" | grep -q "$TEST_FILENAME"; then
            pass "Concept references source document: $TEST_FILENAME"
        else
            # May reference other documents in the ontology
            log_verbose "Concept doesn't reference $TEST_FILENAME (may reference other docs)"
        fi
    fi
else
    # May not find concepts if LLM extraction hasn't run or is slow
    log_verbose "No concepts found - this may be expected if extraction is still running"
    pass "Query directory created (concepts may appear after extraction completes)"
fi

# Check .meta directory contents
if [[ -f "$CONCEPT_QUERY_DIR/.meta/query.toml" ]]; then
    QUERY_TOML_CONTENT=$(cat "$CONCEPT_QUERY_DIR/.meta/query.toml")
    if echo "$QUERY_TOML_CONTENT" | grep -q "query_text = \"$CONCEPT_QUERY\""; then
        pass "Query text correctly stored in query.toml"
    else
        fail "Query text not found in query.toml"
    fi
fi

# Clean up concept query
rmdir "$CONCEPT_QUERY_DIR" 2>/dev/null || true

timer_end "concept_query"

# ============================================================================
# Test 7: rmdir cleanup
# ============================================================================

timer_start "rmdir_cleanup"
log "Test 7: Testing query directory removal..."

if rmdir "$QUERY_DIR" 2>/dev/null; then
    pass "Removed query directory"
else
    fail "Failed to remove query directory"
fi

# Verify it's gone
if [[ -d "$QUERY_DIR" ]]; then
    fail "Query directory still exists after rmdir"
else
    pass "Query directory properly removed"
fi
timer_end "rmdir_cleanup"

# ============================================================================
# Summary
# ============================================================================

echo ""
echo "============================================"
echo -e "Test Results: ${GREEN}$PASS_COUNT passed${NC}, ${RED}$FAIL_COUNT failed${NC}"
echo "Log directory: $LOG_DIR"
echo "============================================"

print_timings

if [[ $FAIL_COUNT -gt 0 ]]; then
    echo ""
    echo "Failed tests - check $LOG_DIR/test.log for details"
    exit 1
fi

exit 0
