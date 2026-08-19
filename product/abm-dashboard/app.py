from __future__ import annotations

import math
import sys
import time
from pathlib import Path
from typing import Literal

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, model_validator

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from outsourcing_sim.params import SimParams
from outsourcing_sim.simulate import run_many

StrategyName = Literal["conservative", "cost_optimal", "adaptive"]
STRATEGY_ORDER: tuple[StrategyName, ...] = ("conservative", "cost_optimal", "adaptive")
RUNWAY_CLIP = 1e9


class SimParamsInput(BaseModel):
    alpha: float = Field(default=0.6, gt=0.0, le=2.0)
    beta: float = Field(default=3.0, gt=0.0, le=20.0)
    lam: float = Field(default=0.7, ge=0.0, le=1.0)
    k1: float = Field(default=1.0, gt=0.0)
    cost_curve_exponent: float = Field(default=2.0, ge=0.5, le=5.0)
    sigma_noise: float = Field(default=0.3, ge=0.0, le=2.0)
    gamma: float = Field(default=0.15, ge=0.0, le=2.0)
    partial_pay: float = Field(default=0.0, ge=0.0, le=1.0)
    r_min: float = Field(default=0.4, ge=0.0, le=1.0)
    max_consecutive_failures: int = Field(default=3, ge=1, le=50)
    difficulty_0: float = Field(default=1.0, gt=0.0)
    funds_0: float = Field(default=100.0, gt=0.0)
    difficulty_cap: float = Field(default=20.0, gt=0.0)
    budget_c0: float = Field(default=5.0, ge=0.0)
    budget_c1: float = Field(default=15.0, ge=0.0)
    max_rounds: int = Field(default=200, ge=1, le=1000)
    strategy: StrategyName = "adaptive"

    @model_validator(mode="after")
    def validate_cap(self) -> "SimParamsInput":
        if self.difficulty_cap < self.difficulty_0:
            raise ValueError("difficulty_cap must be greater than or equal to difficulty_0")
        return self


class SimulateRequest(BaseModel):
    params: SimParamsInput = Field(default_factory=SimParamsInput)
    n_trials: int = Field(default=100, ge=1, le=500)
    base_seed: int = 0
    compare_strategies: bool = False


class StrategyAggregate(BaseModel):
    success_rate: float
    bankruptcy_rate: float
    mean_survival_rounds: float
    mean_net_profit: float


class TrialResult(BaseModel):
    seed: int
    strategy: StrategyName
    survival_rounds: int
    success_rate: float
    net_profit: float
    end_reason: str
    final_quadrant: str
    final_capability_margin: float
    final_funding_runway: float


class QuadrantPoint(BaseModel):
    x: float
    y: float
    quadrant: str
    seed: int
    strategy: StrategyName


class SurvivalHistogram(BaseModel):
    values: list[int]


class PlotData(BaseModel):
    quadrant_points: list[QuadrantPoint]
    survival_histogram: SurvivalHistogram


class MetaInfo(BaseModel):
    n_trials: int
    elapsed_seconds: float
    compare_strategies: bool
    strategies_run: list[StrategyName]


class SimulateResponse(BaseModel):
    meta: MetaInfo
    aggregates: dict[str, StrategyAggregate]
    per_trial: list[TrialResult]
    plot_data: PlotData


def _clip_runway(value: float) -> float:
    numeric = float(value)
    if not math.isfinite(numeric):
        return RUNWAY_CLIP
    if numeric > RUNWAY_CLIP:
        return RUNWAY_CLIP
    if numeric < -RUNWAY_CLIP:
        return -RUNWAY_CLIP
    return numeric


def _build_trial_results(
    strategy: StrategyName,
    params_input: SimParamsInput,
    n_trials: int,
    base_seed: int,
) -> list[TrialResult]:
    params_dict = params_input.model_dump()
    params_dict["strategy"] = strategy
    sim_params = SimParams(**params_dict)
    summaries, traces = run_many(sim_params, n_trials, base_seed=base_seed, keep_traces=True)

    results: list[TrialResult] = []
    for summary, trace in zip(summaries, traces):
        last = trace[-1]
        result = TrialResult(
            seed=int(summary["seed"]),
            strategy=strategy,
            survival_rounds=int(summary["survival_rounds"]),
            success_rate=float(summary["success_rate"]),
            net_profit=float(summary["net_profit"]),
            end_reason=str(summary["end_reason"]),
            final_quadrant=str(summary["final_quadrant"]),
            final_capability_margin=float(last["capability_margin"]),
            final_funding_runway=_clip_runway(last["funding_runway"]),
        )
        results.append(result)
    return results


def _aggregate_for_strategy(results: list[TrialResult]) -> StrategyAggregate:
    count = len(results)
    success_rate = sum(float(item.success_rate) for item in results) / count
    bankruptcy_rate = (
        sum(1 for item in results if item.end_reason == "bankrupt") / count
    )
    mean_survival_rounds = sum(int(item.survival_rounds) for item in results) / count
    mean_net_profit = sum(float(item.net_profit) for item in results) / count
    return StrategyAggregate(
        success_rate=float(success_rate),
        bankruptcy_rate=float(bankruptcy_rate),
        mean_survival_rounds=float(mean_survival_rounds),
        mean_net_profit=float(mean_net_profit),
    )


BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(title="ABM Dashboard API", version="1.0.0")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
def root() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.post("/api/simulate", response_model=SimulateResponse)
def simulate(request: SimulateRequest) -> SimulateResponse:
    started_at = time.perf_counter()
    strategies_run: list[StrategyName] = (
        list(STRATEGY_ORDER) if request.compare_strategies else [request.params.strategy]
    )

    aggregates: dict[str, StrategyAggregate] = {}
    per_trial: list[TrialResult] = []

    for strategy in strategies_run:
        strategy_results = _build_trial_results(
            strategy=strategy,
            params_input=request.params,
            n_trials=int(request.n_trials),
            base_seed=int(request.base_seed),
        )
        aggregates[strategy] = _aggregate_for_strategy(strategy_results)
        per_trial.extend(strategy_results)

    quadrant_points = [
        QuadrantPoint(
            x=float(item.final_capability_margin),
            y=float(item.final_funding_runway),
            quadrant=str(item.final_quadrant),
            seed=int(item.seed),
            strategy=item.strategy,
        )
        for item in per_trial
    ]
    survival_values = [int(item.survival_rounds) for item in per_trial]

    elapsed_seconds = float(time.perf_counter() - started_at)
    return SimulateResponse(
        meta=MetaInfo(
            n_trials=int(request.n_trials),
            elapsed_seconds=elapsed_seconds,
            compare_strategies=bool(request.compare_strategies),
            strategies_run=strategies_run,
        ),
        aggregates=aggregates,
        per_trial=per_trial,
        plot_data=PlotData(
            quadrant_points=quadrant_points,
            survival_histogram=SurvivalHistogram(values=survival_values),
        ),
    )
