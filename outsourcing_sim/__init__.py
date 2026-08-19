"""outsourcing_sim: abstract agent-based model of client (A) vs contractor (B)
technology-outsourcing dynamics.

See docs/DESIGN.md for the full mathematical model description.
"""

from .params import SimParams
from .tiers import ModelTier, TIERS
from .model import capability, credit_cost, success_probability, time_required
from .agents import ClientState, ContractorState
from .simulate import run_game, run_many

__all__ = [
    "SimParams",
    "ModelTier",
    "TIERS",
    "capability",
    "credit_cost",
    "success_probability",
    "time_required",
    "ClientState",
    "ContractorState",
    "run_game",
    "run_many",
]
