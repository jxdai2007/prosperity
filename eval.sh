#!/bin/bash
# Immutable evaluation script for IMC Prosperity 3 autoresearch
# Tests strategy archetypes across their natural rounds + stress tests
# DO NOT MODIFY during experiments

set -uo pipefail

TRADER_FILE="trader.py"
TIMEOUT_SEC=90

echo "=== Eval Start ==="
echo "timestamp: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
COMMIT=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")
echo "commit: $COMMIT"

# Create temp dir for per-round outputs
TMPDIR=$(mktemp -d)
trap "rm -rf $TMPDIR" EXIT

CRASH=0

###############################################################################
# ARCHETYPE 1: Market Making (Round 1 — RESIN, KELP, SQUID_INK only)
###############################################################################
echo ""
echo "=== Archetype: Market Making (Round 1) ==="
R1_OUT=$(timeout $TIMEOUT_SEC prosperity3bt "$TRADER_FILE" 1 --no-out --merge-pnl --no-progress 2>&1) || true
echo "$R1_OUT" | tail -8
R1_PROFIT=$(echo "$R1_OUT" | grep "^Total profit:" | tail -1 | sed 's/Total profit: //; s/,//g')
if [ -z "$R1_PROFIT" ]; then
    echo "mm_profit: CRASH"
    R1_PROFIT=0
    CRASH=1
else
    echo "mm_profit: $R1_PROFIT"
fi

###############################################################################
# ARCHETYPE 2: Stat Arb (Round 2 — baskets + components added)
###############################################################################
echo ""
echo "=== Archetype: Stat Arb (Round 2) ==="
R2_OUT=$(timeout $TIMEOUT_SEC prosperity3bt "$TRADER_FILE" 2 --no-out --merge-pnl --no-progress 2>&1) || true
echo "$R2_OUT" | tail -12

# Extract basket-related profits (CROISSANTS, JAMS, DJEMBES, PB1, PB2)
# We need the final-day per-product breakdown
R2_PROFIT=$(echo "$R2_OUT" | grep "^Total profit:" | tail -1 | sed 's/Total profit: //; s/,//g')
if [ -z "$R2_PROFIT" ]; then
    echo "statarb_profit: CRASH"
    R2_PROFIT=0
    CRASH=1
else
    # Subtract MM products to isolate basket contribution
    # (R2 includes RESIN/KELP/SQUID too)
    echo "statarb_total_profit: $R2_PROFIT"
fi

###############################################################################
# ARCHETYPE 3: Options (Round 3 — volcanic rock + vouchers added)
###############################################################################
echo ""
echo "=== Archetype: Options (Round 3) ==="
R3_OUT=$(timeout $TIMEOUT_SEC prosperity3bt "$TRADER_FILE" 3 --no-out --merge-pnl --no-progress 2>&1) || true
echo "$R3_OUT" | tail -20
R3_PROFIT=$(echo "$R3_OUT" | grep "^Total profit:" | tail -1 | sed 's/Total profit: //; s/,//g')
if [ -z "$R3_PROFIT" ]; then
    echo "options_profit: CRASH"
    R3_PROFIT=0
    CRASH=1
else
    echo "options_total_profit: $R3_PROFIT"
fi

###############################################################################
# ARCHETYPE 4+5: Conversion Arb + Insider (Round 5 — all products, revealed IDs)
###############################################################################
echo ""
echo "=== Archetype: Full (Round 5 — conversion + insider + all) ==="
R5_OUT=$(timeout $TIMEOUT_SEC prosperity3bt "$TRADER_FILE" 5 --no-out --merge-pnl --no-progress 2>&1) || true
echo "$R5_OUT" | tail -20
R5_PROFIT=$(echo "$R5_OUT" | grep "^Total profit:" | tail -1 | sed 's/Total profit: //; s/,//g')
if [ -z "$R5_PROFIT" ]; then
    echo "full_profit: CRASH"
    R5_PROFIT=0
    CRASH=1
else
    echo "full_profit: $R5_PROFIT"
fi

###############################################################################
# STRESS TEST: Round 5 with --match-trades worse (adversarial fills)
###############################################################################
echo ""
echo "=== Stress: Round 5 worse fills ==="
R5W_OUT=$(timeout $TIMEOUT_SEC prosperity3bt "$TRADER_FILE" 5 --no-out --merge-pnl --no-progress --match-trades worse 2>&1) || true
echo "$R5W_OUT" | tail -8
R5W_PROFIT=$(echo "$R5W_OUT" | grep "^Total profit:" | tail -1 | sed 's/Total profit: //; s/,//g')
if [ -z "$R5W_PROFIT" ]; then
    echo "stress_profit: CRASH"
    R5W_PROFIT=0
    CRASH=1
else
    echo "stress_profit: $R5W_PROFIT"
fi

###############################################################################
# COMPOSITE SCORE
###############################################################################
echo ""
echo "=== Per-Archetype Scores ==="
echo "mm_profit: $R1_PROFIT"
echo "statarb_profit: $R2_PROFIT"
echo "options_profit: $R3_PROFIT"
echo "full_profit: $R5_PROFIT"
echo "stress_profit: $R5W_PROFIT"
echo "crash_count: $CRASH"

# Compute composite score via Python
python3 compute_score.py "$R1_PROFIT" "$R2_PROFIT" "$R3_PROFIT" "$R5_PROFIT" "$R5W_PROFIT" "$CRASH"
