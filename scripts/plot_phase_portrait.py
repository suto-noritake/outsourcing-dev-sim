"""Plot the "phase portrait": contractor B trajectories through the 2-axis
quadrant framework (Capability Margin x Funding Runway, docs/DESIGN.md)
over the course of individual games, for a handful of example seeds per
strategy.
"""
from __future__ import annotations

import argparse
import os

import matplotlib.pyplot as plt
import numpy as np

from outsourcing_sim import SimParams
from outsourcing_sim.simulate import run_game

QUADRANT_COLORS = {
    "dominant_leader": "tab:green",
    "cash_starved_specialist": "tab:orange",
    "deep_pockets_shallow_skills": "tab:blue",
    "exit_candidate": "tab:red",
}

RUNWAY_CAP = 30  # clip for readability


def main():
    ap = argparse.ArgumentParser(description="Plot capability-margin x funding-runway phase portrait")
    ap.add_argument("--strategies", nargs="+", default=["conservative", "cost_optimal", "adaptive"])
    ap.add_argument("--n-games", type=int, default=5, help="example games to plot per strategy")
    ap.add_argument("--base-seed", type=int, default=0)
    ap.add_argument("--out", type=str, default="results/figures/phase_portrait.png")
    args = ap.parse_args()

    fig, axes = plt.subplots(1, len(args.strategies), figsize=(6 * len(args.strategies), 5), sharey=True)
    if len(args.strategies) == 1:
        axes = [axes]

    for ax, strategy in zip(axes, args.strategies):
        for g in range(args.n_games):
            seed = args.base_seed + g
            params = SimParams(strategy=strategy, seed=seed)
            rng = np.random.default_rng(seed)
            trace = run_game(params, rng=rng)
            xs = [r["capability_margin"] for r in trace]
            ys = [min(r["funding_runway"], RUNWAY_CAP) for r in trace]
            colors = [QUADRANT_COLORS[r["quadrant"]] for r in trace]
            ax.plot(xs, ys, "-", color="gray", alpha=0.4, linewidth=1)
            ax.scatter(xs, ys, c=colors, s=15)
            if xs:
                ax.scatter(xs[-1], ys[-1], c="black", marker="x", s=60)  # end-state marker

        ax.axvline(0, color="black", linewidth=0.8)
        ax.axhline(5, color="black", linewidth=0.8, linestyle="--")
        ax.set_title(strategy)
        ax.set_xlabel("Capability Margin (Capability - Difficulty)")

    axes[0].set_ylabel("Funding Runway (rounds)")

    handles = [
        plt.Line2D([0], [0], marker="o", color="w", markerfacecolor=c, markersize=8, label=k)
        for k, c in QUADRANT_COLORS.items()
    ]
    fig.legend(handles=handles, loc="upper center", ncol=4, bbox_to_anchor=(0.5, 1.08))
    fig.suptitle("")

    out_dir = os.path.dirname(args.out)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    plt.tight_layout()
    plt.savefig(args.out, dpi=150, bbox_inches="tight")
    print(f"Saved {args.out}")


if __name__ == "__main__":
    main()
