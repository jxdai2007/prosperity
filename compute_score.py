#!/usr/bin/env python3
"""
Immutable composite score calculator for IMC Prosperity 3 autoresearch.
DO NOT MODIFY during experiments.

Produces a single composite_score that rewards:
1. Strong per-archetype performance (each archetype matters independently)
2. Robustness (profit under adversarial fills)
3. Breadth (strategies that work across rounds, not just round 5)
4. Penalizes crashes heavily (broken code = broken competition day)

The composite is what the agent optimizes. Per-archetype scores
are tracked in results.tsv for insight.
"""

import sys


def main():
    if len(sys.argv) != 7:
        print("Usage: compute_score.py mm_profit statarb_profit options_profit full_profit stress_profit crash_count")
        sys.exit(1)

    mm = int(sys.argv[1])          # Round 1: market making only
    statarb = int(sys.argv[2])     # Round 2: MM + baskets
    options = int(sys.argv[3])     # Round 3: MM + baskets + options
    full = int(sys.argv[4])        # Round 5: everything
    stress = int(sys.argv[5])      # Round 5 with worse fills
    crashes = int(sys.argv[6])     # Number of rounds that crashed

    # --- Archetype isolation ---
    # Round 1 = pure MM profit
    # Round 2 - Round 1 ≈ basket/statarb contribution
    # Round 3 - Round 2 ≈ options contribution
    # Round 5 - Round 3 ≈ conversion + insider contribution
    # (These are approximate due to cross-round data differences)
    mm_score = mm
    baskets_score = max(statarb - mm, 0)  # Don't penalize if MM does worse in R2
    options_score = max(options - statarb, 0)
    insider_conversion_score = max(full - options, 0)

    print(f"\n=== Archetype Isolation (approximate) ===")
    print(f"  Market Making:      {mm_score:>10,}")
    print(f"  Basket/Stat Arb:    {baskets_score:>10,}")
    print(f"  Options:            {options_score:>10,}")
    print(f"  Insider+Conversion: {insider_conversion_score:>10,}")

    # --- Robustness ratio ---
    # How much profit survives adversarial fills?
    if full > 0:
        robustness = stress / full
    else:
        robustness = 0.0

    print(f"  Robustness ratio:   {robustness:>10.2%}")

    # --- Composite score ---
    # Weights:
    #   40% full round 5 performance (the "real" competition score)
    #   20% stress test (robustness — will fills be generous in P4?)
    #   15% options archetype (historically most valuable, R3 is make-or-break)
    #   10% market making (foundation, should always work)
    #   10% stat arb (baskets are standard R2)
    #    5% insider+conversion (P4 equivalent may differ most)
    #
    # Crash penalty: -100,000 per crash (a crash in competition = 0 for that round)

    composite = (
        0.40 * full
        + 0.20 * stress
        + 0.15 * options
        + 0.10 * mm
        + 0.10 * statarb
        + 0.05 * full  # extra weight for breadth
        - 100_000 * crashes
    )

    print(f"\n=== Final Score ===")
    print(f"composite_score: {int(composite)}")


if __name__ == "__main__":
    main()
