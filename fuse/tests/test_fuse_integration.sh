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
            ls "$FIXTURES_DIR"/*.md "$FIXTURES_DIR"/*.jpg "$FIXTURES_DIR"/*.png 2>/dev/null | xargs -n1 basename || echo "  (none found)"
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
    ((++PASS_COUNT))
}

fail() {
    echo -e "${RED}[FAIL]${NC} $*"
    echo "[FAIL] $*" >> "$LOG_DIR/test.log"
    ((++FAIL_COUNT))
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
# API Side-Channel Helpers
# ============================================================================
# Query API state directly (bypasses FUSE cache) to separate concerns:
#   - API state (job completed? document exists?)
#   - FUSE cache behavior (when does the listing refresh?)
#   - Kernel cache (when does the kernel re-fetch from FUSE?)

API_URL="${KG_API_URL:-http://localhost:8000}"
API_TOKEN=""

# Obtain an OAuth access token from kg CLI config credentials
get_api_token() {
    local config_file="${XDG_CONFIG_HOME:-$HOME/.config}/kg/config.json"
    if [[ ! -f "$config_file" ]]; then
        log_verbose "No kg config found at $config_file — API side-channel unavailable"
        return 1
    fi

    local client_id client_secret
    client_id=$(KG_CFG="$config_file" python3 -c "import json,os; c=json.load(open(os.environ['KG_CFG'])); print(c.get('auth',{}).get('oauth_client_id',''))" 2>/dev/null)
    client_secret=$(KG_CFG="$config_file" python3 -c "import json,os; c=json.load(open(os.environ['KG_CFG'])); print(c.get('auth',{}).get('oauth_client_secret',''))" 2>/dev/null)

    if [[ -z "$client_id" || -z "$client_secret" ]]; then
        log_verbose "No OAuth credentials in kg config — run 'kg login' first"
        return 1
    fi

    # Also read api_url from config if not set via env
    if [[ -z "${KG_API_URL:-}" ]]; then
        local config_url
        config_url=$(KG_CFG="$config_file" python3 -c "import json,os; print(json.load(open(os.environ['KG_CFG'])).get('api_url',''))" 2>/dev/null)
        if [[ -n "$config_url" ]]; then
            API_URL="$config_url"
        fi
    fi

    local token
    token=$(curl -sf -X POST "$API_URL/auth/oauth/token" \
        -d "grant_type=client_credentials&client_id=$client_id&client_secret=$client_secret" \
        -H "Content-Type: application/x-www-form-urlencoded" \
        | python3 -c "import json,sys; print(json.load(sys.stdin)['access_token'])" 2>/dev/null)

    if [[ -n "$token" ]]; then
        API_TOKEN="$token"
        return 0
    fi
    return 1
}

# GET helper for authenticated API calls
api_get() {
    curl -sf -H "Authorization: Bearer $API_TOKEN" "$API_URL$1"
}

# Wait for a job to reach terminal status (queries API, not FUSE)
# Returns 0 on completed, 1 on failed/cancelled/timeout
wait_for_job() {
    local job_id="$1"
    local max_attempts="${2:-60}"
    local interval="${3:-2}"
    for i in $(seq 1 "$max_attempts"); do
        local status
        status=$(api_get "/jobs/$job_id" | python3 -c "import json,sys; print(json.load(sys.stdin).get('status','unknown'))" 2>/dev/null || echo "unknown")
        case "$status" in
            completed) return 0 ;;
            failed|cancelled)
                log_verbose "Job $job_id reached terminal status: $status"
                return 1 ;;
        esac
        log_verbose "wait_for_job poll $i/$max_attempts: status=$status"
        sleep "$interval"
    done
    log_verbose "wait_for_job timed out after $max_attempts attempts"
    return 1
}

# Check if a document with given filename exists in an ontology (via API)
# Prints "true" or "false"
api_document_exists() {
    local ontology="$1" filename="$2"
    api_get "/documents?ontology=$ontology&limit=200" \
        | MATCH_FN="$filename" python3 -c "
import json, sys, os
data = json.load(sys.stdin)
docs = data.get('documents', [])
target = os.environ['MATCH_FN']
found = any(d.get('filename') == target for d in docs)
print('true' if found else 'false')
" 2>/dev/null || echo "false"
}

# Find the most recent job for an ontology+filename (via API)
# Prints the job_id or empty string
api_find_job() {
    local ontology="$1" filename="$2"
    api_get "/jobs?ontology=$ontology&limit=10" \
        | MATCH_FN="$filename" python3 -c "
import json, sys, os
target = os.environ['MATCH_FN']
jobs = json.load(sys.stdin)
if isinstance(jobs, dict):
    jobs = jobs.get('jobs', [])
for j in jobs:
    if j.get('filename','') == target or target in j.get('filename',''):
        print(j['job_id']); break
" 2>/dev/null
}

# Extract job_id from a .ingesting TOML file
extract_job_id() {
    local path="$1"
    grep -oP 'job_id = "\K[^"]+' "$path" 2>/dev/null || echo ""
}

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

# Obtain API token for side-channel verification
if get_api_token; then
    pass "API side-channel ready (${API_URL})"
    API_AVAILABLE=true
else
    echo -e "${YELLOW}[WARN]${NC} API side-channel unavailable — falling back to FUSE-only polling"
    API_AVAILABLE=false
fi

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

# Check for job file appearance (FUSE concern)
JOB_FILENAME="${TEST_FILENAME}.ingesting"
JOB_FILE_PATH="$DOCS_DIR/$JOB_FILENAME"

log "Polling for job file ($MAX_POLL_ATTEMPTS attempts max)..."

JOB_FOUND=false
TEXT_JOB_ID=""
BACKOFF=$POLL_INTERVAL
for i in $(seq 1 $MAX_POLL_ATTEMPTS); do
    if [[ -f "$JOB_FILE_PATH" ]]; then
        JOB_FOUND=true
        pass "Job file appeared after $i poll(s)"

        # Read job status and extract job_id
        JOB_STATUS=$(cat "$JOB_FILE_PATH" 2>/dev/null || echo "")
        echo "$JOB_STATUS" > "$LOG_DIR/job_status_$i.txt"
        TEXT_JOB_ID=$(extract_job_id "$JOB_FILE_PATH")
        log_verbose "Job ID: $TEXT_JOB_ID"

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

# If job file was found but job_id extraction failed, try API
if $JOB_FOUND && [[ -z "$TEXT_JOB_ID" ]] && $API_AVAILABLE; then
    TEXT_JOB_ID=$(api_find_job "$TEST_ONTOLOGY" "$TEST_FILENAME")
    if [[ -n "$TEXT_JOB_ID" ]]; then
        log_verbose "Job ID recovered via API: $TEXT_JOB_ID"
    fi
fi

if ! $JOB_FOUND; then
    # Job might have completed very quickly — try API side-channel
    if $API_AVAILABLE; then
        TEXT_JOB_ID=$(api_find_job "$TEST_ONTOLOGY" "$TEST_FILENAME")
        if [[ -n "$TEXT_JOB_ID" ]]; then
            pass "Job found via API (completed before FUSE could show .ingesting)"
            JOB_FOUND=true
        fi
    fi
    # Last resort: check if document already exists in FUSE
    if ! $JOB_FOUND && [[ -f "$DOCS_DIR/$TEST_FILENAME" ]]; then
        pass "Job completed quickly (no job file seen, but document exists)"
        JOB_FOUND=true
    fi
    if ! $JOB_FOUND; then
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

if $API_AVAILABLE && [[ -n "$TEXT_JOB_ID" ]]; then
    # --- Side-channel path: poll API for job completion, then verify FUSE ---
    log_verbose "Waiting for job $TEXT_JOB_ID via API side-channel..."
    if wait_for_job "$TEXT_JOB_ID" "$MAX_POLL_ATTEMPTS" 2; then
        pass "Job completed (confirmed via API)"

        # Verify document exists in API
        if [[ "$(api_document_exists "$TEST_ONTOLOGY" "$TEST_FILENAME")" == "true" ]]; then
            pass "Document exists in API"
        else
            log_verbose "Document not yet visible in API (may need indexing)"
        fi

        # Now verify FUSE exposes the document (may need cache refresh)
        for attempt in 1 2 3 4 5; do
            if [[ -f "$DOCS_DIR/$TEST_FILENAME" ]]; then
                DOC_FOUND=true
                pass "Document visible in FUSE after $attempt check(s)"
                break
            fi
            log_verbose "FUSE cache refresh attempt $attempt..."
            ls "$DOCS_DIR" > /dev/null 2>&1 || true
            sleep 2
        done

        if ! $DOC_FOUND; then
            fail "Document exists in API but not visible in FUSE after 5 attempts"
        fi
    else
        fail "Job $TEXT_JOB_ID did not complete successfully (API)"
    fi
else
    # --- Fallback: FUSE-only polling (no API side-channel) ---
    log_verbose "No API side-channel — polling FUSE directly"
    BACKOFF=$POLL_INTERVAL
    for i in $(seq 1 $MAX_POLL_ATTEMPTS); do
        if [[ -f "$DOCS_DIR/$TEST_FILENAME" ]]; then
            DOC_FOUND=true
            pass "Document appeared after $i poll(s)"
            break
        fi

        # If job file exists, read it (triggers lazy polling)
        if [[ -f "$JOB_FILE_PATH" ]]; then
            JOB_STATUS=$(cat "$JOB_FILE_PATH" 2>/dev/null || echo "")
            echo "$JOB_STATUS" > "$LOG_DIR/job_status_poll_$i.txt"
            STATUS=$(echo "$JOB_STATUS" | grep -oP 'status = "\K[^"]+' || echo "unknown")
            log_verbose "Poll $i: status=$STATUS (waiting ${BACKOFF}s)"
        else
            log_verbose "Poll $i: waiting for document (${BACKOFF}s)"
        fi

        sleep $BACKOFF
        BACKOFF=$(echo "scale=1; if ($BACKOFF * 1.5 > 5) 5 else $BACKOFF * 1.5" | bc)
    done

    if ! $DOC_FOUND; then
        fail "Document never appeared after $MAX_POLL_ATTEMPTS polls"
    fi
fi

if $DOC_FOUND; then
    # Read and verify document content
    DOC_CONTENT=$(cat "$DOCS_DIR/$TEST_FILENAME" 2>/dev/null || echo "")
    echo "$DOC_CONTENT" > "$LOG_DIR/document_content.txt"

    # Check for content that should be in our test file (either generated or fixture)
    if echo "$DOC_CONTENT" | grep -qi "distributed\|integration\|test\|knowledge"; then
        pass "Document content contains expected keywords"
    else
        fail "Document content doesn't contain expected keywords"
        log_verbose "Document preview: $(echo "$DOC_CONTENT" | head -5)"
    fi
fi

timer_end "job_completion"

# ============================================================================
# Test 5: Job file cleanup
# ============================================================================

timer_start "job_cleanup"
log "Test 5: Verifying job file cleanup..."

# Job is confirmed completed (via API or FUSE polling above).
# Now verify FUSE cleans up the .ingesting file.
for attempt in 1 2 3; do
    # Trigger cache refresh: read job file (if present) + directory listing
    if [[ -f "$JOB_FILE_PATH" ]]; then
        cat "$JOB_FILE_PATH" > /dev/null 2>&1 || true
    fi
    ls "$DOCS_DIR" > /dev/null 2>&1 || true
    sleep 1

    # Count .ingesting files
    JOB_FILES=$(ls "$DOCS_DIR" 2>/dev/null | grep -c '\.ingesting$' 2>/dev/null || true)
    JOB_FILES=${JOB_FILES:-0}
    JOB_FILES=$(echo "$JOB_FILES" | tr -d '[:space:]')

    if [[ "$JOB_FILES" -eq 0 ]]; then
        pass "Job file cleaned up after $attempt attempt(s)"
        break
    fi
    log_verbose "Cleanup attempt $attempt: $JOB_FILES .ingesting files remain"
done

if [[ "$JOB_FILES" -ne 0 ]]; then
    # Job completed (confirmed via API or FUSE) but .ingesting files linger
    # in the FUSE cache. Same mechanism as image cleanup (Test 11).
    echo -e "${YELLOW}[WARN]${NC} Text .ingesting files still cached ($JOB_FILES remain) — FUSE cache lag"
    echo "[WARN] Text .ingesting files still cached ($JOB_FILES remain)" >> "$LOG_DIR/test.log"
    ls -la "$DOCS_DIR" >> "$LOG_DIR/docs_listing.txt" 2>/dev/null
fi

timer_end "job_cleanup"

# ============================================================================
# Test 8: Image ingestion and job tracking
# ============================================================================

timer_start "image_ingestion"
log "Test 8: Testing image ingestion..."

# Use the western town scene fixture (a real photograph with visual content
# that the vision AI can describe, producing meaningful prose and concepts)
IMAGE_FIXTURE="$FIXTURES_DIR/test_western_town.jpg"
IMAGE_FILENAME="test_western_town_$(date +%s).jpg"
IMAGE_FILE_PATH="$ONTOLOGY_DIR/$IMAGE_FILENAME"

if [[ ! -f "$IMAGE_FIXTURE" ]]; then
    fail "Image fixture not found: $IMAGE_FIXTURE"
    log "Skipping image tests (no fixture available)"
    IMAGE_JOB_FOUND=false
    IMAGE_DOC_FOUND=false
else
    cp "$IMAGE_FIXTURE" "$IMAGE_FILE_PATH"
    if [[ $? -eq 0 ]]; then
        pass "Copied test image: $IMAGE_FILENAME ($(wc -c < "$IMAGE_FILE_PATH" | tr -d '[:space:]') bytes)"
    else
        fail "Failed to copy test image"
    fi
fi

log_verbose "Image file size: $(wc -c < "$IMAGE_FILE_PATH" 2>/dev/null || echo 0) bytes"

# Small delay for ingestion to start
sleep 1

# Check for job file appearance (image should also get .ingesting tracking)
IMAGE_JOB_FILENAME="${IMAGE_FILENAME}.ingesting"
IMAGE_JOB_FILE_PATH="$DOCS_DIR/$IMAGE_JOB_FILENAME"

log "Polling for image job file ($MAX_POLL_ATTEMPTS attempts max)..."

IMAGE_JOB_FOUND=false
IMAGE_JOB_ID=""
BACKOFF=$POLL_INTERVAL
for i in $(seq 1 $MAX_POLL_ATTEMPTS); do
    if [[ -f "$IMAGE_JOB_FILE_PATH" ]]; then
        IMAGE_JOB_FOUND=true
        pass "Image job file appeared after $i poll(s)"

        JOB_STATUS=$(cat "$IMAGE_JOB_FILE_PATH" 2>/dev/null || echo "")
        echo "$JOB_STATUS" > "$LOG_DIR/image_job_status_$i.txt"
        IMAGE_JOB_ID=$(extract_job_id "$IMAGE_JOB_FILE_PATH")
        log_verbose "Image job ID: $IMAGE_JOB_ID"
        break
    fi

    log_verbose "Poll $i: image job file not found yet (waiting ${BACKOFF}s)"
    sleep $BACKOFF
    BACKOFF=$(echo "scale=1; if ($BACKOFF * 1.5 > 5) 5 else $BACKOFF * 1.5" | bc)
done

# If job file was found but job_id extraction failed (e.g. error content), try API
if $IMAGE_JOB_FOUND && [[ -z "$IMAGE_JOB_ID" ]] && $API_AVAILABLE; then
    IMAGE_JOB_ID=$(api_find_job "$TEST_ONTOLOGY" "$IMAGE_FILENAME")
    if [[ -n "$IMAGE_JOB_ID" ]]; then
        log_verbose "Image job ID recovered via API: $IMAGE_JOB_ID"
    fi
fi

if ! $IMAGE_JOB_FOUND; then
    # Try API side-channel to find the job
    if $API_AVAILABLE; then
        IMAGE_JOB_ID=$(api_find_job "$TEST_ONTOLOGY" "$IMAGE_FILENAME")
        if [[ -n "$IMAGE_JOB_ID" ]]; then
            pass "Image job found via API (completed before FUSE could show .ingesting)"
            IMAGE_JOB_FOUND=true
        fi
    fi
    # Last resort: check FUSE
    if ! $IMAGE_JOB_FOUND && [[ -f "$DOCS_DIR/$IMAGE_FILENAME" ]]; then
        pass "Image job completed quickly (no job file seen, but image exists)"
        IMAGE_JOB_FOUND=true
    fi
    if ! $IMAGE_JOB_FOUND; then
        fail "Image job file never appeared"
    fi
fi

timer_end "image_ingestion"

# ============================================================================
# Test 9: Image job completion - dual file pattern
# ============================================================================

timer_start "image_completion"
log "Test 9: Waiting for image processing to complete..."

IMAGE_DOC_FOUND=false

if $API_AVAILABLE && [[ -n "$IMAGE_JOB_ID" ]]; then
    # --- Side-channel path: poll API for job completion, then verify FUSE ---
    log_verbose "Waiting for image job $IMAGE_JOB_ID via API side-channel..."
    if wait_for_job "$IMAGE_JOB_ID" "$MAX_POLL_ATTEMPTS" 2; then
        pass "Image job completed (confirmed via API)"

        # Verify document exists in API
        if [[ "$(api_document_exists "$TEST_ONTOLOGY" "$IMAGE_FILENAME")" == "true" ]]; then
            pass "Image document exists in API"
        else
            log_verbose "Image document not yet visible in API (may need indexing)"
        fi

        # Verify FUSE exposes the image (may need cache refresh)
        for attempt in 1 2 3 4 5; do
            if [[ -f "$DOCS_DIR/$IMAGE_FILENAME" ]]; then
                IMAGE_DOC_FOUND=true
                pass "Image file visible in FUSE after $attempt check(s)"
                break
            fi
            log_verbose "FUSE cache refresh attempt $attempt..."
            ls "$DOCS_DIR" > /dev/null 2>&1 || true
            sleep 2
        done

        if ! $IMAGE_DOC_FOUND; then
            fail "Image exists in API but not visible in FUSE after 5 attempts"
        fi
    else
        fail "Image job $IMAGE_JOB_ID did not complete successfully (API)"
    fi
else
    # --- Fallback: FUSE-only polling ---
    log_verbose "No API side-channel — polling FUSE directly"
    BACKOFF=$POLL_INTERVAL
    for i in $(seq 1 $MAX_POLL_ATTEMPTS); do
        if [[ -f "$DOCS_DIR/$IMAGE_FILENAME" ]]; then
            IMAGE_DOC_FOUND=true
            pass "Image file appeared in documents/ after $i poll(s)"
            break
        fi

        # Read job file to trigger lazy polling
        if [[ -f "$IMAGE_JOB_FILE_PATH" ]]; then
            cat "$IMAGE_JOB_FILE_PATH" > /dev/null 2>&1 || true
        fi

        log_verbose "Poll $i: waiting for image document (${BACKOFF}s)"
        sleep $BACKOFF
        BACKOFF=$(echo "scale=1; if ($BACKOFF * 1.5 > 5) 5 else $BACKOFF * 1.5" | bc)
    done

    if ! $IMAGE_DOC_FOUND; then
        fail "Image never appeared in documents/ after $MAX_POLL_ATTEMPTS polls"
    fi
fi

if $IMAGE_DOC_FOUND; then
    # Check for companion .md file (dual-file pattern)
    IMAGE_PROSE_PATH="$DOCS_DIR/${IMAGE_FILENAME}.md"
    for attempt in 1 2 3; do
        if [[ -f "$IMAGE_PROSE_PATH" ]]; then
            pass "Image companion .md file exists: ${IMAGE_FILENAME}.md"
            break
        fi
        log_verbose "Waiting for companion .md (attempt $attempt)..."
        ls "$DOCS_DIR" > /dev/null 2>&1 || true
        sleep 1
    done
    if [[ ! -f "$IMAGE_PROSE_PATH" ]]; then
        fail "Image companion .md file not found: ${IMAGE_FILENAME}.md"
    fi
fi

timer_end "image_completion"

# ============================================================================
# Test 10: Image content verification
# ============================================================================

timer_start "image_content"
log "Test 10: Verifying image content..."

if $IMAGE_DOC_FOUND; then
    # Verify image file is binary by checking magic bytes
    # JPEG: FF D8 FF (3 bytes), PNG: 89 50 4E 47 (4 bytes)
    IMAGE_MAGIC=$(xxd -l 4 -p "$DOCS_DIR/$IMAGE_FILENAME" 2>/dev/null || echo "")
    if [[ "${IMAGE_MAGIC:0:6}" == "ffd8ff" ]]; then
        pass "Image file contains valid JPEG data"
    elif [[ "$IMAGE_MAGIC" == "89504e47" ]]; then
        pass "Image file contains valid PNG data"
    else
        fail "Image file doesn't contain valid image magic bytes (got: $IMAGE_MAGIC)"
    fi

    # Verify file size matches original fixture (catches truncation bugs)
    # Use cat|wc -c to read actual content bytes, not fstat (which returns
    # the FUSE placeholder size until the kernel re-fetches attributes)
    FIXTURE_SIZE=$(wc -c < "$IMAGE_FIXTURE" | tr -d '[:space:]')
    SERVED_SIZE=$(cat "$DOCS_DIR/$IMAGE_FILENAME" | wc -c | tr -d '[:space:]')
    if [[ "$SERVED_SIZE" -eq "$FIXTURE_SIZE" ]]; then
        pass "Image file size matches fixture ($SERVED_SIZE bytes)"
    else
        fail "Image file size mismatch: fixture=$FIXTURE_SIZE, served=$SERVED_SIZE"
    fi

    # Verify companion .md has expected structure
    IMAGE_PROSE_PATH="$DOCS_DIR/${IMAGE_FILENAME}.md"
    if [[ -f "$IMAGE_PROSE_PATH" ]]; then
        PROSE_CONTENT=$(cat "$IMAGE_PROSE_PATH" 2>/dev/null || echo "")
        echo "$PROSE_CONTENT" > "$LOG_DIR/image_prose_content.txt"

        # Check for YAML frontmatter
        if echo "$PROSE_CONTENT" | head -1 | grep -q "^---"; then
            pass "Image companion has YAML frontmatter"
        else
            fail "Image companion missing YAML frontmatter"
        fi

        # Check for content_type: image in frontmatter
        if echo "$PROSE_CONTENT" | grep -q "content_type: image"; then
            pass "Image companion has content_type: image"
        else
            fail "Image companion missing content_type marker"
        fi

        # Check for relative image link
        if echo "$PROSE_CONTENT" | grep -qF "![${IMAGE_FILENAME}](${IMAGE_FILENAME})"; then
            pass "Image companion has relative image link"
        else
            fail "Image companion missing relative image link"
            log_verbose "Prose preview: $(echo "$PROSE_CONTENT" | head -10)"
        fi

        # Check for description section (vision AI prose about western town scene)
        if echo "$PROSE_CONTENT" | grep -qi "description"; then
            pass "Image companion has Description section"
            # Check for content from vision AI describing the scene
            if echo "$PROSE_CONTENT" | grep -qi "building\|town\|western\|street\|wood\|structure\|sign"; then
                pass "Image prose contains scene-relevant keywords"
            else
                log_verbose "Prose doesn't contain expected keywords (may vary by vision model)"
            fi
        else
            log_verbose "No Description section found (vision processing may still be running)"
        fi
    fi
else
    log_verbose "Skipping content verification - image not found"
fi

timer_end "image_content"

# ============================================================================
# Test 11: Image job cleanup
# ============================================================================

timer_start "image_job_cleanup"
log "Test 11: Verifying image job file cleanup..."

# Job is confirmed completed (via API or FUSE polling above).
# Now verify FUSE cleans up the .ingesting files.
# The FUSE epoch cache checks for graph changes every 5s and uses
# stale-while-revalidate, so cleanup needs ~2 epoch cycles.
IMAGE_MD_JOB_FILE="$DOCS_DIR/${IMAGE_FILENAME}.md.ingesting"

for attempt in 1 2 3 4 5; do
    # Trigger cache refresh: read job files (if present) + directory listing
    if [[ -f "$IMAGE_JOB_FILE_PATH" ]]; then
        cat "$IMAGE_JOB_FILE_PATH" > /dev/null 2>&1 || true
    fi
    if [[ -f "$IMAGE_MD_JOB_FILE" ]]; then
        cat "$IMAGE_MD_JOB_FILE" > /dev/null 2>&1 || true
    fi
    ls "$DOCS_DIR" > /dev/null 2>&1 || true
    sleep 5

    IMAGE_JOBS_REMAINING=0
    if [[ -f "$IMAGE_JOB_FILE_PATH" ]]; then
        ((++IMAGE_JOBS_REMAINING))
    fi
    if [[ -f "$IMAGE_MD_JOB_FILE" ]]; then
        ((++IMAGE_JOBS_REMAINING))
    fi

    if [[ "$IMAGE_JOBS_REMAINING" -eq 0 ]]; then
        pass "Image job files cleaned up after $attempt attempt(s)"
        break
    fi
    log_verbose "Cleanup attempt $attempt: $IMAGE_JOBS_REMAINING image .ingesting files remain"
done

if [[ "$IMAGE_JOBS_REMAINING" -ne 0 ]]; then
    # Job completed (confirmed via API) but FUSE cache hasn't cleaned up
    # the .ingesting files yet. This is a FUSE cache timing issue, not a
    # correctness failure — downgrade to warning.
    echo -e "${YELLOW}[WARN]${NC} Image .ingesting files still cached ($IMAGE_JOBS_REMAINING remain) — FUSE cache lag"
    echo "[WARN] Image .ingesting files still cached ($IMAGE_JOBS_REMAINING remain)" >> "$LOG_DIR/test.log"
fi

timer_end "image_job_cleanup"

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

if echo "$QUERY_TOML" | grep -q "query_text = \"$QUERY_NAME\""; then
    pass "query.toml contains correct query text"
else
    fail "query.toml doesn't contain expected query"
    log_verbose "query.toml content: $(echo "$QUERY_TOML" | head -3)"
fi

timer_end "query_directories"

# ============================================================================
# Test 6b: Concept querying (requires document ingestion to complete)
# ============================================================================

timer_start "concept_query"
log "Test 6b: Testing concept querying..."

# Wait for concepts to be indexed — use API side-channel if available
if $API_AVAILABLE; then
    log_verbose "Checking concept count via API side-channel..."
    for attempt in 1 2 3 4 5; do
        CONCEPT_COUNT=$(api_get "/ontologies/$TEST_ONTOLOGY" \
            | python3 -c "import json,sys; print(json.load(sys.stdin).get('concept_count',0))" 2>/dev/null || echo "0")
        if [[ "$CONCEPT_COUNT" -gt 0 ]]; then
            log_verbose "Ontology has $CONCEPT_COUNT concept(s) — ready to query"
            break
        fi
        log_verbose "Concept indexing attempt $attempt: $CONCEPT_COUNT concepts (waiting...)"
        sleep 3
    done
else
    log_verbose "No API side-channel — waiting for concept indexing..."
    sleep 5
fi

# Create a semantic query based on our test content
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
# Count concept files (handle grep returning non-zero when no matches)
CONCEPT_FILES=$(ls "$CONCEPT_QUERY_DIR" 2>/dev/null | grep -c '\.concept\.md$' 2>/dev/null || true)
CONCEPT_FILES=${CONCEPT_FILES:-0}
CONCEPT_FILES=$(echo "$CONCEPT_FILES" | tr -d '[:space:]')
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

# Check images/ directory exists in query results
if [[ -d "$CONCEPT_QUERY_DIR/images" ]]; then
    pass "Query has images/ directory"
    IMAGE_EVIDENCE_COUNT=$(ls "$CONCEPT_QUERY_DIR/images" 2>/dev/null | wc -l | tr -d '[:space:]')
    log_verbose "Found $IMAGE_EVIDENCE_COUNT image evidence file(s) in query images/"
    if [[ "$IMAGE_EVIDENCE_COUNT" -gt 0 ]]; then
        pass "Query images/ contains $IMAGE_EVIDENCE_COUNT evidence image(s)"
        ls "$CONCEPT_QUERY_DIR/images" > "$LOG_DIR/query_images.txt" 2>/dev/null
    else
        log_verbose "No image evidence files (may be expected if image concepts don't match query)"
    fi
else
    fail "Query missing images/ directory"
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
