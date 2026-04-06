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

    keeps = [r for r in rows if r.get("status") == "keep"]
    discards = [r for r in rows if r.get("status") == "discard"]
    crashes_list = [r for r in rows if r.get("status") in ("crash",)]
    baseline = [r for r in rows if r.get("status") == "baseline"]

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
    for col, name in [("mm_profit", "Market Making (R1)"),
                       ("statarb_profit", "Stat Arb (R2)"),
                       ("options_profit", "Options (R3)"),
                       ("full_profit", "Full (R5)"),
                       ("stress_profit", "Stress (R5 worse)")]:
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
        crashes = row.get("crashes", "?")
        desc = row.get("description", "")[:50]
        marker = "✓" if status == "keep" else "✗" if status == "discard" else "⚠" if "crash" in str(crashes) else "·"
        print(f"  {marker} {status:<10} score={composite:>10}  crash={crashes}  {desc}")

    # Discards since last keep
    discards_since = 0
    for row in reversed(rows):
        if row.get("status") == "keep":
            break
        if row.get("status") in ("discard", "crash"):
            discards_since += 1

    print(f"\nDiscards since last keep: {discards_since}")
    if discards_since >= 5:
        print("  → Go radical. Try a different archetype or approach.")
    elif discards_since >= 3:
        print("  → Consider changing direction.")

    # Crash analysis
    crash_rounds = 0
    for r in rows[-5:]:
        c = safe_int(r.get("crashes"))
        if c and c > 0:
            crash_rounds += 1
    if crash_rounds > 0:
        print(f"\n⚠ {crash_rounds}/5 recent experiments had crashes — FIX STABILITY FIRST")

    print("\n" + "=" * 70)

if __name__ == "__main__":
    main()
