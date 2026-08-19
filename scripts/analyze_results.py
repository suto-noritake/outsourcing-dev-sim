"""Aggregate & visualize Monte Carlo results produced by run_monte_carlo.py
or run_pilot.py: success rate, bankruptcy rate, survival rounds, profit,
and the distribution across the 2-axis quadrant framework
(docs/DESIGN.md: Capability Margin x Funding Runway).
"""
from __future__ import annotations

import argparse
import os

import matplotlib.pyplot as plt
import pandas as pd


def load(path: str) -> pd.DataFrame:
    if path.endswith(".parquet"):
        return pd.read_parquet(path)
    return pd.read_csv(path)


def main():
    ap = argparse.ArgumentParser(description="Analyze Monte Carlo simulation results")
    ap.add_argument("--input", type=str, required=True)
    ap.add_argument("--out-dir", type=str, default="results/figures")
    args = ap.parse_args()

    df = load(args.input)
    os.makedirs(args.out_dir, exist_ok=True)

    group_col = "strategy" if "strategy" in df.columns else None

    print("=== Summary by strategy ===")
    if group_col:
        summary = df.groupby(group_col).agg(
            n=("seed", "count"),
            mean_success_rate=("success_rate", "mean"),
            mean_survival_rounds=("survival_rounds", "mean"),
            bankruptcy_rate=("end_reason", lambda s: (s == "bankrupt").mean()),
            mean_net_profit=("net_profit", "mean"),
        )
        print(summary.to_string())
        summary.to_csv(os.path.join(args.out_dir, "summary_by_strategy.csv"))

    # Quadrant distribution (final state) by strategy
    if "final_quadrant" in df.columns and group_col:
        quad_counts = (
            df.groupby([group_col, "final_quadrant"]).size().unstack(fill_value=0)
        )
        quad_props = quad_counts.div(quad_counts.sum(axis=1), axis=0)
        print("\n=== Final-state quadrant distribution (proportion) by strategy ===")
        print(quad_props.to_string())

        ax = quad_props.plot(kind="bar", stacked=True, figsize=(8, 5))
        ax.set_ylabel("proportion of runs")
        ax.set_title("Final quadrant distribution by contractor strategy")
        plt.tight_layout()
        fig_path = os.path.join(args.out_dir, "quadrant_distribution.png")
        plt.savefig(fig_path, dpi=150)
        print(f"\nSaved {fig_path}")

    # Survival rounds distribution
    if "survival_rounds" in df.columns and group_col:
        plt.figure(figsize=(8, 5))
        for name, sub in df.groupby(group_col):
            sub["survival_rounds"].plot(kind="hist", alpha=0.5, bins=30, label=name)
        plt.xlabel("survival rounds")
        plt.legend()
        plt.title("Survival rounds distribution by strategy")
        plt.tight_layout()
        fig_path = os.path.join(args.out_dir, "survival_rounds_hist.png")
        plt.savefig(fig_path, dpi=150)
        print(f"Saved {fig_path}")


if __name__ == "__main__":
    main()
