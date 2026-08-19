import math

import numpy as np
import pytest

from outsourcing_sim import SimParams
from outsourcing_sim.model import (
    capability,
    capability_margin,
    credit_cost,
    funding_runway,
    quadrant,
    success_probability,
    time_required,
)
from outsourcing_sim.simulate import run_game, run_many, summarize_trace
from outsourcing_sim.strategies import (
    STRATEGIES,
    conservative_strategy,
    cost_optimal_strategy,
)
from outsourcing_sim.agents import ContractorState


def test_capability_increases_with_tier_and_agents():
    low = capability("low", 1, alpha=0.6)
    mid = capability("mid", 1, alpha=0.6)
    assert mid > low
    more_agents = capability("low", 5, alpha=0.6)
    assert more_agents > low


def test_capability_diminishing_returns():
    alpha = 0.5
    cap1 = capability("mid", 1, alpha)
    cap2 = capability("mid", 2, alpha)
    cap4 = capability("mid", 4, alpha)
    # doubling agents should not double capability (alpha < 1)
    assert cap2 < 2 * cap1
    assert cap4 < 2 * cap2


def test_success_probability_monotonic_and_bounded():
    p_low = success_probability(cap=1.0, difficulty=5.0, beta=3.0)
    p_high = success_probability(cap=10.0, difficulty=5.0, beta=3.0)
    assert 0.0 <= p_low <= 1.0
    assert 0.0 <= p_high <= 1.0
    assert p_high > p_low
    # at cap == difficulty, probability should be exactly 0.5
    assert math.isclose(success_probability(cap=5.0, difficulty=5.0, beta=3.0), 0.5, abs_tol=1e-9)


def test_credit_cost_scales_with_difficulty_and_tier():
    params = SimParams(sigma_noise=0.0)
    cost_low = credit_cost("low", 1, difficulty=1.0, params=params)
    cost_frontier = credit_cost("frontier", 1, difficulty=1.0, params=params)
    assert cost_frontier > cost_low
    cost_high_diff = credit_cost("low", 1, difficulty=5.0, params=params)
    assert cost_high_diff > cost_low


def test_time_required_decreases_with_capability():
    t_low_cap = time_required(cap=1.0, difficulty=5.0)
    t_high_cap = time_required(cap=10.0, difficulty=5.0)
    assert t_high_cap < t_low_cap


def test_quadrant_classification():
    assert quadrant(cap_margin=1.0, runway=10.0) == "dominant_leader"
    assert quadrant(cap_margin=1.0, runway=1.0) == "cash_starved_specialist"
    assert quadrant(cap_margin=-1.0, runway=10.0) == "deep_pockets_shallow_skills"
    assert quadrant(cap_margin=-1.0, runway=1.0) == "exit_candidate"


def test_funding_runway_infinite_when_no_burn():
    assert funding_runway(funds=100, avg_burn_rate=0.0) == float("inf")


@pytest.mark.parametrize("strategy", ["conservative", "cost_optimal", "adaptive"])
def test_strategies_return_valid_combo(strategy):
    contractor = ContractorState(funds=100.0)
    fn = STRATEGIES[strategy]
    params = SimParams(strategy=strategy)
    tier, n = fn(contractor, difficulty=1.0, params=params)
    assert tier in ("low", "mid", "high", "frontier")
    assert isinstance(n, int) and n >= 1


def test_conservative_more_aggressive_than_cost_optimal_on_expensive_case():
    contractor = ContractorState(funds=1000.0)
    params = SimParams()
    tier_c, n_c = conservative_strategy(contractor, difficulty=1.0, params=params, budget_fraction=0.9)
    tier_co, n_co = cost_optimal_strategy(contractor, difficulty=1.0, params=params, target_success_prob=0.5)
    cap_c = capability(tier_c, n_c, params.alpha)
    cap_co = capability(tier_co, n_co, params.alpha)
    assert cap_c >= cap_co


def test_run_game_terminates_and_produces_valid_trace():
    params = SimParams(max_rounds=50, funds_0=50.0, seed=42)
    rng = np.random.default_rng(42)
    trace = run_game(params, rng=rng)
    assert len(trace) > 0
    assert len(trace) <= params.max_rounds
    for record in trace:
        assert record["capability"] > 0
        assert record["quadrant"] in (
            "dominant_leader",
            "cash_starved_specialist",
            "deep_pockets_shallow_skills",
            "exit_candidate",
        )


def test_run_game_bankruptcy_with_tiny_funds():
    params = SimParams(max_rounds=50, funds_0=0.01, strategy="conservative", seed=1)
    rng = np.random.default_rng(1)
    trace = run_game(params, rng=rng)
    assert trace[-1]["bankrupt"] is True


def test_run_many_returns_summaries_for_each_seed():
    params = SimParams(max_rounds=20, funds_0=50.0)
    summaries = run_many(params, n_seeds=5)
    assert len(summaries) == 5
    for s in summaries:
        assert "survival_rounds" in s
        assert "success_rate" in s
        assert 0.0 <= s["success_rate"] <= 1.0


def test_summarize_trace_computes_expected_fields():
    params = SimParams(max_rounds=20, funds_0=50.0, seed=7)
    rng = np.random.default_rng(7)
    trace = run_game(params, rng=rng)
    summary = summarize_trace(trace, params, seed=7)
    assert summary["survival_rounds"] == len(trace)
    assert summary["end_reason"] in ("bankrupt", "max_rounds", "contract_terminated")
