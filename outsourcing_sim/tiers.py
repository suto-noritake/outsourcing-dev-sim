"""Discrete model performance tiers.

Each tier has a performance score `perf` and a *base* cost multiplier
`base_cost_mult`. The realized cost multiplier additionally depends on
`cost_curve` (how steeply cost grows relative to tier rank), see
`model.credit_cost`.

This deliberately mirrors real-world LLM API pricing: moving to a more
capable tier increases performance sub-linearly relative to the increase
in per-token / per-call price.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelTier:
    name: str
    rank: int  # 1..4, used as the exponent base for cost curves
    perf: float
    base_cost_mult: float


TIERS: dict[str, ModelTier] = {
    "low": ModelTier("low", 1, perf=1.0, base_cost_mult=1.0),
    "mid": ModelTier("mid", 2, perf=2.5, base_cost_mult=3.0),
    "high": ModelTier("high", 3, perf=4.0, base_cost_mult=8.0),
    "frontier": ModelTier("frontier", 4, perf=6.0, base_cost_mult=20.0),
}

TIER_ORDER = ["low", "mid", "high", "frontier"]


def cost_curve_multiplier(tier: ModelTier, cost_curve_exponent: float) -> float:
    """Return the effective cost multiplier for a tier given a cost-curve
    steepness exponent (1=linear, 2=quadratic, 3=cubic in tier rank).

    We blend the tier's base_cost_mult (calibrated for the quadratic
    default) with a pure rank^exponent curve so that `cost_curve_exponent`
    can be swept continuously in experiments (parameter #6 in
    docs/experiment_design.md).
    """
    baseline_exponent = 2.0
    scale = tier.base_cost_mult / (tier.rank**baseline_exponent)
    return scale * (tier.rank**cost_curve_exponent)
