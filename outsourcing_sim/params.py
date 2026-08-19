"""All tunable parameters of the abstract ABM (see docs/experiment_design.md).

Baseline values match the "Baseline" column of the parameter matrix table.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SimParams:
    # --- structural parameters ---
    alpha: float = 0.6  # agent-count diminishing-returns exponent
    beta: float = 3.0  # success-probability sensitivity
    lam: float = 0.7  # reputation EMA smoothing factor
    k1: float = 1.0  # base credit-cost scale
    cost_curve_exponent: float = 2.0  # 1=linear, 2=quadratic, 3=cubic
    sigma_noise: float = 0.3  # log-normal sigma for cost/time noise

    # --- A (client) policy parameters ---
    gamma: float = 0.15  # difficulty escalation rate on success
    partial_pay: float = 0.0  # partial payment ratio on failure
    r_min: float = 0.4  # reputation floor -> contract termination
    max_consecutive_failures: int = 3  # K

    # --- environment parameters ---
    difficulty_0: float = 1.0  # initial difficulty D_0
    funds_0: float = 100.0  # initial contractor funds (~10 mid-size projects)
    difficulty_cap: float = 20.0  # escalation ceiling

    # --- budget policy ---
    budget_c0: float = 5.0
    budget_c1: float = 15.0

    # --- run control ---
    max_rounds: int = 200
    seed: int | None = None

    # --- B (contractor) strategy ---
    strategy: str = "adaptive"  # "conservative" | "cost_optimal" | "adaptive"

    def to_dict(self) -> dict:
        return self.__dict__.copy()
