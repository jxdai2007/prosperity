#!/usr/bin/env python3
"""
Immutable composite score calculator for IMC Prosperity autoresearch.
DO NOT MODIFY during experiments.

Tests the SAME trader on P3 and P2 across multiple rounds, fill modes,
and out-of-sample data. Rewards transferability and robustness.
"""

import sys


def main():
    if len(sys.argv) != 14:
        print("Usage: compute_score.py p3_mm p3_statarb p3_options p3_full p3_stress p3_hardmode p3_oos p3_crashes p2_mm p2_basket p2_options p2_oos p2_crashes")
        sys.exit(1)

    # P3 scores
    p3_mm = int(sys.argv[1])
    p3_statarb = int(sys.argv[2])
    p3_options = int(sys.argv[3])
    p3_full = int(sys.argv[4])
    p3_stress = int(sys.argv[5])      # worse fills
    p3_hardmode = int(sys.argv[6])    # no trade matching
    p3_oos = int(sys.argv[7])         # out-of-sample (round 6)
    p3_crashes = int(sys.argv[8])

    # P2 scores
    p2_mm = int(sys.argv[9])
    p2_basket = int(sys.argv[10])
    p2_options = int(sys.argv[11])
    p2_oos = int(sys.argv[12])        # out-of-sample (round 7)
    p2_crashes = int(sys.argv[13])

    total_crashes = p3_crashes + p2_crashes

    # --- P3 archetype isolation ---
    p3_mm_score = p3_mm
    p3_baskets_score = max(p3_statarb - p3_mm, 0)
    p3_options_score = max(p3_options - p3_statarb, 0)
    p3_insider_score = max(p3_full - p3_options, 0)

    # --- Robustness ratios ---
    p3_robustness_worse = p3_stress / p3_full if p3_full > 0 else 0.0
    p3_robustness_none = p3_hardmode / p3_full if p3_full > 0 else 0.0

    print(f"\n=== P3 Archetype Isolation ===")
    print(f"  Market Making:      {p3_mm_score:>12,}")
    print(f"  Basket/Stat Arb:    {p3_baskets_score:>12,}")
    print(f"  Options:            {p3_options_score:>12,}")
    print(f"  Insider+Conversion: {p3_insider_score:>12,}")
    print(f"  Robustness (worse): {p3_robustness_worse:>12.1%}")
    print(f"  Robustness (none):  {p3_robustness_none:>12.1%}")
    print(f"  Out-of-sample (R6): {p3_oos:>12,}")
    print(f"  Crashes:            {p3_crashes:>12}")

    print(f"\n=== P2 Scores ===")
    print(f"  Market Making:      {p2_mm:>12,}")
    print(f"  Basket/Signal:      {p2_basket:>12,}")
    print(f"  Options:            {p2_options:>12,}")
    print(f"  Out-of-sample (R7): {p2_oos:>12,}")
    print(f"  Crashes:            {p2_crashes:>12}")

    # --- Cross-competition transfer ---
    mm_transfers = p3_mm_score > 0 and p2_mm > 0
    basket_transfers = p3_baskets_score > 0 and p2_basket > 0
    options_transfers = p3_options_score > 0 and p2_options > 0
    transfer_count = sum([mm_transfers, basket_transfers, options_transfers])

    print(f"\n=== Transfer Check ===")
    print(f"  MM transfers:       {'YES' if mm_transfers else 'NO'}")
    print(f"  Basket transfers:   {'YES' if basket_transfers else 'NO'}")
    print(f"  Options transfers:  {'YES' if options_transfers else 'NO'}")
    print(f"  Archetypes: {transfer_count}/3")

    # --- Composite score ---
    #
    # P3 in-sample (35%):
    #   15% full R5, 5% each for MM/statarb/options, 5% stress (worse fills)
    # P3 robustness (10%):
    #   5% hardmode (no trade matching), 5% out-of-sample (R6)
    # P2 in-sample (30%):
    #   10% MM, 10% basket, 10% options
    # P2 out-of-sample (10%):
    #   10% R7 OOS
    # Transfer bonus (15%):
    #   50,000 per archetype that works on both P2 and P3
    # Crash penalty: -100,000 per crash

    composite = (
        # P3 in-sample (35%)
        0.15 * p3_full
        + 0.05 * p3_mm
        + 0.05 * p3_statarb
        + 0.05 * p3_options
        + 0.05 * p3_stress
        # P3 robustness (10%)
        + 0.05 * p3_hardmode
        + 0.05 * p3_oos
        # P2 in-sample (30%)
        + 0.10 * p2_mm
        + 0.10 * p2_basket
        + 0.10 * p2_options
        # P2 out-of-sample (10%)
        + 0.10 * p2_oos
        # Transfer bonus
        + 50_000 * transfer_count
        # Crash penalty
        - 100_000 * total_crashes
    )

    print(f"\n=== Final Score ===")
    print(f"composite_score: {int(composite)}")


if __name__ == "__main__":
    main()
