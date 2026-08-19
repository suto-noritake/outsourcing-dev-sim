"""Round-by-round simulation of the 1-on-1 repeated game between client A and
contractor B (docs/DESIGN.md), plus Monte Carlo batch running.
"""
from __future__ import annotations

from dataclasses import asdict
from typing import Any

import numpy as np

from .agents import ClientState, ContractorState
from .model import capability, credit_cost, funding_runway, quadrant, success_probability
from .params import SimParams
from .strategies import STRATEGIES


def run_game(params: SimParams, rng: np.random.Generator | None = None) -> list[dict[str, Any]]:
    """Run a single 1-on-1 repeated game to completion (bankruptcy, contract
    termination, or max_rounds) and return the full round-by-round trace.
    """
    if rng is None:
        rng = np.random.default_rng(params.seed)

    strategy_fn = STRATEGIES[params.strategy]

    client = ClientState(difficulty=params.difficulty_0, budget=_budget_for(params, params.difficulty_0, 1.0))
    contractor = ContractorState(funds=params.funds_0)

    trace: list[dict[str, Any]] = []

    for t in range(1, params.max_rounds + 1):
        tier_name, n = strategy_fn(contractor, client.difficulty, params)
        cap = capability(tier_name, n, params.alpha)
        cost = credit_cost(tier_name, n, client.difficulty, params, rng=rng)

        contractor.funds -= cost
        contractor.avg_burn_rate = (
            cost if contractor.avg_burn_rate == 0 else 0.3 * cost + 0.7 * contractor.avg_burn_rate
        )

        bankrupt_this_round = contractor.funds < 0
        p_success = success_probability(cap, client.difficulty, params.beta)
        success = bool(rng.random() < p_success) and not bankrupt_this_round

        payment = 0.0
        if not bankrupt_this_round:
            payment = client.budget if success else client.budget * params.partial_pay
            contractor.funds += payment

        contractor.history.append(success)
        contractor.last_tier, contractor.last_n = tier_name, n

        client.reputation = params.lam * client.reputation + (1 - params.lam) * (1.0 if success else 0.0)
        client.consecutive_failures = 0 if success else client.consecutive_failures + 1

        cap_margin = cap - client.difficulty
        runway = funding_runway(contractor.funds, contractor.avg_burn_rate)
        quad = quadrant(cap_margin, runway)

        record = {
            "round": t,
            "tier": tier_name,
            "n_agents": n,
            "capability": cap,
            "difficulty": client.difficulty,
            "cost": cost,
            "payment": payment,
            "success": success,
            "funds": contractor.funds,
            "reputation": client.reputation,
            "capability_margin": cap_margin,
            "funding_runway": runway,
            "quadrant": quad,
            "bankrupt": bankrupt_this_round,
        }
        trace.append(record)

        if bankrupt_this_round:
            contractor.bankrupt = True
            break

        terminated = (
            client.consecutive_failures >= params.max_consecutive_failures
            or client.reputation < params.r_min
        )
        if terminated:
            client.terminated = True
            client.termination_reason = (
                "consecutive_failures" if client.consecutive_failures >= params.max_consecutive_failures
                else "low_reputation"
            )
            break

        # A's next-round policy update
        if success:
            client.difficulty = min(client.difficulty * (1 + params.gamma), params.difficulty_cap)
        client.budget = _budget_for(params, client.difficulty, client.reputation)

    return trace


def _budget_for(params: SimParams, difficulty: float, reputation: float) -> float:
    return params.budget_c0 + params.budget_c1 * difficulty * (0.5 + 0.5 * reputation)


def summarize_trace(trace: list[dict[str, Any]], params: SimParams, seed: int) -> dict[str, Any]:
    if not trace:
        return {}
    n_rounds = len(trace)
    successes = sum(1 for r in trace if r["success"])
    last = trace[-1]
    end_reason = "bankrupt" if last["bankrupt"] else (
        "max_rounds" if n_rounds >= params.max_rounds else "contract_terminated"
    )
    return {
        "seed": seed,
        "strategy": params.strategy,
        "survival_rounds": n_rounds,
        "success_rate": successes / n_rounds,
        "final_funds": last["funds"],
        "final_difficulty": last["difficulty"],
        "final_quadrant": last["quadrant"],
        "end_reason": end_reason,
        "total_cost": sum(r["cost"] for r in trace),
        "total_payment": sum(r["payment"] for r in trace),
        "net_profit": sum(r["payment"] for r in trace) - sum(r["cost"] for r in trace),
    }


def run_many(params: SimParams, n_seeds: int, base_seed: int = 0, keep_traces: bool = False):
    """Monte Carlo batch: run `n_seeds` independent games with the same
    parameters (different RNG seeds) and return a list of summary dicts
    (and optionally the full traces for later quadrant-trajectory plots).
    """
    summaries = []
    traces = [] if keep_traces else None
    for i in range(n_seeds):
        seed = base_seed + i
        rng = np.random.default_rng(seed)
        run_params = SimParams(**{**params.to_dict(), "seed": seed})
        trace = run_game(run_params, rng=rng)
        summary = summarize_trace(trace, run_params, seed)
        summary.update({k: v for k, v in run_params.to_dict().items() if k not in summary})
        summaries.append(summary)
        if keep_traces:
            traces.append(trace)
    if keep_traces:
        return summaries, traces
    return summaries
