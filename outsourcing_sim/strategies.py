"""Contractor (B) investment strategies: how to choose (model tier, n agents)
each round. This choice is itself the primary treatment variable (#13 in
docs/experiment_design.md) — we compare strategies rather than hand-pick one.
"""
from __future__ import annotations

import itertools

from .agents import ContractorState
from .model import capability, credit_cost, success_probability
from .params import SimParams
from .tiers import TIER_ORDER

# Candidate agent counts to search over. Kept small/discrete for tractability;
# diminishing returns (alpha) make very large n rarely worthwhile anyway.
N_CANDIDATES = (1, 2, 3, 5, 8, 13)


def _expected_cost(tier_name: str, n: int, difficulty: float, params: SimParams) -> float:
    # Expected cost ignoring stochastic noise (E[lognormal(0, sigma)] = exp(sigma^2/2))
    import math

    return credit_cost(tier_name, n, difficulty, params, rng=None) * math.exp(
        params.sigma_noise**2 / 2
    )


def _all_combos():
    return list(itertools.product(TIER_ORDER, N_CANDIDATES))


def conservative_strategy(
    contractor: ContractorState, difficulty: float, params: SimParams, budget_fraction: float = 0.5
) -> tuple[str, int]:
    """Maximize capability (=> success probability) subject to spending at
    most `budget_fraction` of current funds this round.
    """
    safety_budget = contractor.funds * budget_fraction
    best = None
    best_cap = -1.0
    for tier_name, n in _all_combos():
        cost = _expected_cost(tier_name, n, difficulty, params)
        if cost > safety_budget:
            continue
        cap = capability(tier_name, n, params.alpha)
        if cap > best_cap:
            best_cap = cap
            best = (tier_name, n)
    if best is None:
        # Can't safely afford anything meaningful; take the cheapest option.
        return (TIER_ORDER[0], 1)
    return best


def cost_optimal_strategy(
    contractor: ContractorState,
    difficulty: float,
    params: SimParams,
    target_success_prob: float = 0.6,
) -> tuple[str, int]:
    """Pick the cheapest (tier, n) combo whose (noise-free) success
    probability meets `target_success_prob`; fall back to a conservative
    pick with a tight budget fraction if nothing qualifies.
    """
    best = None
    best_cost = float("inf")
    for tier_name, n in _all_combos():
        cap = capability(tier_name, n, params.alpha)
        p = success_probability(cap, difficulty, params.beta)
        if p < target_success_prob:
            continue
        cost = _expected_cost(tier_name, n, difficulty, params)
        if cost < best_cost:
            best_cost = cost
            best = (tier_name, n)
    if best is None:
        return conservative_strategy(contractor, difficulty, params, budget_fraction=0.2)
    return best


def adaptive_strategy(
    contractor: ContractorState, difficulty: float, params: SimParams, window: int = 5
) -> tuple[str, int]:
    """Adjust aggressiveness based on recent track record and remaining
    funding runway: struggling (low recent success rate or thin runway)
    -> invest more heavily to raise success odds; comfortable -> economize.
    """
    recent = contractor.history[-window:]
    recent_success_rate = sum(recent) / len(recent) if recent else 0.5
    runway_rounds = (
        contractor.funds / contractor.avg_burn_rate if contractor.avg_burn_rate > 1e-9 else float("inf")
    )

    if runway_rounds < 3:
        # Cash is nearly gone: go cheap and hope, rather than risk instant bankruptcy.
        return cost_optimal_strategy(contractor, difficulty, params, target_success_prob=0.4)
    if recent_success_rate < 0.5:
        # Struggling on delivery: invest more to raise the success chance.
        return conservative_strategy(contractor, difficulty, params, budget_fraction=0.5)
    # Doing fine: economize while keeping a solid success chance.
    return cost_optimal_strategy(contractor, difficulty, params, target_success_prob=0.7)


STRATEGIES = {
    "conservative": conservative_strategy,
    "cost_optimal": cost_optimal_strategy,
    "adaptive": adaptive_strategy,
}
