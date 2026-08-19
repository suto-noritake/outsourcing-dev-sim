# ABM Dashboard

FastAPI + static HTML dashboard for `outsourcing_sim` Monte Carlo simulation.

## かんたんな使い方（Windows）

### 1) 起動（ダブルクリック）

- `product\abm-dashboard\launch_dashboard.vbs` をダブルクリックしてください。
- 数秒待つと、既定ブラウザで `http://127.0.0.1:8000/` が自動で開きます。
- コンソール画面は表示されません（内部で `launch_dashboard.bat` が非表示実行されます）。

### 2) もし起動できない場合

- `.venv` はリポジトリ直下（`..\..\.venv`）にある前提です。
- `.venv` が別の場所にある場合は、`launch_dashboard.bat` 内の `VENV_PY` を実環境の
  `python.exe` パスに合わせて編集してください。
- ポート 8000 が使用中でも、既に起動済みと判断できる場合はブラウザ表示のみ実行します。

### 3) 画面の使い方

- 左上の「初期値に戻す」で標準パラメータに戻せます。
- 「シミュレーション実行」で選択中の戦略のみ実行します。
- 「3戦略を比較」で保守的・コスト最適・適応型を同条件で同時比較します。

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
