#!/usr/bin/env bash
# core-tests.sh — Validate graph-accel core engine without PostgreSQL
#
# Runs unit tests (including direction tracking) and a quick smoke test
# of all 6 topology generators at reduced scale.
#
# No containers, no database, no extension — just cargo.
#
# Usage:
#   ./graph-accel/tests/core-tests.sh           # default (10,000 nodes)
#   ./graph-accel/tests/core-tests.sh 100000    # custom scale

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

usage() {
    echo "Usage: $(basename "$0") [OPTIONS] [NODE_COUNT]"
    echo ""
    echo "Validate graph-accel core engine without PostgreSQL."
    echo "Runs unit tests and benchmarks all 6 topology generators."
    echo ""
    echo "Arguments:"
    echo "  NODE_COUNT    Nodes per topology (default: 10000)"
    echo ""
    echo "Options:"
    echo "  -h, --help    Show this help"
    echo ""
    echo "Examples:"
    echo "  $(basename "$0")            # 10,000 nodes (quick)"
    echo "  $(basename "$0") 100000     # 100k nodes"
    echo "  $(basename "$0") 1000000    # 1M nodes (takes a few seconds)"
}

NODE_COUNT=10000
for arg in "$@"; do
    case "$arg" in
        -h|--help|help)
            usage
            exit 0
            ;;
        *)
            if [[ "$arg" =~ ^[0-9]+$ ]]; then
                NODE_COUNT="$arg"
            else
                echo "Unknown argument: $arg"
                usage
                exit 1
            fi
            ;;
    esac
done

echo "================================================================"
echo "  graph-accel core tests (no PostgreSQL)"
echo "================================================================"
echo ""

all_pass=true

# --- Unit tests ---
echo "--- Unit tests (cargo test) ---"
echo ""

if cargo test --manifest-path "$SCRIPT_DIR/Cargo.toml" -p graph-accel-core 2>&1; then
    echo ""
    echo "  Unit tests: PASS"
else
    echo ""
    echo "  Unit tests: FAIL"
    all_pass=false
fi

echo ""

# --- Bench binary build ---
echo "--- Bench binary (release build) ---"
echo ""

if cargo build --manifest-path "$SCRIPT_DIR/Cargo.toml" --release -p graph-accel-bench 2>&1; then
    echo ""
    echo "  Build: PASS"
else
    echo ""
    echo "  Build: FAIL"
    all_pass=false
    echo ""
    echo "RESULT: BUILD FAILED"
    exit 1
fi

echo ""

# --- Topology smoke tests ---
echo "================================================================"
echo "  Topology smoke tests ($NODE_COUNT nodes each)"
echo "================================================================"
echo ""

BENCH_BIN="$SCRIPT_DIR/target/release/graph-accel-bench"

topologies=("lsystem" "scalefree" "smallworld" "random" "barbell" "dla")

for topo in "${topologies[@]}"; do
    echo "--- $topo ---"
    if output=$("$BENCH_BIN" "$topo" "$NODE_COUNT" 2>&1); then
        # Verify we got timing output and direction check passed
        if echo "$output" | grep -qE '[0-9]+\.[0-9]+ms'; then
            echo "$output" | head -25
            if echo "$output" | grep -q 'Direction check: FAIL'; then
                echo "  Result: FAIL (direction check failed)"
                all_pass=false
            else
                echo "  Result: PASS"
            fi
        else
            echo "$output"
            echo "  Result: FAIL (no timing output)"
            all_pass=false
        fi
    else
        echo "  Result: FAIL (exit code $?)"
        all_pass=false
    fi
    echo ""
done

# --- Direction spot-check ---
# The bench binary uses bfs_neighborhood and shortest_path which now return
# direction data. The unit tests validate correctness. Here we just confirm
# the binary runs without panicking on all topologies (above), which exercises
# the updated neighbors_all() return type through the full code path.

# --- Summary ---
echo "================================================================"
if $all_pass; then
    echo "  RESULT: ALL CHECKS PASSED"
    exit 0
else
    echo "  RESULT: SOME CHECKS FAILED"
    exit 1
fi
