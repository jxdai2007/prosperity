#!/usr/bin/env python3
"""
Immutable preparation script for IMC Prosperity 3→4 autoresearch.
DO NOT MODIFY during experiments.

Validates environment, runs multi-round baseline eval, initializes tracking.
"""

import subprocess
import sys
import os
import hashlib
from pathlib import Path

WORKDIR = Path(__file__).parent
os.chdir(WORKDIR)

def run(cmd, check=True):
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=300)
    if check and result.returncode != 0:
        print(f"FAIL: {cmd}")
        print(result.stderr[-500:] if result.stderr else "")
        sys.exit(1)
    return result

def main():
    print("=" * 60)
    print("IMC Prosperity 3→4 Autoresearch - Environment Validation")
    print("=" * 60)

    # 1. Check Python
    print(f"\n[1/8] Python: {sys.version.split()[0]}")

    # 2. Check backtester
    print("\n[2/8] Backtester...")
    result = run("prosperity3bt --version")
    print(f"  {result.stdout.strip()}")

    # 3. Check required files
    print("\n[3/8] Required files...")
    required = ["trader.py", "datamodel.py", "eval.sh", "compute_score.py", "program.md"]
    for f in required:
        if not (WORKDIR / f).exists():
            print(f"  MISSING: {f}")
            sys.exit(1)
        print(f"  OK: {f}")

    # 4. Check numpy
    print("\n[4/8] Numpy...")
    import numpy as np
    print(f"  numpy {np.__version__}")

    # 5. Smoke test: single day round 5
    print("\n[5/8] Smoke test (round 5 day 2)...")
    result = run("timeout 30 prosperity3bt trader.py 5-2 --no-out --no-progress 2>&1", check=False)
    if result.returncode != 0:
        print(f"  WARNING: backtester returned {result.returncode}")
        print(f"  (Trader may crash on some rounds — that's what we're fixing)")
    else:
        for line in result.stdout.split("\n"):
            if line.startswith("Total profit:"):
                print(f"  R5 day 2: {line.split(':')[1].strip()}")
    print("  OK")

    # 6. Multi-round crash check
    print("\n[6/8] Round compatibility check...")
    for rnd in ["1-0", "2-0", "3-0", "5-2"]:
        result = run(f"timeout 30 prosperity3bt trader.py {rnd} --no-out --no-progress 2>&1", check=False)
        status = "OK" if result.returncode == 0 else "CRASH"
        profit = "?"
        if result.returncode == 0:
            for line in result.stdout.split("\n"):
                if line.startswith("Total profit:"):
                    profit = line.split(":")[1].strip()
        print(f"  Round {rnd}: {status} (profit: {profit})")

    # 7. File checksums
    print("\n[7/8] File checksums...")
    immutable = ["eval.sh", "prepare.py", "compute_score.py", "datamodel.py"]
    checksums = {}
    for f in immutable:
        path = WORKDIR / f
        if path.exists():
            h = hashlib.sha256(path.read_bytes()).hexdigest()[:16]
            checksums[f] = h
            print(f"  {f}: {h}")
    with open(WORKDIR / "file_checksums.txt", "w") as fh:
        for f, h in checksums.items():
            fh.write(f"{f}\t{h}\n")

    # 8. Initialize tracking files
    print("\n[8/8] Tracking files...")
    results_path = WORKDIR / "results.tsv"
    if not results_path.exists():
        with open(results_path, "w") as f:
            f.write("commit\tcomposite_score\tmm_profit\tstatarb_profit\toptions_profit\tfull_profit\tstress_profit\tcrashes\tstatus\tdescription\n")
        print("  Created results.tsv")
    else:
        print("  results.tsv exists")

    # Initialize insights.md
    insights_path = WORKDIR / "insights.md"
    if not insights_path.exists():
        insights_path.write_text("""# Strategy Insights for IMC Prosperity 4

This is the REAL deliverable. Document what you learn about each archetype.
Focus on TRANSFERABLE PRINCIPLES, not P3-specific implementation details.

## Market Making (R1 archetype)

### What works
- (to be filled by experiments)

### Transferable principles
- (to be filled)

## Statistical Arbitrage (R2 archetype)

### What works
- (to be filled)

### Transferable principles
- (to be filled)

## Volatility Trading (R3 archetype)

### What works
- (to be filled)

### Transferable principles
- (to be filled)

## Conversion Arbitrage (R4 archetype)

### What works
- (to be filled)

### Transferable principles
- (to be filled)

## Insider Following (R5 archetype)

### What works
- (to be filled)

### Transferable principles
- (to be filled)
""")
        print("  Created insights.md")

    for f, default in [("experiment_feedback.md", "# Experiment Feedback\n\n"),
                       ("research_queue.md", "# Research Queue\n(see program.md)\n")]:
        path = WORKDIR / f
        if not path.exists():
            path.write_text(default)
            print(f"  Created {f}")

    print("\n" + "=" * 60)
    print("PREPARATION COMPLETE")
    print("NOTE: Trader may crash on rounds 1-2. Fix this first!")
    print("=" * 60)

if __name__ == "__main__":
    main()
