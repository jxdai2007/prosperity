#!/usr/bin/env python3
"""Summarize autoresearch experiment results with per-archetype analysis."""

import csv
from pathlib import Path

def safe_int(val):
    try:
        return int(val)
    except (ValueError, TypeError):
        return None

def main():
    results_path = Path(__file__).parent / "results.tsv"
    if not results_path.exists():
        print("No results.tsv found")
        return

    rows = []
    with open(results_path) as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            rows.append(row)

    if not rows:
        print("No experiments recorded")
        return

    print("=" * 70)
    print(f"EXPERIMENT SUMMARY — {len(rows)} experiments")
    print("=" * 70)

    keeps = [r for r in rows if r.get("status", "").upper() == "KEEP"]
    discards = [r for r in rows if r.get("status", "").upper() == "DISCARD"]
    crashes_list = [r for r in rows if r.get("status", "").upper() == "CRASH"]
    baseline = [r for r in rows if r.get("status", "").upper() == "BASELINE"]

    total_exp = len(keeps) + len(discards) + len(crashes_list)

    # Best scores
    best_composite = None
    best_row = None
    for r in rows:
        score = safe_int(r.get("composite_score"))
        if score is not None and (best_composite is None or score > best_composite):
            best_composite = score
            best_row = r

    print(f"\nBest composite: {best_composite:>12,}" if best_composite else "\nBest composite: unknown")
    if best_row:
        print(f"  ({best_row.get('description', '')})")

    print(f"\nKeeps:    {len(keeps):>4}")
    print(f"Discards: {len(discards):>4}")
    print(f"Crashes:  {len(crashes_list):>4}")
    if total_exp > 0:
        print(f"Keep rate: {len(keeps)/total_exp*100:.1f}%")

    # Per-archetype best scores
    print("\n--- Best Per-Archetype Scores ---")
    for col, name in [("p3_mm", "P3 Market Making (R1)"),
                       ("p3_statarb", "P3 Stat Arb (R2)"),
                       ("p3_options", "P3 Options (R3)"),
                       ("p3_full", "P3 Full (R5)"),
                       ("p3_stress", "P3 Stress (R5 worse)"),
                       ("p3_hardmode", "P3 Hardmode (no fills)"),
                       ("p3_oos", "P3 OOS (R6)"),
                       ("p2_mm", "P2 Market Making"),
                       ("p2_basket", "P2 Basket"),
                       ("p2_options", "P2 Options"),
                       ("p2_oos", "P2 OOS (R7)")]:
        best = None
        for r in rows:
            val = safe_int(r.get(col))
            if val is not None and (best is None or val > best):
                best = val
        if best is not None:
            print(f"  {name:<25} {best:>12,}")

    # Archetype focus distribution
    print("\n--- Experiment Focus ---")
    archetype_counts = {}
    for r in rows:
        desc = r.get("description", "")
        for tag in ["[mm]", "[statarb]", "[options]", "[conversion]", "[insider]", "[robustness]"]:
            if tag in desc.lower():
                archetype_counts[tag] = archetype_counts.get(tag, 0) + 1
                break
        else:
            archetype_counts["[other]"] = archetype_counts.get("[other]", 0) + 1

    for tag, count in sorted(archetype_counts.items(), key=lambda x: -x[1]):
        print(f"  {tag:<20} {count:>4}")

    # Recent history
    print("\n--- Recent History (last 10) ---")
    for row in rows[-10:]:
        status = row.get("status", "?")
        composite = row.get("composite_score", "?")
        p3_crashes = row.get("p3_crashes", "0")
        p2_crashes = row.get("p2_crashes", "0")
        desc = row.get("description", "")[:50]
        marker = "✓" if status.upper() == "KEEP" else "✗" if status.upper() == "DISCARD" else "⚠" if status.upper() == "CRASH" else "·"
        print(f"  {marker} {status:<10} score={composite:>10}  p3c={p3_crashes} p2c={p2_crashes}  {desc}")

    # Discards since last keep
    discards_since = 0
    for row in reversed(rows):
        if row.get("status", "").upper() == "KEEP":
            break
        if row.get("status", "").upper() in ("DISCARD", "CRASH"):
            discards_since += 1

    print(f"\nDiscards since last keep: {discards_since}")
    if discards_since >= 5:
        print("  → Go radical. Try a different archetype or approach.")
    elif discards_since >= 3:
        print("  → Consider changing direction.")

    # Crash analysis
    crash_rounds = 0
    for r in rows[-5:]:
        c3 = safe_int(r.get("p3_crashes")) or 0
        c2 = safe_int(r.get("p2_crashes")) or 0
        if c3 + c2 > 0:
            crash_rounds += 1
    if crash_rounds > 0:
        print(f"\n⚠ {crash_rounds}/5 recent experiments had crashes — FIX STABILITY FIRST")

    print("\n" + "=" * 70)

if __name__ == "__main__":
    main()
