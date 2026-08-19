# ABM Dashboard

FastAPI + static HTML dashboard for `outsourcing_sim` Monte Carlo simulation.

## Setup (PowerShell, Windows)

From repository root:

```powershell
.\.venv\Scripts\pip install -r product\abm-dashboard\requirements.txt
Set-Location product\abm-dashboard
..\..\.venv\Scripts\python -m uvicorn app:app --reload --port 8000
```

Open: `http://127.0.0.1:8000/`

## API

- Endpoint: `POST /api/simulate`
- Main request fields:
  - `params` (SimParams fields; `seed` is not accepted)
  - `n_trials` (`1..500`)
  - `base_seed` (int)
  - `compare_strategies` (bool)
- `funding_runway` is clipped to `1e9` when it would be infinite.

### PowerShell example

```powershell
$body = @{
  params = @{
    strategy = "adaptive"
    max_rounds = 200
  }
  n_trials = 5
  base_seed = 0
  compare_strategies = $false
} | ConvertTo-Json -Depth 5

Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/simulate" -Method Post -ContentType "application/json" -Body $body
```

## Preset buttons (UI)

- **Baseline**: reset all form values to default `SimParams`.
- **Compare 3 strategies**: run `conservative`, `cost_optimal`, `adaptive` on the same input (ignores selected `strategy` field).

## Tests

From repository root:

```powershell
.\.venv\Scripts\python -m pytest product\abm-dashboard\tests\test_api.py
```

## Runtime note

This product does **not** use any LLM at runtime. It only executes deterministic/stochastic simulation code in `outsourcing_sim`.
