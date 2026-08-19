"""Stage 0: pilot trials at the baseline configuration to estimate outcome
variance and compute the replication count needed for a target confidence
interval width (docs/experiment_design.md, Stage 0).
"""
from __future__ import annotations

import argparse
import json
import math

import pandas as pd

from outsourcing_sim import SimParams
from outsourcing_sim.simulate import run_many


def required_n_for_proportion(p: float, half_width: float, z: float = 1.96) -> int:
    p = min(max(p, 1e-6), 1 - 1e-6)
    return math.ceil((z / half_width) ** 2 * p * (1 - p))


def main():
    ap = argparse.ArgumentParser(description="Run pilot trials at baseline params")
    ap.add_argument("--n", type=int, default=200, help="number of pilot seeds")
    ap.add_argument("--strategy", type=str, default="adaptive")
    ap.add_argument("--half-width", type=float, default=0.02, help="target 95%% CI half-width for success_rate")
    ap.add_argument("--out", type=str, default="results/pilot_summary.csv")
    args = ap.parse_args()

    params = SimParams(strategy=args.strategy)
    summaries = run_many(params, n_seeds=args.n)
    df = pd.DataFrame(summaries)

    import os

    os.makedirs(os.path.dirname(args.out), exist_ok=True) if os.path.dirname(args.out) else None
    df.to_csv(args.out, index=False)

    stats = {
        "n_pilot": args.n,
        "mean_success_rate": df["success_rate"].mean(),
        "std_success_rate": df["success_rate"].std(),
        "mean_survival_rounds": df["survival_rounds"].mean(),
        "std_survival_rounds": df["survival_rounds"].std(),
        "bankruptcy_rate": (df["end_reason"] == "bankrupt").mean(),
        "required_n_success_rate_ci": required_n_for_proportion(
            df["success_rate"].mean(), args.half_width
        ),
    }
    print(json.dumps(stats, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
