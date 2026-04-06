#!/usr/bin/env python3
"""Summarize autoresearch experiment results."""

import csv
from collections import defaultdict
from pathlib import Path
from datetime import datetime

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

    # Parse profits
    keeps = []
    discards = []
    crashes = []
    baseline = None
    best_profit = None
    best_desc = None

    for row in rows:
        status = row.get("status", "")
        try:
            profit = int(row["total_profit"])
        except (ValueError, KeyError):
            profit = None

        if status == "baseline":
            baseline = profit
        elif status == "keep":
            keeps.append((profit, row))
        elif status == "discard":
            discards.append((profit, row))
        elif status in ("crash", "prescreen_fail"):
            crashes.append(row)

        if profit is not None:
            if best_profit is None or profit > best_profit:
                best_profit = profit
                best_desc = row.get("description", "")

    total_experiments = len(keeps) + len(discards) + len(crashes)

    print(f"\nBaseline:     {baseline:>12,}" if baseline else "\nBaseline:     unknown")
    print(f"Best profit:  {best_profit:>12,}" if best_profit else "Best profit:  unknown")
    if best_desc:
        print(f"  ({best_desc})")

    if baseline and best_profit:
        improvement = best_profit - baseline
        pct = (improvement / abs(baseline)) * 100 if baseline != 0 else 0
        print(f"Improvement:  {improvement:>+12,} ({pct:+.1f}%)")

    print(f"\nKeeps:    {len(keeps):>4}")
    print(f"Discards: {len(discards):>4}")
    print(f"Crashes:  {len(crashes):>4}")

    if total_experiments > 0:
        keep_rate = len(keeps) / total_experiments * 100
        print(f"Keep rate: {keep_rate:.1f}%")

    # Recent streak
    print("\n--- Recent History (last 10) ---")
    for row in rows[-10:]:
        status = row.get("status", "?")
        profit = row.get("total_profit", "?")
        desc = row.get("description", "")[:50]
        marker = "✓" if status == "keep" else "✗" if status == "discard" else "⚠" if status == "crash" else "·"
        print(f"  {marker} {status:<10} {profit:>12}  {desc}")

    # Discards since last keep
    discards_since_keep = 0
    for row in reversed(rows):
        if row.get("status") == "keep":
            break
        if row.get("status") in ("discard", "crash"):
            discards_since_keep += 1

    print(f"\nDiscards since last keep: {discards_since_keep}")

    if discards_since_keep >= 5:
        print("  → Consider more radical experiments")
    elif discards_since_keep >= 3:
        print("  → Consider changing direction")

    # Category analysis
    print("\n--- Structural vs Tuning ---")
    structural = sum(1 for _, r in keeps + discards if "struct" in r.get("description", "").lower()
                     or any(w in r.get("description", "").lower() for w in ["add", "remove", "new", "replace", "switch", "implement"]))
    tuning = sum(1 for _, r in keeps + discards if any(w in r.get("description", "").lower()
                 for w in ["tune", "adjust", "increase", "decrease", "tweak", "param"]))
    other = len(keeps) + len(discards) - structural - tuning

    print(f"  Structural: {structural}")
    print(f"  Tuning:     {tuning}")
    print(f"  Other:      {other}")
    if tuning > structural and total_experiments > 5:
        print("  → WARNING: Too much tuning, not enough structural changes")

    print("\n" + "=" * 70)

if __name__ == "__main__":
    main()
