#!/usr/bin/env python3
"""
Immutable preparation script for IMC Prosperity 3 autoresearch.
DO NOT MODIFY during experiments.

Validates environment, runs baseline eval, initializes tracking files.
"""

import subprocess
import sys
import os
import hashlib
from pathlib import Path

WORKDIR = Path(__file__).parent
os.chdir(WORKDIR)

def run(cmd, check=True):
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if check and result.returncode != 0:
        print(f"FAIL: {cmd}")
        print(result.stderr)
        sys.exit(1)
    return result

def main():
    print("=" * 60)
    print("IMC Prosperity 3 Autoresearch - Environment Validation")
    print("=" * 60)

    # 1. Check Python
    print(f"\n[1/9] Python version: {sys.version}")

    # 2. Check backtester
    print("\n[2/9] Checking prosperity3bt...")
    result = run("prosperity3bt --version")
    print(f"  {result.stdout.strip()}")

    # 3. Check required files
    print("\n[3/9] Checking required files...")
    required = ["trader.py", "datamodel.py", "eval.sh", "program.md"]
    for f in required:
        path = WORKDIR / f
        if not path.exists():
            print(f"  MISSING: {f}")
            sys.exit(1)
        print(f"  OK: {f}")

    # 4. Check numpy available
    print("\n[4/9] Checking numpy...")
    try:
        import numpy as np
        print(f"  numpy {np.__version__}")
    except ImportError:
        print("  FAIL: numpy not installed")
        sys.exit(1)

    # 5. Smoke test: run backtester on single day
    print("\n[5/9] Smoke test (round 5 day 2)...")
    result = run("timeout 60 prosperity3bt trader.py 5-2 --no-out --no-progress 2>&1", check=False)
    if result.returncode != 0:
        print(f"  FAIL: backtester returned {result.returncode}")
        print(result.stdout[-500:] if result.stdout else "")
        print(result.stderr[-500:] if result.stderr else "")
        sys.exit(1)

    # Parse profit from smoke test
    for line in result.stdout.split("\n"):
        if line.startswith("Total profit:"):
            print(f"  Smoke test profit (day 2): {line.split(':')[1].strip()}")
            break
    print("  OK")

    # 6. Full baseline eval
    print("\n[6/9] Running full baseline eval...")
    result = run("bash eval.sh 2>&1", check=False)
    print(result.stdout[-300:] if result.stdout else "")

    baseline_profit = None
    for line in result.stdout.split("\n"):
        if line.startswith("total_profit:"):
            val = line.split(":")[1].strip()
            if val not in ("CRASH", "PARSE_ERROR"):
                baseline_profit = int(val)
                print(f"\n  BASELINE PROFIT: {baseline_profit:,}")

    if baseline_profit is None:
        print("  WARNING: Could not establish baseline profit")

    # 7. File checksums (immutable files)
    print("\n[7/9] Computing file checksums...")
    immutable_files = ["eval.sh", "prepare.py", "datamodel.py"]
    checksums = {}
    for f in immutable_files:
        path = WORKDIR / f
        if path.exists():
            h = hashlib.sha256(path.read_bytes()).hexdigest()[:16]
            checksums[f] = h
            print(f"  {f}: {h}")

    with open(WORKDIR / "file_checksums.txt", "w") as fh:
        for f, h in checksums.items():
            fh.write(f"{f}\t{h}\n")

    # 8. Initialize results.tsv
    print("\n[8/9] Initializing results.tsv...")
    results_path = WORKDIR / "results.tsv"
    if not results_path.exists():
        with open(results_path, "w") as f:
            f.write("commit\ttotal_profit\tstatus\tdescription\n")
            if baseline_profit is not None:
                commit = subprocess.run("git rev-parse --short HEAD", shell=True,
                                       capture_output=True, text=True).stdout.strip()
                f.write(f"{commit}\t{baseline_profit}\tbaseline\tOLIVIA IS THE GOAT starting point\n")
        print("  Created results.tsv with baseline")
    else:
        print("  results.tsv already exists")

    # 9. Git + .gitignore
    print("\n[9/9] Checking git...")
    result = run("git status --short", check=False)
    print(f"  Git status: {len(result.stdout.strip().splitlines())} files")

    # Initialize shared files
    feedback_path = WORKDIR / "experiment_feedback.md"
    if not feedback_path.exists():
        feedback_path.write_text("# Experiment Feedback\n\n")

    queue_path = WORKDIR / "research_queue.md"
    if not queue_path.exists():
        queue_path.write_text("""# Research Queue
# Updated: initial
# Discards since last keep: 0

## Next Up

### Enable MAGNIFICENT_MACARONS trading
- Reasoning: trade_macaroni() exists but is commented out in run(). FrankfurtHedgehogs had a working strategy.
- Changes: uncomment self.trade_macaroni(state) in run(), tune conversion/sell logic
- Radicality: nearby
- Mechanism: currently 0 profit from macarons, even small profit adds to total
- Category: product activation

### Increase basket position limits
- Reasoning: BASKET1_LIMIT=10 vs actual 60, BASKET2_LIMIT=10 vs actual 100. Massive untapped capacity.
- Changes: increase BASKET1_LIMIT and BASKET2_LIMIT, adjust MM logic
- Radicality: nearby
- Mechanism: larger positions = more market making profit per turn
- Category: position sizing

### Increase SQUID_LIMIT
- Reasoning: SQUID_LIMIT=15 vs actual limit of 50. Market making profit scales with position.
- Changes: increase SQUID_LIMIT from 15 toward 50
- Radicality: nearby
- Mechanism: more capital deployed = more MM spread capture
- Category: position sizing

### Fix options for losing strikes
- Reasoning: VOUCHER_10250 and VOUCHER_10500 consistently lose money
- Changes: remove these from self.vouchers list, or add special handling
- Radicality: nearby
- Mechanism: stop bleeding on unprofitable strikes, redirect capital
- Category: options strategy

### Basket arbitrage strategy
- Reasoning: currently only Olivia-signal trading + simple MM on baskets. No actual arb vs components.
- Changes: implement PB1 = 6*CROISSANTS + 3*JAMS + 1*DJEMBES fair value calculation, trade spread
- Radicality: moderate
- Mechanism: exploit mispricing between baskets and components
- Category: new strategy

## Queue

### Improve IV estimation for options
- Reasoning: using simple window average of IV. Could use vol smile model or weighted estimation.
- Changes: implement quadratic vol smile fitting like FrankfurtHedgehogs
- Radicality: moderate
- Mechanism: better fair value = better fills, less adverse selection
- Category: options strategy

### Enable delta hedging
- Reasoning: trade_underlying has dont_hedge=True. Unhedged options exposure = unnecessary risk.
- Changes: set dont_hedge=False, tune hedging logic
- Radicality: moderate
- Mechanism: reduce P&L variance, prevent large drawdowns
- Category: options strategy

### Kelp Olivia signal following
- Reasoning: kelp_signal is tracked but never acted on (only squid and croissants are traded on signals)
- Changes: add Olivia signal logic for KELP similar to squid
- Radicality: nearby
- Mechanism: capture informed trading edge from Olivia's signals
- Category: signal trading

## Rejected
(none yet)
""")

    print("\n" + "=" * 60)
    print("PREPARATION COMPLETE")
    if baseline_profit is not None:
        print(f"Baseline total profit: {baseline_profit:,}")
    print("=" * 60)

if __name__ == "__main__":
    main()
