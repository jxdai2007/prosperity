#!/usr/bin/env python3
"""
Immutable composite score calculator for IMC Prosperity autoresearch.
DO NOT MODIFY during experiments.

Tests the SAME trader on both P3 and P2 data. The trader must detect
which competition it's in from product names and apply the right archetype.

If a strategy only works on P3, the P2 score will be 0 or negative.
That means it's overfit to P3 product names, not transferable to P4.
"""

import sys


def main():
    if len(sys.argv) != 11:
        print("Usage: compute_score.py p3_mm p3_statarb p3_options p3_full p3_stress p3_crashes p2_mm p2_basket p2_options p2_crashes")
        sys.exit(1)

    # P3 scores
    p3_mm = int(sys.argv[1])
    p3_statarb = int(sys.argv[2])
    p3_options = int(sys.argv[3])
    p3_full = int(sys.argv[4])
    p3_stress = int(sys.argv[5])
    p3_crashes = int(sys.argv[6])

    # P2 scores
    p2_mm = int(sys.argv[7])
    p2_basket = int(sys.argv[8])
    p2_options = int(sys.argv[9])
    p2_crashes = int(sys.argv[10])

    total_crashes = p3_crashes + p2_crashes

    # --- P3 archetype isolation ---
    p3_mm_score = p3_mm
    p3_baskets_score = max(p3_statarb - p3_mm, 0)
    p3_options_score = max(p3_options - p3_statarb, 0)
    p3_insider_score = max(p3_full - p3_options, 0)

    # --- Robustness ---
    p3_robustness = p3_stress / p3_full if p3_full > 0 else 0.0

    print(f"\n=== P3 Archetype Isolation ===")
    print(f"  Market Making:      {p3_mm_score:>12,}")
    print(f"  Basket/Stat Arb:    {p3_baskets_score:>12,}")
    print(f"  Options:            {p3_options_score:>12,}")
    print(f"  Insider+Conversion: {p3_insider_score:>12,}")
    print(f"  Robustness ratio:   {p3_robustness:>12.1%}")
    print(f"  Crashes:            {p3_crashes:>12}")

    print(f"\n=== P2 Scores ===")
    print(f"  Market Making:      {p2_mm:>12,}")
    print(f"  Basket/Signal:      {p2_basket:>12,}")
    print(f"  Options:            {p2_options:>12,}")
    print(f"  Crashes:            {p2_crashes:>12}")

    # --- Cross-competition transfer score ---
    # If both P2 and P3 MM are positive, the MM archetype transfers
    mm_transfers = p3_mm_score > 0 and p2_mm > 0
    basket_transfers = p3_baskets_score > 0 and p2_basket > 0
    options_transfers = p3_options_score > 0 and p2_options > 0

    transfer_count = sum([mm_transfers, basket_transfers, options_transfers])

    print(f"\n=== Transfer Check ===")
    print(f"  MM transfers:       {'YES' if mm_transfers else 'NO'}")
    print(f"  Basket transfers:   {'YES' if basket_transfers else 'NO'}")
    print(f"  Options transfers:  {'YES' if options_transfers else 'NO'}")
    print(f"  Archetypes that transfer: {transfer_count}/3")

    # --- Composite score ---
    # Design philosophy:
    #   - P3 and P2 weighted equally (tests generalization)
    #   - Stress test matters (adversarial fills = real competition)
    #   - Each transferring archetype gets a bonus
    #   - Crashes are severely penalized
    #
    # P3 component (50% weight):
    #   25% full R5, 10% stress, 5% each for MM/statarb/options
    # P2 component (35% weight):
    #   15% MM, 10% basket, 10% options
    # Transfer bonus (15% weight):
    #   50,000 per archetype that works on both P2 and P3
    # Crash penalty: -100,000 per crash

    composite = (
        # P3 (50%)
        0.25 * p3_full
        + 0.10 * p3_stress
        + 0.05 * p3_mm
        + 0.05 * p3_statarb
        + 0.05 * p3_options
        # P2 (35%)
        + 0.15 * p2_mm
        + 0.10 * p2_basket
        + 0.10 * p2_options
        # Transfer bonus (rewards strategies that work on BOTH)
        + 50_000 * transfer_count
        # Crash penalty
        - 100_000 * total_crashes
    )

    print(f"\n=== Final Score ===")
    print(f"composite_score: {int(composite)}")


if __name__ == "__main__":
    main()
