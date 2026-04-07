#!/bin/bash
# Immutable evaluation script for IMC Prosperity autoresearch
# Tests strategy archetypes across P3 AND P2 — the trader must handle both
# DO NOT MODIFY during experiments

set -uo pipefail

TRADER_FILE="trader.py"
P2_SUBMISSIONS="/home/researcher/prosperity/imc-prosperity-2/src/submissions"
TIMEOUT_SEC=90

echo "=== Eval Start ==="
echo "timestamp: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
COMMIT=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")
echo "commit: $COMMIT"

P3_CRASH=0
P2_CRASH=0

###############################################################################
# P3 EVALUATION
###############################################################################

echo ""
echo "========== PROSPERITY 3 =========="

# P3 Archetype 1: Market Making (Round 1)
echo ""
echo "=== P3 Market Making (Round 1) ==="
R1_OUT=$(timeout $TIMEOUT_SEC prosperity3bt "$TRADER_FILE" 1 --no-out --merge-pnl --no-progress 2>&1) || true
echo "$R1_OUT" | tail -6
P3_MM=$(echo "$R1_OUT" | grep "^Total profit:" | tail -1 | sed 's/Total profit: //; s/,//g')
if [ -z "$P3_MM" ]; then
    echo "p3_mm_profit: CRASH"
    P3_MM=0
    P3_CRASH=$((P3_CRASH + 1))
else
    echo "p3_mm_profit: $P3_MM"
fi

# P3 Archetype 2: Stat Arb (Round 2)
echo ""
echo "=== P3 Stat Arb (Round 2) ==="
R2_OUT=$(timeout $TIMEOUT_SEC prosperity3bt "$TRADER_FILE" 2 --no-out --merge-pnl --no-progress 2>&1) || true
echo "$R2_OUT" | tail -10
P3_STATARB=$(echo "$R2_OUT" | grep "^Total profit:" | tail -1 | sed 's/Total profit: //; s/,//g')
if [ -z "$P3_STATARB" ]; then
    echo "p3_statarb_profit: CRASH"
    P3_STATARB=0
    P3_CRASH=$((P3_CRASH + 1))
else
    echo "p3_statarb_profit: $P3_STATARB"
fi

# P3 Archetype 3: Options (Round 3)
echo ""
echo "=== P3 Options (Round 3) ==="
R3_OUT=$(timeout $TIMEOUT_SEC prosperity3bt "$TRADER_FILE" 3 --no-out --merge-pnl --no-progress 2>&1) || true
echo "$R3_OUT" | tail -18
P3_OPTIONS=$(echo "$R3_OUT" | grep "^Total profit:" | tail -1 | sed 's/Total profit: //; s/,//g')
if [ -z "$P3_OPTIONS" ]; then
    echo "p3_options_profit: CRASH"
    P3_OPTIONS=0
    P3_CRASH=$((P3_CRASH + 1))
else
    echo "p3_options_profit: $P3_OPTIONS"
fi

# P3 Full (Round 5)
echo ""
echo "=== P3 Full (Round 5) ==="
R5_OUT=$(timeout $TIMEOUT_SEC prosperity3bt "$TRADER_FILE" 5 --no-out --merge-pnl --no-progress 2>&1) || true
echo "$R5_OUT" | tail -20
P3_FULL=$(echo "$R5_OUT" | grep "^Total profit:" | tail -1 | sed 's/Total profit: //; s/,//g')
if [ -z "$P3_FULL" ]; then
    echo "p3_full_profit: CRASH"
    P3_FULL=0
    P3_CRASH=$((P3_CRASH + 1))
else
    echo "p3_full_profit: $P3_FULL"
fi

# P3 Stress (Round 5, worse fills)
echo ""
echo "=== P3 Stress (Round 5 worse fills) ==="
R5W_OUT=$(timeout $TIMEOUT_SEC prosperity3bt "$TRADER_FILE" 5 --no-out --merge-pnl --no-progress --match-trades worse 2>&1) || true
echo "$R5W_OUT" | tail -6
P3_STRESS=$(echo "$R5W_OUT" | grep "^Total profit:" | tail -1 | sed 's/Total profit: //; s/,//g')
if [ -z "$P3_STRESS" ]; then
    echo "p3_stress_profit: CRASH"
    P3_STRESS=0
else
    echo "p3_stress_profit: $P3_STRESS"
fi

# P3 Hardmode (Round 5, NO trade matching — pure order book only)
echo ""
echo "=== P3 Hardmode (Round 5 no trade matching) ==="
R5N_OUT=$(timeout $TIMEOUT_SEC prosperity3bt "$TRADER_FILE" 5 --no-out --merge-pnl --no-progress --match-trades none 2>&1) || true
echo "$R5N_OUT" | tail -6
P3_HARDMODE=$(echo "$R5N_OUT" | grep "^Total profit:" | tail -1 | sed 's/Total profit: //; s/,//g')
if [ -z "$P3_HARDMODE" ]; then
    echo "p3_hardmode_profit: CRASH"
    P3_HARDMODE=0
else
    echo "p3_hardmode_profit: $P3_HARDMODE"
fi

# P3 Out-of-Sample (Round 6 day 3 — unseen data)
echo ""
echo "=== P3 Out-of-Sample (Round 6 day 3) ==="
R6_OUT=$(timeout $TIMEOUT_SEC prosperity3bt "$TRADER_FILE" 6-3 --no-out --no-progress 2>&1) || true
echo "$R6_OUT" | tail -6
P3_OOS=$(echo "$R6_OUT" | grep "^Total profit:" | tail -1 | sed 's/Total profit: //; s/,//g')
if [ -z "$P3_OOS" ]; then
    echo "p3_oos_profit: CRASH"
    P3_OOS=0
