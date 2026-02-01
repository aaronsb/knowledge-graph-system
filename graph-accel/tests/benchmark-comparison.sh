#!/usr/bin/env bash
# benchmark-comparison.sh — Compare AGE vs graph_accel traversal
#
# Tests neighborhood queries at depths 1-5 against the live knowledge graph.
# Validates: timing, concept counts, and data correctness.
#
# Requirements:
#   - knowledge-graph-postgres container running with AGE graph loaded
#   - graph_accel extension installed (Option 0 or later deployment)
#
# Usage:
#   ./graph-accel/tests/benchmark-comparison.sh
#   ./graph-accel/tests/benchmark-comparison.sh sha256:990a8_chunk1_d7639f13   # custom concept

set -euo pipefail

# Configuration
CONTAINER="knowledge-graph-postgres"
DB="knowledge_graph"
USER="admin"
CONCEPT_ID="${1:-sha256:990a8_chunk1_d7639f13}"  # "Way" concept, degree 36
MAX_DEPTH=5

psql_cmd() {
    docker exec "$CONTAINER" psql -U "$USER" -d "$DB" -t -A "$@"
}

psql_timed() {
    docker exec "$CONTAINER" psql -U "$USER" -d "$DB" "$@"
}

echo "================================================================"
echo "  graph_accel vs AGE Benchmark Comparison"
echo "================================================================"
echo ""
echo "Container: $CONTAINER"
echo "Concept:   $CONCEPT_ID"
echo "Max depth: $MAX_DEPTH"
echo ""

# --- Verify prerequisites ---
echo "--- Prerequisites ---"

node_count=$(psql_cmd -c "SELECT count(*)::text FROM knowledge_graph.\"Concept\";")
echo "Concept count: $node_count"

concept_label=$(psql_cmd -c "LOAD 'age'; SET search_path = ag_catalog, public;" \
    -c "SELECT * FROM cypher('knowledge_graph', \$\$
        MATCH (c:Concept {concept_id: '$CONCEPT_ID'}) RETURN c.label
    \$\$) as (label agtype);")
echo "Target concept: $concept_label"

if [ -z "$concept_label" ]; then
    echo "ERROR: Concept $CONCEPT_ID not found"
    exit 1
fi

# Check graph_accel is installed
ext_check=$(psql_cmd -c "SELECT count(*) FROM pg_extension WHERE extname = 'graph_accel';")
if [ "$ext_check" -eq 0 ]; then
    echo "ERROR: graph_accel extension not installed"
    exit 1
fi
echo "graph_accel: installed"
echo ""

# --- AGE Baseline ---
echo "================================================================"
echo "  AGE Baseline (fixed-depth chain queries)"
echo "================================================================"
echo ""

declare -a AGE_COUNTS
declare -a AGE_TIMES

for depth in $(seq 1 $MAX_DEPTH); do
    # Build the chain pattern
    chain=""
    for i in $(seq 0 $((depth - 1))); do
        if [ $i -lt $((depth - 1)) ]; then
            chain="${chain}[r${i}]-(h$((i+1)):Concept)-"
        else
            chain="${chain}[r${i}]-(target:Concept)"
        fi
    done

    query="MATCH (start:Concept {concept_id: '$CONCEPT_ID'})-${chain}
           WHERE start <> target
           WITH DISTINCT target.concept_id as concept_id
           RETURN count(*) as found"

    # Run with timing
    output=$(psql_timed -c "\\timing" \
        -c "LOAD 'age'" \
        -c "SET search_path = ag_catalog, public" \
        -c "SELECT * FROM cypher('knowledge_graph', \$\$ $query \$\$) as (found agtype);" 2>&1)

    count=$(echo "$output" | grep -E '^\s*[0-9]+' | tr -d ' ')
    time_ms=$(echo "$output" | grep "^Time:" | tail -1 | grep -oP '[\d.]+' | head -1)

    AGE_COUNTS[$depth]="$count"
    AGE_TIMES[$depth]="$time_ms"

    printf "  Depth %d: %4s concepts in %10s ms\n" "$depth" "$count" "$time_ms"
done

echo ""

# --- graph_accel ---
echo "================================================================"
echo "  graph_accel (in-memory BFS)"
echo "================================================================"
echo ""

declare -a GA_COUNTS
declare -a GA_TIMES

# Load graph and run all depths in one session
ga_output=$(psql_timed -c "\\timing" \
    -c "SET graph_accel.node_id_property = 'concept_id';" \
    -c "SELECT * FROM graph_accel_load('knowledge_graph');" \
    -c "SELECT count(*) FROM graph_accel_neighborhood('$CONCEPT_ID', 1) WHERE label = 'Concept';" \
    -c "SELECT count(*) FROM graph_accel_neighborhood('$CONCEPT_ID', 2) WHERE label = 'Concept';" \
    -c "SELECT count(*) FROM graph_accel_neighborhood('$CONCEPT_ID', 3) WHERE label = 'Concept';" \
    -c "SELECT count(*) FROM graph_accel_neighborhood('$CONCEPT_ID', 4) WHERE label = 'Concept';" \
    -c "SELECT count(*) FROM graph_accel_neighborhood('$CONCEPT_ID', 5) WHERE label = 'Concept';" \
    2>&1)

