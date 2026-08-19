"""State dataclasses for the client (A) and contractor (B) agents."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ClientState:
    difficulty: float
    budget: float
    reputation: float = 1.0
    consecutive_failures: int = 0
    terminated: bool = False
    termination_reason: str | None = None


@dataclass
class ContractorState:
    funds: float
    bankrupt: bool = False
    avg_burn_rate: float = 0.0
    history: list = field(default_factory=list)  # list of (success: bool)
    last_tier: str = "mid"
    last_n: int = 1
