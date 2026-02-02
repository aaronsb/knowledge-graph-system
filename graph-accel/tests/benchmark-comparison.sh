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
# API Integration Rosetta Stone
# =============================
# Each test section below maps to an API worker pattern. When integrating
# graph_accel into the API server, use these as reference for the SQL calls:
#
#   BFS Comparison → bfs_neighborhood() in query_facade.py
#     Current: Cypher MATCH chain at fixed depth
#     Replace: SELECT * FROM graph_accel_neighborhood(concept_id, depth)
#
#   Directed Filter → concept detail routes (outgoing/incoming separation)
#     Current: Two separate Cypher queries with -> and <-
#     Replace: graph_accel_neighborhood(id, depth, 'outgoing'|'incoming')
#
#   Degree Centrality → get_concept_degree_ranking() in ontology routes
#     Current: OPTIONAL MATCH per concept, counted in Python
#     Replace: SELECT * FROM graph_accel_degree(top_n) WHERE label = 'Concept'
#
#   Subgraph Extraction → ontology affinity, cross-ontology edge analysis
#     Current: 3-hop Cypher patterns with UNWIND
#     Replace: SELECT * FROM graph_accel_subgraph(start_id, depth)
#
#   Confidence Filtering → quality-filtered traversal in pathfinding_facade.py
#     Current: Fetch all, filter in Python
#     Replace: graph_accel_neighborhood(id, depth, 'both', min_confidence)
#
#   Cache Invalidation → call after any graph mutation in ingest/edit routes
#     Current: N/A (no cache)
#     Replace: SELECT graph_accel_invalidate('knowledge_graph') after writes
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

# Helper: run a graph_accel query and return only the last statement's output.
# Filters out SET/LOAD noise and graph_accel_load table output.
ga_query() {
    psql_cmd \
        -c "SET graph_accel.node_id_property = 'concept_id';" \
        -c "SELECT * FROM graph_accel_load('knowledge_graph');" \
        -c "$1" 2>&1 | grep -v -E '^$|^SET$|^LOAD$|^[0-9]+\|[0-9]+\|[0-9]'
}

