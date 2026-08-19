from __future__ import annotations

import json
import sys
from pathlib import Path

from fastapi.testclient import TestClient

APP_DIR = Path(__file__).resolve().parents[1]
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from app import app

client = TestClient(app)

VALID_QUADRANTS = {
    "dominant_leader",
    "cash_starved_specialist",
    "deep_pockets_shallow_skills",
    "exit_candidate",
}


def test_baseline_success_shape():
    response = client.post("/api/simulate", json={"n_trials": 5})
    assert response.status_code == 200
    data = response.json()

    assert data["meta"]["n_trials"] == 5
    assert data["meta"]["compare_strategies"] is False
    assert data["meta"]["strategies_run"] == ["adaptive"]
    assert set(data["aggregates"].keys()) == {"adaptive"}
    assert len(data["per_trial"]) == 5
    assert len(data["plot_data"]["quadrant_points"]) == 5
    assert len(data["plot_data"]["survival_histogram"]["values"]) == 5

    required_keys = {
        "seed",
        "strategy",
        "survival_rounds",
        "success_rate",
        "net_profit",
        "end_reason",
        "final_quadrant",
        "final_capability_margin",
        "final_funding_runway",
    }
    for row in data["per_trial"]:
        assert required_keys.issubset(row.keys())
        assert row["final_quadrant"] in VALID_QUADRANTS

    json.dumps(data, allow_nan=False)


def test_invalid_strategy_returns_422():
    response = client.post("/api/simulate", json={"params": {"strategy": "aggressive"}})
    assert response.status_code == 422


def test_n_trials_above_limit_returns_422():
    response = client.post("/api/simulate", json={"n_trials": 501})
    assert response.status_code == 422


def test_n_trials_zero_returns_422():
    response = client.post("/api/simulate", json={"n_trials": 0})
    assert response.status_code == 422


def test_compare_strategies_shape():
    response = client.post("/api/simulate", json={"n_trials": 3, "compare_strategies": True})
    assert response.status_code == 200
    data = response.json()

    assert data["meta"]["strategies_run"] == ["conservative", "cost_optimal", "adaptive"]
    assert set(data["aggregates"].keys()) == {"conservative", "cost_optimal", "adaptive"}
    assert len(data["per_trial"]) == 9
    assert {row["strategy"] for row in data["per_trial"]} == {
        "conservative",
        "cost_optimal",
        "adaptive",
    }


def test_difficulty_cap_must_be_ge_difficulty_0():
    response = client.post(
        "/api/simulate",
        json={"params": {"difficulty_0": 10.0, "difficulty_cap": 5.0}},
    )
    assert response.status_code == 422


def test_reproducibility_same_seed():
    payload = {
        "params": {"strategy": "adaptive", "max_rounds": 200},
        "n_trials": 5,
        "base_seed": 123,
        "compare_strategies": False,
    }
    first = client.post("/api/simulate", json=payload)
    second = client.post("/api/simulate", json=payload)
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["per_trial"] == second.json()["per_trial"]
