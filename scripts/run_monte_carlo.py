"""Monte Carlo + parameter sweep runner (Stage 2 "focused factorial" style,
but flexible enough for ad-hoc sweeps too).

Usage:
    python scripts/run_monte_carlo.py --grid configs/example_grid.json --n-seeds 200 --out results/mc.parquet

The grid file is a JSON object mapping SimParams field names to a list of
values to sweep (a full factorial over all listed fields, crossed with all
listed values). Any SimParams field not listed uses its baseline default.
"""
from __future__ import annotations

import argparse
import itertools
import json
import os

import pandas as pd

from outsourcing_sim import SimParams
from outsourcing_sim.simulate import run_many

DEFAULT_GRID = {
    "strategy": ["conservative", "cost_optimal", "adaptive"],
}


def load_grid(path: str | None) -> dict:
    if not path:
        return DEFAULT_GRID
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def iter_param_combos(grid: dict):
    keys = list(grid.keys())
    value_lists = [grid[k] for k in keys]
    for combo in itertools.product(*value_lists):
        yield dict(zip(keys, combo))


def main():
    ap = argparse.ArgumentParser(description="Run Monte Carlo parameter sweep")
    ap.add_argument("--grid", type=str, default=None, help="path to a JSON grid file")
    ap.add_argument("--n-seeds", type=int, default=200, help="Monte Carlo replications per design point")
    ap.add_argument("--base-seed", type=int, default=0)
    ap.add_argument("--out", type=str, default="results/mc.parquet")
    args = ap.parse_args()

    grid = load_grid(args.grid)
    all_summaries = []
    for combo_idx, overrides in enumerate(iter_param_combos(grid)):
        base = SimParams()
        params = SimParams(**{**base.to_dict(), **overrides})
        summaries = run_many(params, n_seeds=args.n_seeds, base_seed=args.base_seed)
        for s in summaries:
            s["design_point"] = combo_idx
            s.update(overrides)
        all_summaries.extend(summaries)

    df = pd.DataFrame(all_summaries)
    out_dir = os.path.dirname(args.out)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    if args.out.endswith(".parquet"):
        df.to_parquet(args.out, index=False)
    else:
        df.to_csv(args.out, index=False)
    print(f"Wrote {len(df)} rows across {df['design_point'].nunique()} design points to {args.out}")


if __name__ == "__main__":
    main()