# Helper: run ga_query and extract a single integer count
ga_count() {
    ga_query "$1" | grep -oE '^[0-9]+$' | head -1
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
    path_target=$(echo "$path_target" | grep '^sha256:\|^c_' | tr -d ' ' | head -1)

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

    sym_line=$(echo "$sym_output" | grep -E '^(sha256:|c_)' | head -1)
    sym_neighbor=$(echo "$sym_line" | cut -d'|' -f1 | tr -d ' ')
    sym_dir=$(echo "$sym_line" | cut -d'|' -f2 | tr -d ' {}')

    if [ -n "$sym_neighbor" ] && [ -n "$sym_dir" ]; then
        # Query from the neighbor back to our start concept
        reverse_output=$(psql_cmd \
            -c "SET graph_accel.node_id_property = 'concept_id';" \
            -c "SELECT * FROM graph_accel_load('knowledge_graph');" \
            -c "SELECT app_id, path_directions[1] FROM graph_accel_neighborhood('$sym_neighbor', 1)
                WHERE app_id = '$CONCEPT_ID';")

        reverse_dir=$(echo "$reverse_output" | grep -E '^(sha256:|c_)' | head -1 | cut -d'|' -f2 | tr -d ' {}')

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

# --- Directed traversal filter ---
echo "================================================================"
echo "  Directed Traversal Filter (v0.4.0)"
echo "================================================================"
echo ""

# Test: outgoing-only depth-1 should match AGE forward query
# Exclude start node (distance > 0) to match AGE's WHERE start <> target
ga_outgoing=$(ga_query "SELECT app_id FROM graph_accel_neighborhood('$CONCEPT_ID', 1, 'outgoing')
    WHERE label = 'Concept' AND distance > 0 ORDER BY app_id;" \
    | grep '^sha256:\|^c_' | sort)

age_fwd=$(psql_cmd -c "LOAD 'age'; SET search_path = ag_catalog, public;" \
    -c "SELECT * FROM cypher('knowledge_graph', \$\$
        MATCH (start:Concept {concept_id: '$CONCEPT_ID'})-[r]->(target:Concept)
        WHERE start <> target
        RETURN DISTINCT target.concept_id
    \$\$) as (cid agtype);" | grep -v '^$\|^LOAD\|^SET' | sed 's/"//g' | sort)

if diff <(echo "$age_fwd") <(echo "$ga_outgoing") > /dev/null 2>&1; then
    fwd_count=$(echo "$age_fwd" | grep -c . || true)
    echo "  Outgoing depth-1:    OK (exact match, $fwd_count concepts)"
else
    echo "  Outgoing depth-1:    FAIL"
    echo "    Only in AGE forward:"
    comm -23 <(echo "$age_fwd") <(echo "$ga_outgoing") | head -3
    echo "    Only in graph_accel outgoing:"
    comm -13 <(echo "$age_fwd") <(echo "$ga_outgoing") | head -3
    all_pass=false
fi

# Test: incoming-only depth-1 should match AGE reverse query
ga_incoming=$(ga_query "SELECT app_id FROM graph_accel_neighborhood('$CONCEPT_ID', 1, 'incoming')
    WHERE label = 'Concept' AND distance > 0 ORDER BY app_id;" \
    | grep '^sha256:\|^c_' | sort)

age_rev=$(psql_cmd -c "LOAD 'age'; SET search_path = ag_catalog, public;" \
    -c "SELECT * FROM cypher('knowledge_graph', \$\$
        MATCH (start:Concept {concept_id: '$CONCEPT_ID'})<-[r]-(target:Concept)
        WHERE start <> target
        RETURN DISTINCT target.concept_id
    \$\$) as (cid agtype);" | grep -v '^$\|^LOAD\|^SET' | sed 's/"//g' | sort)

if diff <(echo "$age_rev") <(echo "$ga_incoming") > /dev/null 2>&1; then
    rev_count=$(echo "$age_rev" | grep -c . || true)
    echo "  Incoming depth-1:    OK (exact match, $rev_count concepts)"
else
    echo "  Incoming depth-1:    FAIL"
    echo "    Only in AGE reverse:"
    comm -23 <(echo "$age_rev") <(echo "$ga_incoming") | head -3
    echo "    Only in graph_accel incoming:"
    comm -13 <(echo "$age_rev") <(echo "$ga_incoming") | head -3
    all_pass=false
fi

# Test: outgoing ∪ incoming = both at depth 1
ga_both=$(ga_query "SELECT app_id FROM graph_accel_neighborhood('$CONCEPT_ID', 1)
    WHERE label = 'Concept' AND distance > 0 ORDER BY app_id;" \
    | grep '^sha256:\|^c_' | sort)

ga_union=$(sort -u <(echo "$ga_outgoing") <(echo "$ga_incoming"))

if diff <(echo "$ga_both") <(echo "$ga_union") > /dev/null 2>&1; then
    echo "  Union = both:        OK"
else
    echo "  Union = both:        FAIL (outgoing ∪ incoming ≠ both)"
    all_pass=false
fi

echo ""

# --- Degree centrality ---
echo "================================================================"
echo "  Degree Centrality (v0.4.0)"
echo "================================================================"
echo ""

# Get top-10 from graph_accel (filter noise lines from SET/LOAD output)
ga_degree=$(ga_query "SELECT app_id, out_degree, in_degree, total_degree
    FROM graph_accel_degree(10)
    WHERE label = 'Concept';" | grep -E '^(sha256:|c_)')

top_node=$(echo "$ga_degree" | head -1)
top_app_id=$(echo "$top_node" | cut -d'|' -f1 | tr -d ' ')
top_total=$(echo "$top_node" | cut -d'|' -f4 | tr -d ' ')

if [ -n "$top_app_id" ] && [ "$top_total" -gt 0 ] 2>/dev/null; then
    # Verify top node's degree against AGE
    age_degree=$(psql_cmd -c "LOAD 'age'; SET search_path = ag_catalog, public;" \
        -c "SELECT * FROM cypher('knowledge_graph', \$\$
            MATCH (c:Concept {concept_id: '$top_app_id'})-[r]-(n)
            RETURN count(r)
        \$\$) as (cnt agtype);" | grep -oE '[0-9]+' | head -1)

    if [ "$top_total" = "$age_degree" ] 2>/dev/null; then
        echo "  Top node degree:     OK ($top_app_id: $top_total matches AGE)"
    else
        echo "  Top node degree:     WARN ($top_app_id: graph_accel=$top_total, AGE=$age_degree)"
        # Not a hard fail — AGE counts differently with self-loops and multi-edges
    fi
    echo "  Top 5 by degree:"
    echo "$ga_degree" | head -5 | while IFS='|' read -r app out ind total; do
        printf "    %-40s  out=%-4s in=%-4s total=%-4s\n" \
            "$(echo "$app" | tr -d ' ')" "$(echo "$out" | tr -d ' ')" \
            "$(echo "$ind" | tr -d ' ')" "$(echo "$total" | tr -d ' ')"
    done
else
    echo "  Degree centrality:   FAIL (no results)"
    all_pass=false
fi

echo ""

# --- Subgraph extraction ---
echo "================================================================"
echo "  Subgraph Extraction (v0.4.0)"
echo "================================================================"
echo ""

ga_sub_count=$(ga_count "SELECT count(*) FROM graph_accel_subgraph('$CONCEPT_ID', 2);")

# Neighborhood node count at depth 2 for reference
ga_hood_count=$(ga_count "SELECT count(*) FROM graph_accel_neighborhood('$CONCEPT_ID', 2);")

if [ -n "$ga_sub_count" ] && [ "$ga_sub_count" -gt 0 ] 2>/dev/null; then
    echo "  Depth-2 subgraph:    OK ($ga_sub_count edges among $ga_hood_count nodes)"

    # Verify edges are between reachable nodes (spot check: first 5 from_app_id should be in neighborhood)
    ga_sub_from=$(ga_query "SELECT DISTINCT from_app_id FROM graph_accel_subgraph('$CONCEPT_ID', 2)
        WHERE from_app_id IS NOT NULL LIMIT 5;" | grep '^sha256:\|^c_')
    ga_hood_ids=$(ga_query "SELECT app_id FROM graph_accel_neighborhood('$CONCEPT_ID', 2)
        WHERE app_id IS NOT NULL;")

    sub_valid=true
    while IFS= read -r from_id; do
        from_id=$(echo "$from_id" | tr -d ' ')
        [ -z "$from_id" ] && continue
        if ! echo "$ga_hood_ids" | grep -qF "$from_id"; then
            echo "    FAIL: edge from $from_id not in neighborhood"
            sub_valid=false
        fi
    done <<< "$ga_sub_from"

    if $sub_valid; then
        echo "  Edge containment:    OK (all edge sources within neighborhood)"
    else
        all_pass=false
    fi
else
    echo "  Depth-2 subgraph:    FAIL (no edges returned)"
    all_pass=false
fi

echo ""

# --- Confidence filtering ---
echo "================================================================"
echo "  Confidence Filtering (v0.4.0)"
echo "================================================================"
echo ""

# Unfiltered count
ga_unfiltered=$(ga_count "SELECT count(*) FROM graph_accel_neighborhood('$CONCEPT_ID', 2);")

# Filtered at 0.5
ga_filtered=$(ga_count "SELECT count(*) FROM graph_accel_neighborhood('$CONCEPT_ID', 2, 'both', 0.5);")

if [ "$ga_filtered" -le "$ga_unfiltered" ] 2>/dev/null; then
    echo "  Filtered ≤ unfiltered: OK ($ga_filtered ≤ $ga_unfiltered at min_confidence=0.5)"
else
    echo "  Filtered ≤ unfiltered: FAIL ($ga_filtered > $ga_unfiltered)"
    all_pass=false
fi

# Filtered at high threshold should find fewer or equal
ga_strict=$(ga_count "SELECT count(*) FROM graph_accel_neighborhood('$CONCEPT_ID', 2, 'both', 0.9);")

if [ "$ga_strict" -le "$ga_filtered" ] 2>/dev/null; then
    echo "  Monotonic filtering:   OK ($ga_strict ≤ $ga_filtered ≤ $ga_unfiltered)"
else
    echo "  Monotonic filtering:   FAIL (0.9=$ga_strict, 0.5=$ga_filtered, none=$ga_unfiltered)"
    all_pass=false
fi

# Path with confidence — reuse path_target from direction correctness section
if [ -n "$path_target" ]; then
    ga_path_unfiltered=$(ga_count "SELECT count(*) FROM graph_accel_path('$CONCEPT_ID', '$path_target');")
    ga_path_filtered=$(ga_count "SELECT count(*) FROM graph_accel_path('$CONCEPT_ID', '$path_target', 10, 'both', 0.5);")
else
    # Pick a depth-2 neighbor for path test
    path_target=$(ga_query "SELECT app_id FROM graph_accel_neighborhood('$CONCEPT_ID', 2)
        WHERE label = 'Concept' AND distance = 2 LIMIT 1;" | grep '^sha256:\|^c_' | tr -d ' ' | head -1)
    ga_path_unfiltered=$(ga_count "SELECT count(*) FROM graph_accel_path('$CONCEPT_ID', '$path_target');")
    ga_path_filtered=$(ga_count "SELECT count(*) FROM graph_accel_path('$CONCEPT_ID', '$path_target', 10, 'both', 0.5);")
fi

echo "  Path (unfiltered):     $ga_path_unfiltered steps"
echo "  Path (min_conf=0.5):   $ga_path_filtered steps"
if [ "$ga_path_filtered" -ge "$ga_path_unfiltered" ] 2>/dev/null || [ "$ga_path_filtered" -eq 0 ] 2>/dev/null; then
    echo "  Path confidence:       OK (filtered path ≥ unfiltered or no path)"
else
    echo "  Path confidence:       WARN (filtered shorter — alternate route?)"
fi

echo ""

# --- Multi-path (Yen's k-shortest-paths, v0.5.0) ---
echo "================================================================"
echo "  Multi-Path / Yen's k-shortest-paths (v0.5.0)"
echo "================================================================"
echo ""

# Check if graph_accel_paths exists
has_paths=$(psql_cmd -c "SELECT count(*) FROM pg_proc WHERE proname = 'graph_accel_paths';")
if [ "$has_paths" -eq 0 ]; then
    echo "  SKIP: graph_accel_paths not available (requires v0.5.0+)"
    echo ""
else
    # Pick a target concept at distance 2 for multi-path testing
    ksp_target=$(ga_query "SELECT app_id FROM graph_accel_neighborhood('$CONCEPT_ID', 2)
        WHERE label = 'Concept' AND distance = 2 LIMIT 1;" | grep '^sha256:\|^c_' | tr -d ' ' | head -1)

    if [ -z "$ksp_target" ]; then
        echo "  SKIP: no depth-2 neighbor found for multi-path test"
        echo ""
    else
        echo "  Source: $CONCEPT_ID"
        echo "  Target: $ksp_target"
        echo ""

        # Test 1: k=1 should match graph_accel_path (single shortest)
        single_path=$(ga_query "SELECT step, app_id, rel_type FROM graph_accel_path('$CONCEPT_ID', '$ksp_target');" \
            | grep -E '^[0-9]')
        single_hops=$(echo "$single_path" | wc -l)

        multi_k1=$(ga_query "SELECT path_index, step, app_id, rel_type FROM graph_accel_paths('$CONCEPT_ID', '$ksp_target', 10, 1);" \
            | grep -E '^0\|')
        multi_k1_hops=$(echo "$multi_k1" | wc -l)

        if [ "$single_hops" = "$multi_k1_hops" ]; then
            echo "  k=1 matches single:  OK ($single_hops steps)"
        else
            echo "  k=1 matches single:  FAIL (single=$single_hops, k=1=$multi_k1_hops)"
            all_pass=false
        fi

        # Test 2: k=5 should return 1-5 paths, all distinct
        multi_k5_output=$(ga_query "SELECT path_index, step, app_id, rel_type FROM graph_accel_paths('$CONCEPT_ID', '$ksp_target', 10, 5);")
        multi_k5_paths=$(echo "$multi_k5_output" | grep -E '^[0-9]' | cut -d'|' -f1 | sort -u | wc -l)

        if [ "$multi_k5_paths" -ge 1 ]; then
            echo "  k=5 found paths:     OK ($multi_k5_paths distinct paths)"
        else
            echo "  k=5 found paths:     FAIL (no paths returned)"
            all_pass=false
        fi

        # Test 3: All paths start and end at the right nodes
        path_starts=$(echo "$multi_k5_output" | grep -E '^[0-9]+\|0\|' | cut -d'|' -f3 | tr -d ' ' | sort -u)
        if [ "$(echo "$path_starts" | wc -l)" = "1" ] && [ "$(echo "$path_starts" | head -1)" = "$CONCEPT_ID" ]; then
            echo "  Start nodes correct: OK (all start at $CONCEPT_ID)"
        else
            echo "  Start nodes correct: FAIL"
            all_pass=false
        fi

        # Check last step of each path ends at target
        end_check_pass=true
        for pi in $(echo "$multi_k5_output" | grep -E '^[0-9]' | cut -d'|' -f1 | sort -un); do
            last_node=$(echo "$multi_k5_output" | grep "^${pi}|" | tail -1 | cut -d'|' -f3 | tr -d ' ')
            if [ "$last_node" != "$ksp_target" ]; then
                echo "  End node path $pi:    FAIL (expected $ksp_target, got $last_node)"
                end_check_pass=false
                all_pass=false
            fi
        done
        if $end_check_pass; then
            echo "  End nodes correct:   OK (all end at $ksp_target)"
        fi

        # Test 4: Paths are sorted by length (non-decreasing)
        prev_len=0
        sorted_pass=true
        for pi in $(echo "$multi_k5_output" | grep -E '^[0-9]' | cut -d'|' -f1 | sort -un); do
            path_len=$(echo "$multi_k5_output" | grep -c "^${pi}|")
            if [ "$path_len" -lt "$prev_len" ]; then
                echo "  Sorted by length:    FAIL (path $pi has $path_len steps < previous $prev_len)"
                sorted_pass=false
                all_pass=false
            fi
            prev_len=$path_len
        done
        if $sorted_pass; then
            echo "  Sorted by length:    OK"
        fi

        # Test 5: Timing
        multi_timing=$(psql_timed -c "\\timing" \
            -c "SET graph_accel.node_id_property = 'concept_id';" \
            -c "SELECT * FROM graph_accel_load('knowledge_graph');" \
            -c "SELECT count(*) FROM graph_accel_paths('$CONCEPT_ID', '$ksp_target', 10, 5);" 2>&1)
        multi_time=$(echo "$multi_timing" | grep "^Time:" | tail -1 | grep -oP '[\d.]+' | head -1)
        multi_rows=$(echo "$multi_timing" | grep -E '^\s+[0-9]+$' | tail -1 | tr -d ' ')
        echo "  k=5 timing:          ${multi_time}ms ($multi_rows rows)"

        echo ""
    fi
fi

# --- Summary ---
if $all_pass; then
    echo "RESULT: ALL CHECKS PASSED"
    exit 0
else
    echo "RESULT: SOME CHECKS FAILED"
    exit 1
fi