else
    echo "p3_oos_profit: $P3_OOS"
fi

###############################################################################
# P2 EVALUATION — same trader.py must work on different product names
# Uses P2 datamodel (copied alongside trader.py as datamodel.py)
# The trader must detect products at runtime and apply correct archetype
###############################################################################

echo ""
echo "========== PROSPERITY 2 =========="

# Copy trader.py to P2 submissions dir temporarily (needs P2 datamodel)
P2_TMPDIR=$(mktemp -d)
cp "$TRADER_FILE" "$P2_TMPDIR/trader.py"
cp /home/researcher/prosperity/imc-prosperity-2/src/algorithms/datamodel.py "$P2_TMPDIR/datamodel.py"

# P2 Market Making (Round 1: AMETHYSTS + STARFRUIT)
echo ""
echo "=== P2 Market Making (Round 1) ==="
P2R1_OUT=$(timeout $TIMEOUT_SEC prosperity2bt "$P2_TMPDIR/trader.py" 1 --no-out --merge-pnl --no-progress 2>&1) || true
echo "$P2R1_OUT" | tail -6
P2_MM=$(echo "$P2R1_OUT" | grep "^Total profit:" | tail -1 | sed 's/Total profit: //; s/,//g')
if [ -z "$P2_MM" ]; then
    echo "p2_mm_profit: CRASH"
    P2_MM=0
    P2_CRASH=$((P2_CRASH + 1))
else
    echo "p2_mm_profit: $P2_MM"
fi

# P2 Basket + Signal (Round 3: GIFT_BASKET, CHOCOLATE, STRAWBERRIES, ROSES)
echo ""
echo "=== P2 Basket/Signal (Round 3) ==="
P2R3_OUT=$(timeout $TIMEOUT_SEC prosperity2bt "$P2_TMPDIR/trader.py" 3 --no-out --merge-pnl --no-progress 2>&1) || true
echo "$P2R3_OUT" | tail -10
P2_BASKET=$(echo "$P2R3_OUT" | grep "^Total profit:" | tail -1 | sed 's/Total profit: //; s/,//g')
if [ -z "$P2_BASKET" ]; then
    echo "p2_basket_profit: CRASH"
    P2_BASKET=0
    P2_CRASH=$((P2_CRASH + 1))
else
    echo "p2_basket_profit: $P2_BASKET"
fi

# P2 Options (Round 4: COCONUT + COCONUT_COUPON)
echo ""
echo "=== P2 Options (Round 4) ==="
P2R4_OUT=$(timeout $TIMEOUT_SEC prosperity2bt "$P2_TMPDIR/trader.py" 4 --no-out --merge-pnl --no-progress 2>&1) || true
echo "$P2R4_OUT" | tail -10
P2_OPTIONS=$(echo "$P2R4_OUT" | grep "^Total profit:" | tail -1 | sed 's/Total profit: //; s/,//g')
if [ -z "$P2_OPTIONS" ]; then
    echo "p2_options_profit: CRASH"
    P2_OPTIONS=0
    P2_CRASH=$((P2_CRASH + 1))
else
    echo "p2_options_profit: $P2_OPTIONS"
fi

# P2 Out-of-Sample (Round 7 day 2 — unseen data)
echo ""
echo "=== P2 Out-of-Sample (Round 7 day 2) ==="
P2R7_OUT=$(timeout $TIMEOUT_SEC prosperity2bt "$P2_TMPDIR/trader.py" 7-2 --no-out --no-progress 2>&1) || true
echo "$P2R7_OUT" | tail -6
P2_OOS=$(echo "$P2R7_OUT" | grep "^Total profit:" | tail -1 | sed 's/Total profit: //; s/,//g')
if [ -z "$P2_OOS" ]; then
    echo "p2_oos_profit: CRASH"
    P2_OOS=0
    P2_CRASH=$((P2_CRASH + 1))
else
    echo "p2_oos_profit: $P2_OOS"
fi

# Cleanup
rm -rf "$P2_TMPDIR"

###############################################################################
# COMPOSITE SCORE
###############################################################################
echo ""
echo "========== SUMMARY =========="
echo "p3_mm_profit: $P3_MM"
echo "p3_statarb_profit: $P3_STATARB"
echo "p3_options_profit: $P3_OPTIONS"
echo "p3_full_profit: $P3_FULL"
echo "p3_stress_profit: $P3_STRESS"
echo "p3_hardmode_profit: $P3_HARDMODE"
echo "p3_oos_profit: $P3_OOS"
echo "p3_crashes: $P3_CRASH"
echo "p2_mm_profit: $P2_MM"
echo "p2_basket_profit: $P2_BASKET"
echo "p2_options_profit: $P2_OPTIONS"
echo "p2_oos_profit: $P2_OOS"
echo "p2_crashes: $P2_CRASH"

python3 compute_score.py \
    "$P3_MM" "$P3_STATARB" "$P3_OPTIONS" "$P3_FULL" "$P3_STRESS" "$P3_HARDMODE" "$P3_OOS" "$P3_CRASH" \
    "$P2_MM" "$P2_BASKET" "$P2_OPTIONS" "$P2_OOS" "$P2_CRASH"
