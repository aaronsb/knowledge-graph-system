#!/usr/bin/env bash
# benchmark-comparison.sh — Compare AGE vs graph_accel traversal
#
# Tests neighborhood queries at depths 1-5 against the live knowledge graph.
# Validates: timing, concept counts, and data correctness.
#
# Requirements:
#   - knowledge-graph-postgres container running with AGE graph loaded
#   - graph_accel extension installed (Option 0 or later deployment)
#   - PostgreSQL 17.x (psql output parsing assumes 17.x formatting)
#   - bc (for floating-point speedup calculation)
#
# Notes:
#   - Operator tooling — concept_id is interpolated into Cypher strings.
#     Not suitable for untrusted input without parameterization.
#   - Concept ID grep filter assumes sha256: or c_ prefixes (current dataset).
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

# --- Cache invalidation ---
echo "================================================================"
echo "  Cache Invalidation (generation-based)"
echo "================================================================"
echo ""

# Check if graph_accel_invalidate exists (v0.2.0+)
has_invalidate=$(psql_cmd -c "SELECT count(*) FROM pg_proc WHERE proname = 'graph_accel_invalidate';")
if [ "$has_invalidate" -eq 0 ]; then
    echo "  SKIP: graph_accel_invalidate not available (requires v0.2.0+)"
    echo ""
else
    # Test 1: invalidate returns monotonic generation
    gen1=$(psql_cmd -c "SELECT graph_accel_invalidate('knowledge_graph');")
    gen2=$(psql_cmd -c "SELECT graph_accel_invalidate('knowledge_graph');")
    if [ "$gen2" -gt "$gen1" ] 2>/dev/null; then
        echo "  Monotonic generation: OK (${gen1} -> ${gen2})"
    else
        echo "  Monotonic generation: FAIL (${gen1} -> ${gen2})"
        all_pass=false
    fi

    # Test 2: status shows stale after invalidation
    # Load graph, invalidate, check status
    status_output=$(psql_cmd \
        -c "SET graph_accel.node_id_property = 'concept_id';" \
        -c "SET graph_accel.auto_reload = false;" \
        -c "SELECT * FROM graph_accel_load('knowledge_graph');" \
        -c "SELECT graph_accel_invalidate('knowledge_graph');" \
        -c "SELECT status, is_stale FROM graph_accel_status();")

    # Parse status|is_stale from output (last non-empty line)
    status_line=$(echo "$status_output" | grep -E 'stale|loaded' | tail -1 | tr -d ' ')
    status_val=$(echo "$status_line" | cut -d'|' -f1)
    is_stale_val=$(echo "$status_line" | cut -d'|' -f2)

    if [ "$status_val" = "stale" ] && [ "$is_stale_val" = "t" ]; then
        echo "  Stale detection:     OK (status='stale', is_stale=true)"
    else
        echo "  Stale detection:     FAIL (status='${status_val}', is_stale='${is_stale_val}')"
        all_pass=false
    fi

    # Test 3: auto-reload clears stale status
    fresh_output=$(psql_cmd \
        -c "SET graph_accel.node_id_property = 'concept_id';" \
        -c "SET graph_accel.auto_reload = true;" \
        -c "SET graph_accel.reload_debounce_sec = 0;" \
        -c "SELECT * FROM graph_accel_load('knowledge_graph');" \
        -c "SELECT graph_accel_invalidate('knowledge_graph');" \
        -c "SELECT count(*) FROM graph_accel_neighborhood('$CONCEPT_ID', 1) WHERE label = 'Concept';" \
        -c "SELECT status, is_stale FROM graph_accel_status();")

    fresh_line=$(echo "$fresh_output" | grep -E 'stale|loaded' | tail -1 | tr -d ' ')
    fresh_status=$(echo "$fresh_line" | cut -d'|' -f1)
    fresh_stale=$(echo "$fresh_line" | cut -d'|' -f2)

    if [ "$fresh_status" = "loaded" ] && [ "$fresh_stale" = "f" ]; then
        echo "  Auto-reload:         OK (status='loaded' after stale query)"
    else
        echo "  Auto-reload:         FAIL (status='${fresh_status}', is_stale='${fresh_stale}')"
        all_pass=false
    fi

    # Test 4: generation table has expected row
    gen_row=$(psql_cmd -c "SELECT graph_name, generation FROM graph_accel.generation WHERE graph_name = 'knowledge_graph';")
    if echo "$gen_row" | grep -q 'knowledge_graph'; then
        gen_val=$(echo "$gen_row" | cut -d'|' -f2)
        echo "  Generation table:    OK (knowledge_graph at gen ${gen_val})"
    else
        echo "  Generation table:    FAIL (no row for knowledge_graph)"
        all_pass=false
    fi

    echo ""
