#!/bin/bash
# Immutable evaluation script for IMC Prosperity 3 trader
# DO NOT MODIFY during experiments

set -euo pipefail

TRADER_FILE="trader.py"
ROUNDS="5"
TIMEOUT_SEC=120

echo "=== Eval Start ==="
echo "timestamp: $(date -u +%Y-%m-%dT%H:%M:%SZ)"

# Derive seed info from git commit hash (for logging)
COMMIT=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")
echo "commit: $COMMIT"

# Run backtester on round 5 (3 days), merge P&L
OUTPUT=$(timeout ${TIMEOUT_SEC} prosperity3bt "$TRADER_FILE" ${ROUNDS} --no-out --merge-pnl --no-progress 2>&1)
EXIT_CODE=$?

echo "$OUTPUT"

if [ $EXIT_CODE -ne 0 ]; then
    echo "=== Eval FAILED (exit code $EXIT_CODE) ==="
    echo "total_profit: CRASH"
    exit 1
fi

# Extract per-day profits
echo ""
echo "=== Per-Day Breakdown ==="
echo "$OUTPUT" | grep "^Round "

# Extract total profit (the final "Total profit:" line from the profit summary)
TOTAL_PROFIT=$(echo "$OUTPUT" | grep "^Total profit:" | tail -1 | sed 's/Total profit: //; s/,//g')

if [ -z "$TOTAL_PROFIT" ]; then
    echo "=== Could not parse total profit ==="
    echo "total_profit: PARSE_ERROR"
    exit 1
fi

# Extract per-product profits from each day for analysis
echo ""
echo "=== Product Analysis ==="
# Last day's per-product breakdown (most recent "Total profit:" section)
echo "$OUTPUT" | grep -E "^[A-Z_]+:" | tail -16

echo ""
echo "=== Final Score ==="
echo "total_profit: $TOTAL_PROFIT"
