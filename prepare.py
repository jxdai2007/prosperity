#!/usr/bin/env python3
"""
Immutable preparation script for dual-competition autoresearch.
DO NOT MODIFY during experiments.
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
    print("IMC Prosperity Autoresearch — Dual Competition Setup")
    print("=" * 60)

    print(f"\n[1/8] Python: {sys.version.split()[0]}")

    print("\n[2/8] Backtesters...")
    for bt in ["prosperity3bt", "prosperity2bt"]:
        result = run(f"{bt} --version 2>&1", check=False)
        ver = result.stdout.strip() if result.returncode == 0 else "NOT FOUND"
        print(f"  {bt}: {ver}")

    print("\n[3/8] Required files...")
    for f in ["trader.py", "datamodel.py", "eval.sh", "compute_score.py", "program.md"]:
        status = "OK" if (WORKDIR / f).exists() else "MISSING"
        print(f"  {f}: {status}")
        if status == "MISSING":
            sys.exit(1)

    print("\n[4/8] Dependencies...")
    import numpy as np
    print(f"  numpy {np.__version__}")

    print("\n[5/8] P3 round compatibility...")
    for rnd in ["1-0", "2-0", "3-0", "5-2"]:
        result = run(f"timeout 30 prosperity3bt trader.py {rnd} --no-out --no-progress 2>&1", check=False)
        status = "OK" if result.returncode == 0 else "CRASH"
        profit = "?"
        if result.returncode == 0:
            for line in result.stdout.split("\n"):
                if line.startswith("Total profit:"):
                    profit = line.split(":")[1].strip()
        print(f"  P3 Round {rnd}: {status} (profit: {profit})")

    print("\n[6/8] P2 round compatibility...")
    p2_dm = Path("/home/researcher/prosperity/imc-prosperity-2/src/algorithms/datamodel.py")
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        os.system(f"cp trader.py {tmpdir}/trader.py")
        os.system(f"cp {p2_dm} {tmpdir}/datamodel.py")
        for rnd in ["1-0", "3-0", "4-1"]:
            result = run(f"timeout 30 prosperity2bt {tmpdir}/trader.py {rnd} --no-out --no-progress 2>&1", check=False)
            status = "OK" if result.returncode == 0 else "CRASH"
            profit = "?"
            if result.returncode == 0:
                for line in result.stdout.split("\n"):
                    if line.startswith("Total profit:"):
                        profit = line.split(":")[1].strip()
            print(f"  P2 Round {rnd}: {status} (profit: {profit})")

    print("\n[7/8] File checksums...")
    for f in ["eval.sh", "prepare.py", "compute_score.py", "datamodel.py"]:
        path = WORKDIR / f
        if path.exists():
            h = hashlib.sha256(path.read_bytes()).hexdigest()[:16]
            print(f"  {f}: {h}")

    print("\n[8/8] Tracking files...")
    results_path = WORKDIR / "results.tsv"
    if not results_path.exists():
        with open(results_path, "w") as f:
            f.write("commit\tcomposite_score\tp3_mm\tp3_statarb\tp3_options\tp3_full\tp3_stress\tp3_crashes\tp2_mm\tp2_basket\tp2_options\tp2_crashes\tstatus\tdescription\n")
        print("  Created results.tsv")

    for f, default in [("insights.md", "# Strategy Insights for P4\n\n(to be filled by experiments)\n"),
                       ("experiment_feedback.md", "# Experiment Feedback\n\n"),
                       ("research_queue.md", "# Research Queue\n(see program.md)\n")]:
        path = WORKDIR / f
        if not path.exists():
            path.write_text(default)
            print(f"  Created {f}")

    print("\n" + "=" * 60)
    print("SETUP COMPLETE")
    print("The trader probably crashes on P3 R1/R2 and all P2 rounds.")
    print("Fix this first — it's worth +300k-500k in composite score.")
    print("=" * 60)

if __name__ == "__main__":
    main()
