"""Core mathematical functions of the model (docs/DESIGN.md).

All functions are pure (no hidden state) so they are easy to unit test and
reuse from the Monte Carlo runner, the screening design, and (later) as a
reference when calibrating the LLM multi-agent experiments in Phase 4.
"""
from __future__ import annotations

import math

from .params import SimParams
from .tiers import TIERS, cost_curve_multiplier


def capability(tier_name: str, n_agents: int, alpha: float) -> float:
    """Capability(m, n) = perf(m) * n^alpha."""
    tier = TIERS[tier_name]
    n = max(n_agents, 1)
    return tier.perf * (n**alpha)


def credit_cost(
    tier_name: str,
    n_agents: int,
    difficulty: float,
    params: SimParams,
    rng: "np.random.Generator | None" = None,
) -> float:
    """CreditCost(m, n, D) = k1 * cost_mult(m) * n * D * noise."""
    tier = TIERS[tier_name]
    mult = cost_curve_multiplier(tier, params.cost_curve_exponent)
    noise = 1.0
    if rng is not None:
        noise = rng.lognormal(mean=0.0, sigma=params.sigma_noise)
    return params.k1 * mult * max(n_agents, 1) * difficulty * noise


def success_probability(cap: float, difficulty: float, beta: float) -> float:
    """P_success = sigmoid(beta * (Capability - D))."""
    x = beta * (cap - difficulty)
    # numerically stable sigmoid
    if x >= 0:
        z = math.exp(-x)
        return 1.0 / (1.0 + z)
    z = math.exp(x)
    return z / (1.0 + z)


def time_required(
    cap: float,
    difficulty: float,
    time_const: float = 1.0,
    rng: "np.random.Generator | None" = None,
    sigma_noise: float = 0.3,
) -> float:
    """Time = time_const * D / Capability * noise."""
    noise = 1.0
    if rng is not None:
        noise = rng.lognormal(mean=0.0, sigma=sigma_noise)
    return time_const * difficulty / max(cap, 1e-6) * noise


def capability_margin(tier_name: str, n_agents: int, difficulty: float, alpha: float) -> float:
    """X-axis of the quadrant framework: Capability - Difficulty."""
    return capability(tier_name, n_agents, alpha) - difficulty


def funding_runway(funds: float, avg_burn_rate: float) -> float:
    """Y-axis of the quadrant framework: Funds / average burn rate.

    Returns the number of rounds B could sustain at its recent average
    spending rate.
    """
    if avg_burn_rate <= 1e-9:
        return float("inf")
    return funds / avg_burn_rate


def quadrant(cap_margin: float, runway: float, runway_threshold: float = 5.0) -> str:
    """Classify a (capability_margin, funding_runway) point into one of the
    four archetypes described in docs/DESIGN.md.
    """
    tech_ok = cap_margin >= 0
    funds_ok = runway >= runway_threshold
    if tech_ok and funds_ok:
        return "dominant_leader"  # (1) 独走勝ち組型
    if tech_ok and not funds_ok:
        return "cash_starved_specialist"  # (2) 宝の持ち腐れ/燃え尽き型
    if not tech_ok and funds_ok:
        return "deep_pockets_shallow_skills"  # (3) 物量型/時間稼ぎ型
    return "exit_candidate"  # (4) 淘汰予備軍型
