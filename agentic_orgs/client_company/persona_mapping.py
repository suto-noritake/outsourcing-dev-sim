from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from outsourcing_sim.params import SimParams


Level = Literal["low", "medium", "high"]


@dataclass
class PersonaAssessment:
    ambition_level: Level
    strictness_level: Level
    factor_levels: dict[str, Level]
    rationale: dict[str, str]


def assess_persona(
    *,
    gamma: float,
    difficulty_0: float,
    budget_c0: float,
    budget_c1: float,
    partial_pay: float,
    r_min: float,
    max_consecutive_failures: int,
) -> PersonaAssessment:
    defaults = SimParams()
    factor_levels: dict[str, Level] = {
        "gamma": classify_vs_default(gamma, defaults.gamma),
        "difficulty_0": classify_vs_default(difficulty_0, defaults.difficulty_0),
        "budget_c0": classify_vs_default(budget_c0, defaults.budget_c0),
        "budget_c1": classify_vs_default(budget_c1, defaults.budget_c1),
        "partial_pay": classify_vs_default(partial_pay, defaults.partial_pay, inverse=True),
        "r_min": classify_vs_default(r_min, defaults.r_min),
        "max_consecutive_failures": classify_vs_default(
            float(max_consecutive_failures),
            float(defaults.max_consecutive_failures),
            inverse=True,
        ),
    }

    ambition_level = majority_level(
        [
            factor_levels["gamma"],
            factor_levels["difficulty_0"],
            factor_levels["budget_c0"],
            factor_levels["budget_c1"],
        ]
    )
    strictness_level = majority_level(
        [
            factor_levels["partial_pay"],
            factor_levels["r_min"],
            factor_levels["max_consecutive_failures"],
        ]
    )

    rationale = {
        "ambition": _ambition_rationale(ambition_level),
        "strictness": _strictness_rationale(strictness_level),
    }
    return PersonaAssessment(
        ambition_level=ambition_level,
        strictness_level=strictness_level,
        factor_levels=factor_levels,
        rationale=rationale,
    )


def classify_vs_default(value: float, default: float, *, inverse: bool = False) -> Level:
    if default == 0:
        if value == 0:
            base_level: Level = "medium"
        elif value > 0:
            base_level = "high"
        else:
            base_level = "low"
    else:
        ratio = value / default
        if ratio < 0.7:
            base_level = "low"
        elif ratio > 1.3:
            base_level = "high"
        else:
            base_level = "medium"

    if not inverse:
        return base_level
    return {"low": "high", "medium": "medium", "high": "low"}[base_level]


def majority_level(levels: list[Level]) -> Level:
    counts = {"low": 0, "medium": 0, "high": 0}
    for level in levels:
        counts[level] += 1

    highest = max(counts.values())
    winners = [level for level, count in counts.items() if count == highest]
    if len(winners) != 1:
        return "medium"
    return winners[0]


def _ambition_rationale(level: Level) -> str:
    if level == "high":
        return "高い成長志向。要求の難易度を積極的に引き上げ、予算も攻めた配分を取りやすい。"
    if level == "low":
        return "慎重志向。初期要求を抑え、予算や難易度の上げ方も段階的。"
    return "バランス志向。成長と実現可能性の均衡を重視する。"


def _strictness_rationale(level: Level) -> str:
    if level == "high":
        return "審査が厳格。失敗への許容が低く、品質ゲートを明確に求める。"
    if level == "low":
        return "審査が寛容。改善余地を重視し、段階的な品質向上を許容する。"
    return "中庸な審査姿勢。品質を求めつつ、合理的な改善機会は認める。"

