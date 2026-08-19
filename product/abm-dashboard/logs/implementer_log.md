# 実装ログ — Implementer

私は `bid_manager_log.md` と `architect_log.md`、および再利用対象の
`outsourcing_sim/params.py`, `simulate.py`, `strategies.py`, `model.py` を全文確認してから実装に着手した。

## 実装内容

1. `product/abm-dashboard/app.py`
   - FastAPI アプリを実装。
   - `POST /api/simulate` を Architect 指定スキーマで実装（`compare_strategies: bool` 方式）。
   - Pydantic でバリデーション（`n_trials<=500`, `max_rounds<=1000`, `difficulty_cap>=difficulty_0` 含む）。
   - `run_many(..., keep_traces=True)` の最終 trace から `final_capability_margin` / `final_funding_runway` を抽出。
   - `funding_runway` の `inf` は `1e9` にクリップ。
   - 数値は `float()` / `int()` で明示キャスト。
   - `/` は `static/index.html` を返却。
   - `abm-dashboard` がハイフン名のため、`app.py` 冒頭で repo root を `sys.path` に追加して `outsourcing_sim` を import。

2. `product/abm-dashboard/static/index.html`
   - 単一 HTML（vanilla JS + Chart.js CDN）。
   - SimParams（seed除く）+ `n_trials`, `base_seed` フォームを実装。
   - ボタン: Baseline / Run Simulation / Compare 3 strategies。
   - 集計値表示、散布図（x=capability_margin, y=funding_runway、点色=quadrant、比較時は戦略ごと系列）、生存ラウンドヒストグラムを実装。

3. `product/abm-dashboard/requirements.txt`
   - `fastapi`, `uvicorn[standard]`, `pydantic`, `httpx` を追加。

4. `product/abm-dashboard/README.md`
   - Windows/PowerShell 起動手順、API例、プリセット説明、LLM不使用注記を記載。

5. `product/abm-dashboard/tests/test_api.py`
   - Architect 指定の7ケースを実装。

## 依存インストール実施記録

repo root で以下を実行し、`.venv` へインストール済み:

```powershell
.\.venv\Scripts\pip install -r product\abm-dashboard\requirements.txt
```

## 動作確認（実サーバー）

以下を実施:

1. サーバー起動  
   `C:\Users\4096361\.copilot\repos\outsourcing-dev-sim\product\abm-dashboard` で  
   `C:\Users\4096361\.copilot\repos\outsourcing-dev-sim\.venv\Scripts\python.exe -m uvicorn app:app --port 8000`
2. 実HTTPリクエスト送信  
   `POST http://127.0.0.1:8000/api/simulate` (`n_trials=5`)
3. レスポンス受領を確認後、サーバー停止

実測レスポンス（実データ）:

```json
{
  "meta": {
    "n_trials": 5,
    "elapsed_seconds": 0.018219400008092634,
    "compare_strategies": false,
    "strategies_run": [
      "adaptive"
    ]
  },
  "aggregates": {
    "adaptive": {
      "success_rate": 0.8459236326109391,
      "bankruptcy_rate": 1.0,
      "mean_survival_rounds": 18.0,
      "mean_net_profit": -194.50945538357337
    }
  },
  "per_trial": [
    {
      "seed": 0,
      "strategy": "adaptive",
      "survival_rounds": 19,
      "success_rate": 0.8421052631578947,
      "net_profit": -120.57971485958433,
      "end_reason": "bankrupt",
      "final_quadrant": "cash_starved_specialist",
      "final_capability_margin": 2.2918451765534957,
      "final_funding_runway": -0.11738127044838331
    },
    {
      "seed": 1,
      "strategy": "adaptive",
      "survival_rounds": 18,
      "success_rate": 0.8333333333333334,
      "net_profit": -181.46215245793735,
      "end_reason": "bankrupt",
      "final_quadrant": "cash_starved_specialist",
      "final_capability_margin": 0.5684440037989198,
      "final_funding_runway": -0.4955423944529653
    },
    {
      "seed": 2,
      "strategy": "adaptive",
      "survival_rounds": 17,
      "success_rate": 0.8823529411764706,
      "net_profit": -296.38148663347056,
      "end_reason": "bankrupt",
      "final_quadrant": "cash_starved_specialist",
      "final_capability_margin": 0.5684440037989198,
      "final_funding_runway": -1.1061626637877175
    },
    {
      "seed": 3,
      "strategy": "adaptive",
      "survival_rounds": 17,
      "success_rate": 0.8823529411764706,
      "net_profit": -105.39054344702697,
      "end_reason": "bankrupt",
      "final_quadrant": "cash_starved_specialist",
      "final_capability_margin": 0.5684440037989198,
      "final_funding_runway": -0.03826541925744576
    },
    {
      "seed": 4,
      "strategy": "adaptive",
      "survival_rounds": 19,
      "success_rate": 0.7894736842105263,
      "net_profit": -268.73337951984763,
      "end_reason": "bankrupt",
      "final_quadrant": "cash_starved_specialist",
      "final_capability_margin": 0.5684440037989198,
      "final_funding_runway": -1.0522319966513214
    }
  ],
  "plot_data": {
    "quadrant_points": [
      {
        "x": 2.2918451765534957,
        "y": -0.11738127044838331,
        "quadrant": "cash_starved_specialist",
        "seed": 0,
        "strategy": "adaptive"
      },
      {
        "x": 0.5684440037989198,
        "y": -0.4955423944529653,
        "quadrant": "cash_starved_specialist",
        "seed": 1,
        "strategy": "adaptive"
      },
      {
        "x": 0.5684440037989198,
        "y": -1.1061626637877175,
        "quadrant": "cash_starved_specialist",
        "seed": 2,
        "strategy": "adaptive"
      },
      {
        "x": 0.5684440037989198,
        "y": -0.03826541925744576,
        "quadrant": "cash_starved_specialist",
        "seed": 3,
        "strategy": "adaptive"
      },
      {
        "x": 0.5684440037989198,
        "y": -1.0522319966513214,
        "quadrant": "cash_starved_specialist",
        "seed": 4,
        "strategy": "adaptive"
      }
    ],
    "survival_histogram": {
      "values": [
        19,
        18,
        17,
        17,
        19
      ]
    }
  }
}
```

## テスト結果

`.\.venv\Scripts\python -m pytest product\abm-dashboard\tests\test_api.py`  
→ **7 passed**

## 判断・補足

- Architect の仕様に対する重大な不整合は見つからなかったため、仕様変更は行っていない。
- 注意点として、`fastapi.testclient` 実行時に Starlette の `httpx2` 移行警告が出る（現時点ではテスト成功・動作影響なし）。

## 次工程への申し送り

### 私が実施済み
- API実装・バリデーション実装
- Compare 3 strategies を含むAPIテスト（7ケース）
- `.venv` への依存導入
- 実サーバー起動 → 実HTTPリクエスト → JSON応答確認 → サーバー停止

### QAで追加確認してほしい点
- ブラウザ上での UI 表示崩れ（入力フォーム、カード、グラフ）と操作性
- Compare 3 strategies 時の散布図/ヒストグラムの見やすさ（凡例・色分け）
- `funding_runway=1e9` クリップ値が可視化上妥当か（必要なら閾値調整検討）
- `n_trials=500` 近辺での応答時間（性能ガードレール確認）
