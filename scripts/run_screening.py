"""Stage 1: Morris-method screening design over the 12 structural /
environment / policy parameters (docs/experiment_design.md, Stage 1).

For each of the 3 contractor strategies (the primary treatment, always kept
separate rather than folded into the screening), this generates a Morris
trajectory sample over the 12 factors, runs a modest number of Monte Carlo
replications at each design point, and reports standardized elementary
effects (mu*, sigma) to rank which factors matter most.
"""
from __future__ import annotations

import argparse
import json
import os

import numpy as np
import pandas as pd
from SALib.analyze import morris as morris_analyze
from SALib.sample import morris as morris_sample

from outsourcing_sim import SimParams
from outsourcing_sim.simulate import run_many

# Screening ranges taken directly from the parameter matrix in
# docs/experiment_design.md (Low..High columns).
PROBLEM = {
    "num_vars": 12,
    "names": [
        "alpha",
        "beta",
        "gamma",
        "lam",
        "k1",
        "cost_curve_exponent",
        "partial_pay",
        "difficulty_0",
        "funds_0",
        "r_min",
        "max_consecutive_failures",
        "sigma_noise",
    ],
    "bounds": [
        [0.3, 0.9],
        [1.0, 8.0],
        [0.05, 0.3],
        [0.5, 0.9],
        [0.5, 2.0],
        [1.0, 3.0],
        [0.0, 0.5],
        [0.5, 2.0],
        [50.0, 200.0],
        [0.2, 0.6],
        [1.0, 5.0],
        [0.1, 0.6],
    ],
}


def run_for_strategy(strategy: str, n_trajectories: int, n_seeds: int, base_seed: int) -> pd.DataFrame:
    sample = morris_sample.sample(PROBLEM, N=n_trajectories, num_levels=4)
    responses_success = np.zeros(sample.shape[0])
    responses_survival = np.zeros(sample.shape[0])

    for i, row in enumerate(sample):
        overrides = dict(zip(PROBLEM["names"], row))
        overrides["max_consecutive_failures"] = max(1, round(overrides["max_consecutive_failures"]))
        base = SimParams(strategy=strategy)
        params = SimParams(**{**base.to_dict(), **overrides})
        summaries = run_many(params, n_seeds=n_seeds, base_seed=base_seed + i * 1000)
        df = pd.DataFrame(summaries)
        responses_success[i] = df["success_rate"].mean()
        responses_survival[i] = df["survival_rounds"].mean()

    result_success = morris_analyze.analyze(PROBLEM, sample, responses_success, print_to_console=False)
    result_survival = morris_analyze.analyze(PROBLEM, sample, responses_survival, print_to_console=False)

    out = pd.DataFrame(
        {
            "parameter": PROBLEM["names"],
            "mu_star_success_rate": result_success["mu_star"],
            "sigma_success_rate": result_success["sigma"],
            "mu_star_survival_rounds": result_survival["mu_star"],
            "sigma_survival_rounds": result_survival["sigma"],
        }
    )
    out["strategy"] = strategy
    return out


def main():
    ap = argparse.ArgumentParser(description="Morris screening design (Stage 1)")
    ap.add_argument("--n-trajectories", type=int, default=20, help="Morris N (trajectories per factor)")
    ap.add_argument("--n-seeds", type=int, default=50, help="Monte Carlo replications per design point")
    ap.add_argument("--base-seed", type=int, default=0)
    ap.add_argument("--strategies", nargs="+", default=["conservative", "cost_optimal", "adaptive"])
    ap.add_argument("--out", type=str, default="results/screening_morris.csv")
    args = ap.parse_args()

    all_results = []
    for strategy in args.strategies:
        print(f"Running Morris screening for strategy={strategy} ...")
        all_results.append(run_for_strategy(strategy, args.n_trajectories, args.n_seeds, args.base_seed))

    df = pd.concat(all_results, ignore_index=True)
    out_dir = os.path.dirname(args.out)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    df.to_csv(args.out, index=False)

    top = (
        df.groupby("parameter")["mu_star_success_rate"]
        .mean()
        .sort_values(ascending=False)
        .head(5)
    )
    print("Top parameters by mean |mu*| on success_rate across strategies:")
    print(top.to_string())
    print(f"\nFull results written to {args.out}")


if __name__ == "__main__":
    main()