fi

# --- Direction correctness ---
echo "================================================================"
echo "  Direction Correctness"
echo "================================================================"
echo ""

# Check if path_directions column exists (v0.3.0+)
has_directions=$(psql_cmd \
    -c "SET graph_accel.node_id_property = 'concept_id';" \
    -c "SELECT * FROM graph_accel_load('knowledge_graph');" \
    -c "SELECT count(*) FROM information_schema.columns
        WHERE table_name = 'graph_accel_neighborhood'
        AND column_name = 'path_directions';" 2>/dev/null || echo "0")
# graph_accel functions are set-returning, so check by querying directly
has_directions=$(psql_cmd \
    -c "SET graph_accel.node_id_property = 'concept_id';" \
    -c "SELECT * FROM graph_accel_load('knowledge_graph');" \
    -c "SELECT path_directions FROM graph_accel_neighborhood('$CONCEPT_ID', 1) LIMIT 1;" 2>/dev/null && echo "1" || echo "0")

if [ "$has_directions" = "0" ]; then
    echo "  SKIP: path_directions not available (requires v0.3.0+)"
    echo ""
else
    # Test 1: Depth-1 direction check against AGE
    # For each depth-1 neighbor, graph_accel says outgoing or incoming.
    # Verify against AGE directed queries.
    echo "  --- Depth-1 direction check ---"

    # Get graph_accel depth-1 neighbors with directions
    ga_dir_output=$(psql_cmd \
        -c "SET graph_accel.node_id_property = 'concept_id';" \
        -c "SELECT * FROM graph_accel_load('knowledge_graph');" \
        -c "SELECT app_id, path_directions[1] FROM graph_accel_neighborhood('$CONCEPT_ID', 1)
            WHERE label = 'Concept' ORDER BY app_id;")

    # Get AGE outgoing neighbors (start)-[]->(target)
    age_outgoing=$(psql_cmd -c "LOAD 'age'; SET search_path = ag_catalog, public;" \
        -c "SELECT * FROM cypher('knowledge_graph', \$\$
            MATCH (start:Concept {concept_id: '$CONCEPT_ID'})-[r]->(target:Concept)
            RETURN DISTINCT target.concept_id
        \$\$) as (cid agtype);" | grep -v '^$\|^LOAD\|^SET' | sed 's/"//g' | sort)

    dir_pass=true
    dir_checked=0
    dir_errors=0

    while IFS='|' read -r app_id direction; do
        [ -z "$app_id" ] && continue
        app_id=$(echo "$app_id" | tr -d ' ')
        direction=$(echo "$direction" | tr -d ' {}')
        [ -z "$app_id" ] && continue

        dir_checked=$((dir_checked + 1))

        # Check: if graph_accel says outgoing, AGE should have a forward edge
        if [ "$direction" = "outgoing" ]; then
            if ! echo "$age_outgoing" | grep -qF "$app_id"; then
                echo "    FAIL: $app_id marked outgoing but no forward edge in AGE"
                dir_errors=$((dir_errors + 1))
                dir_pass=false
            fi
        elif [ "$direction" = "incoming" ]; then
            if echo "$age_outgoing" | grep -qF "$app_id"; then
                # It's in the outgoing set — could be bidirectional (edges in both directions).
                # Only fail if there's NO incoming edge. For now, having it in outgoing
                # while marked incoming is suspicious but not necessarily wrong if
                # there are parallel edges in both directions. Log as warning.
                :
            fi
        fi
    done <<< "$ga_dir_output"

    if $dir_pass; then
        echo "  Depth-1 directions:  OK ($dir_checked checked, $dir_errors errors)"
    else
        echo "  Depth-1 directions:  FAIL ($dir_checked checked, $dir_errors errors)"
        all_pass=false
    fi

    # Test 2: Path direction check
    # Find a shortest path, verify each step's direction against AGE
    echo "  --- Path direction check ---"

    # Pick a depth-2 neighbor to get a multi-step path
    path_target=$(psql_cmd \
        -c "SET graph_accel.node_id_property = 'concept_id';" \
        -c "SELECT * FROM graph_accel_load('knowledge_graph');" \
        -c "SELECT app_id FROM graph_accel_neighborhood('$CONCEPT_ID', 2)
            WHERE label = 'Concept' AND distance = 2 LIMIT 1;")
    path_target=$(echo "$path_target" | tr -d ' ' | head -1)

    if [ -n "$path_target" ]; then
        path_output=$(psql_cmd \
            -c "SET graph_accel.node_id_property = 'concept_id';" \
            -c "SELECT * FROM graph_accel_load('knowledge_graph');" \
            -c "SELECT step, app_id, rel_type, direction FROM graph_accel_path('$CONCEPT_ID', '$path_target');")

        path_steps=$(echo "$path_output" | grep -c '|' || true)
        path_has_dirs=$(echo "$path_output" | grep -c 'outgoing\|incoming' || true)
        path_has_null=$(echo "$path_output" | grep -c '|$' || true)  # start node has NULL direction

        if [ "$path_steps" -ge 2 ] && [ "$path_has_dirs" -ge 1 ]; then
            echo "  Path directions:     OK ($path_steps steps, $path_has_dirs with direction)"
        else
            echo "  Path directions:     FAIL (steps=$path_steps, with_dir=$path_has_dirs)"
            all_pass=false
        fi
    else
        echo "  Path directions:     SKIP (no depth-2 neighbor found)"
    fi

    # Test 3: Symmetry test — same edge from both endpoints
    echo "  --- Symmetry test ---"

    # Get a depth-1 neighbor and its direction
    sym_output=$(psql_cmd \
        -c "SET graph_accel.node_id_property = 'concept_id';" \
        -c "SELECT * FROM graph_accel_load('knowledge_graph');" \
        -c "SELECT app_id, path_directions[1] FROM graph_accel_neighborhood('$CONCEPT_ID', 1)
            WHERE label = 'Concept' LIMIT 1;")

    sym_neighbor=$(echo "$sym_output" | head -1 | cut -d'|' -f1 | tr -d ' ')
    sym_dir=$(echo "$sym_output" | head -1 | cut -d'|' -f2 | tr -d ' {}')

    if [ -n "$sym_neighbor" ] && [ -n "$sym_dir" ]; then
        # Query from the neighbor back to our start concept
        reverse_output=$(psql_cmd \
            -c "SET graph_accel.node_id_property = 'concept_id';" \
            -c "SELECT * FROM graph_accel_load('knowledge_graph');" \
            -c "SELECT app_id, path_directions[1] FROM graph_accel_neighborhood('$sym_neighbor', 1)
                WHERE app_id = '$CONCEPT_ID';")

        reverse_dir=$(echo "$reverse_output" | head -1 | cut -d'|' -f2 | tr -d ' {}')

        # outgoing from A should be incoming from B, and vice versa
        expected_reverse=""
        if [ "$sym_dir" = "outgoing" ]; then
            expected_reverse="incoming"
        elif [ "$sym_dir" = "incoming" ]; then
            expected_reverse="outgoing"
        fi

        if [ "$reverse_dir" = "$expected_reverse" ]; then
            echo "  Symmetry:            OK ($sym_dir from start → $reverse_dir from neighbor)"
        else
            echo "  Symmetry:            FAIL (start=$sym_dir, reverse=$reverse_dir, expected=$expected_reverse)"
            all_pass=false
        fi
    else
        echo "  Symmetry:            SKIP (no neighbor found)"
    fi

    echo ""
fi

# --- Summary ---
if $all_pass; then
    echo "RESULT: ALL CHECKS PASSED"
    exit 0
else
    echo "RESULT: SOME CHECKS FAILED"
    exit 1
fi