# Parse load time
load_time=$(echo "$ga_output" | grep -A2 "node_count" | tail -1 | awk -F'|' '{print $3}' | tr -d ' ')
echo "  Load: ${load_time}ms"
echo ""

# Parse per-depth results (counts and times)
# The output has alternating count rows and Time: lines
depth=0
while IFS= read -r line; do
    if echo "$line" | grep -qE '^\s+[0-9]+$'; then
        depth=$((depth + 1))
        GA_COUNTS[$depth]=$(echo "$line" | tr -d ' ')
    fi
    if echo "$line" | grep -q "^Time:" && [ $depth -ge 1 ] && [ $depth -le $MAX_DEPTH ]; then
        GA_TIMES[$depth]=$(echo "$line" | grep -oP '[\d.]+' | head -1)
    fi
done <<< "$ga_output"

for depth in $(seq 1 $MAX_DEPTH); do
    printf "  Depth %d: %4s concepts in %10s ms\n" "$depth" "${GA_COUNTS[$depth]:-?}" "${GA_TIMES[$depth]:-?}"
done

echo ""

# --- Comparison ---
echo "================================================================"
echo "  Comparison"
echo "================================================================"
echo ""
printf "  %-5s | %-10s %-10s | %-10s %-10s | %-10s | %-6s\n" \
    "Depth" "AGE count" "AGE ms" "GA count" "GA ms" "Speedup" "Match"
printf "  %-5s-+-%-10s-%-10s-+-%-10s-%-10s-+-%-10s-+-%-6s\n" \
    "-----" "----------" "----------" "----------" "----------" "----------" "------"

all_pass=true

for depth in $(seq 1 $MAX_DEPTH); do
    age_c="${AGE_COUNTS[$depth]:-0}"
    age_t="${AGE_TIMES[$depth]:-0}"
    ga_c="${GA_COUNTS[$depth]:-0}"
    ga_t="${GA_TIMES[$depth]:-0}"

    # Speedup calculation
    if [ "$(echo "$ga_t > 0" | bc -l 2>/dev/null || echo 0)" = "1" ]; then
        speedup=$(echo "scale=0; $age_t / $ga_t" | bc -l 2>/dev/null || echo "N/A")
        speedup="${speedup}x"
    else
        speedup="N/A"
    fi

    # Data check: graph_accel should find >= AGE concepts (superset due to cross-type traversal)
    if [ "$ga_c" -ge "$age_c" ] 2>/dev/null; then
        match="OK"
    else
        match="FAIL"
        all_pass=false
    fi

    printf "  %-5d | %-10s %-10s | %-10s %-10s | %-10s | %-6s\n" \
        "$depth" "$age_c" "$age_t" "$ga_c" "$ga_t" "$speedup" "$match"
done

echo ""

# --- Data correctness: depth 1 exact match ---
echo "--- Data Correctness (depth 1 exact match) ---"

age_d1=$(psql_cmd -c "LOAD 'age'; SET search_path = ag_catalog, public;" \
    -c "SELECT * FROM cypher('knowledge_graph', \$\$
        MATCH (start:Concept {concept_id: '$CONCEPT_ID'})-[r0]-(target:Concept)
        WHERE start <> target
        RETURN DISTINCT target.concept_id
        ORDER BY target.concept_id
    \$\$) as (cid agtype);" | grep -v '^$\|^LOAD\|^SET' | sed 's/"//g' | sort)

ga_d1=$(psql_cmd \
    -c "SET graph_accel.node_id_property = 'concept_id';" \
    -c "SELECT * FROM graph_accel_load('knowledge_graph');" \
    -c "SELECT app_id FROM graph_accel_neighborhood('$CONCEPT_ID', 1) WHERE label = 'Concept' ORDER BY app_id;" \
    | grep '^sha256:\|^c_' | sort)

if diff <(echo "$age_d1") <(echo "$ga_d1") > /dev/null 2>&1; then
    echo "  Depth 1: EXACT MATCH ($(echo "$age_d1" | wc -l) concepts)"
else
    echo "  Depth 1: MISMATCH"
    echo "  Only in AGE:"
    comm -23 <(echo "$age_d1") <(echo "$ga_d1") | head -5
    echo "  Only in graph_accel:"
    comm -13 <(echo "$age_d1") <(echo "$ga_d1") | head -5
    all_pass=false
fi

echo ""

# --- Summary ---
if $all_pass; then
    echo "RESULT: ALL CHECKS PASSED"
    exit 0
else
    echo "RESULT: SOME CHECKS FAILED"
    exit 1
fi
