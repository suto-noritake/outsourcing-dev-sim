# システム設計ログ — System Architect

## 0. はじめに

私はまず `product/abm-dashboard/logs/bid_manager_log.md` を読み、Bid/Go-No-Go Manager が
まとめた受け入れ基準（Acceptance Criteria）と Go 判定の根拠を確認した。その上で、再利用対象の
既存シミュレーションエンジン一式（`outsourcing_sim/params.py`, `simulate.py`, `strategies.py`,
`model.py`）のソースを実際に読み、フィールド名・戻り値の型・挙動を裏取りした。以下はその結果に
基づく、Implementer がそのまま実装に着手できるレベルの確定設計である。

ロールの境界を守り、本ログには実装コード（ルーティングやビジネスロジック本体）は書かない。
JSON スキーマ例のみ提示する。

## 1. 既存コードの裏取り結果（設計判断の根拠）

- `SimParams`（`outsourcing_sim/params.py`）のフィールド名は Bid Manager の申し送りにあった
  `D_0`, `Funds_0`, `K` のようなエイリアスではなく、**`difficulty_0`, `funds_0`,
  `max_consecutive_failures`** が正式名である。フロントエンドの表示ラベルは分かりやすい日本語/
  英語にしてよいが、API の JSON キーは **SimParams のフィールド名をそのまま使う**方針とする
  （マッピング層を二重に持つと保守コストが増えるため、Bid Manager が示唆した「フロント名→内部名
  マッピング」は採用せず、フロントの `<label>` 表示と `name` 属性を SimParams のフィールド名に
  統一する。これにより API 契約とフォームの実装がシンプルになる）。
- `run_many(params, n_seeds, base_seed=0, keep_traces=False)` は `keep_traces=True` のとき
  `(summaries, traces)` のタプルを返す。`summaries[i]` は `summarize_trace()` の返す dict に
  `run_params.to_dict()` のうち summary に無いキーをマージしたものであり、
  `seed, strategy, survival_rounds, success_rate, final_funds, final_difficulty,
  final_quadrant, end_reason, total_cost, total_payment, net_profit` を含む。
  **`final_capability_margin` と `final_funding_runway` は summary dict に存在しない**ため、
  Bid Manager の指摘通り API 層で追加抽出が必要。
- `traces[i]` は各ラウンドの dict のリストで、各要素に `capability_margin`, `funding_runway`,
  `quadrant` を含む。よって **`traces[i][-1]`**（最終ラウンド）から
  `capability_margin` / `funding_runway` を取り出せば十分。
- `quadrant()` （`model.py`）はラベル文字列（`dominant_leader` / `cash_starved_specialist` /
  `deep_pockets_shallow_skills` / `exit_candidate`）を返す。`summarize_trace` の
  `final_quadrant` と `traces[i][-1]["quadrant"]` は同じ値になる（同じ最終ラウンドを指す）ため、
  二重計算せず `traces[i][-1]` から `quadrant, capability_margin, funding_runway` の3つを
  まとめて取得すればよい。
- `STRATEGIES`（`strategies.py`）のキーは `"conservative"`, `"cost_optimal"`, `"adaptive"` の
  3つのみ。API 側の strategy バリデーションはこの3値の Enum とする。
- `funding_runway` は `avg_burn_rate <= 1e-9` のとき `float("inf")` を返しうる。JSON は `Infinity`
  を標準では表現できないため、API 層で `inf` を検出したら大きな有限値（例: `1e9`）に丸めるか、
  文字列 `"Infinity"` にせず **数値上限にクリップする**方針とする（後述 §4）。

## 2. 決定：「presets」ではなく `compare_strategies: bool` を採用する理由

Bid Manager 案では `presets: "baseline" | "all_strategies" | null` という文字列 Enum だったが、
私はこれを **`compare_strategies: bool`** に置き換えることを決定した。理由:

1. `"baseline"` は「presets なし＝リクエストされた params をそのまま1戦略で実行する」ことと
   意味的に同一であり、実質的に二値（比較するかしないか）の情報しか持っていない。文字列 Enum に
   すると「他のプリセット名を将来追加する」余地を見せてしまうが、初版のスコープ外
   （Bid Manager ログの「明確に除外」参照）であり、YAGNI に反する。
2 `bool` の方が Pydantic バリデーションが単純（不正値が原理的に存在しない）で、フロントエンドの
   実装（チェックボックス/2つのボタン）とも自然に対応する。
3. `compare_strategies=true` のときの意味を「リクエストの `params.strategy` を無視し、3戦略
   （conservative, cost_optimal, adaptive）を同一の他パラメータ・同一 `n_trials` ・
   `base_seed` で実行し、`per_trial` に戦略ごとの結果を混在させて返す」と定義する。
   `compare_strategies=false`（デフォルト）のときは `params.strategy` で指定された単一戦略のみ
   `n_trials` 回実行する。
4. Bid Manager ログの申し送り「seed は base_seed + offset を使う」を踏襲し、
   `compare_strategies=true` の場合、戦略ごとに `base_seed` は共通のまま `run_many` を3回
   呼び出す（`run_many` 自体が `base_seed + i` で seed を割り振るため、3戦略とも同じ
   `base_seed..base_seed+n_trials-1` のシード列を使う＝**戦略間で同一乱数列による比較**が
   成立し、統計的に公平な比較ができる）。戦略間で seed をずらす必要はない
   （そもそも各戦略は独立した RNG 列で `run_game` を呼ぶため、同じ seed 値でも異なる乱数消費
   パスになりうるが、少なくとも「どの戦略も1本目は seed=base_seed から」という基準は揃う）。

## 3. ファイル/フォルダ構成（確定）

```
product/abm-dashboard/
├── app.py                     # FastAPI アプリ本体（ASGI app インスタンス名: app）
├── requirements.txt           # このサブプロジェクト固有の追加依存（下記§6参照）
├── README.md                  # 起動手順・API例・プリセット説明
├── static/
│   └── index.html             # 単一ページ・フロントエンド（vanilla JS + Chart.js CDN）
├── logs/
│   ├── bid_manager_log.md     # (既存)
│   └── architect_log.md       # (本ファイル)
└── tests/
    └── test_api.py            # FastAPI TestClient による統合テスト
```

補足:
- `app.py` はリポジトリルートから `outsourcing_sim` パッケージを import する
  （`from outsourcing_sim.params import SimParams`, `from outsourcing_sim.simulate import run_many`,
  `from outsourcing_sim.strategies import STRATEGIES`）。リポジトリルートを起点に
  `uvicorn product.abm_dashboard.app:app` として起動する想定のため、
  **`product/` と `product/abm-dashboard/` の両方に `__init__.py` を置くか、あるいは
  ハイフンを含むディレクトリ名は Python パッケージとして import できない**ため、
  実装時に以下のどちらかを選ぶ必要がある（Implementer 判断に委ねるが、README に起動コマンドを
  明記すること）:
  - (a) `uvicorn` をリポジトリルートで `python -m uvicorn` 経由ではなく、
    `product/abm-dashboard` ディレクトリに `cd` した上で `uvicorn app:app --reload` として
    起動する（ディレクトリ名にハイフンがあっても問題なし。こちらを推奨）。
  - (b) `sys.path` に `outsourcing_sim` の親ディレクトリ（repo root）を追加する数行を
    `app.py` 冒頭に書き、起動はどこからでも `uvicorn` で `--app-dir` オプションを使う。
  README には (a) の手順（`cd product/abm-dashboard; uvicorn app:app --reload --port 8000`）を
  第一候補として記載すること。
- `static/index.html` は FastAPI の `app.mount("/static", StaticFiles(directory="static"),
  name="static")` で配信し、`/` にアクセスすると `index.html` を返す（`FileResponse` または
  `RedirectResponse` で `/static/index.html` へ、もしくは `/` 用のルートを1つ用意して
  `index.html` の内容を直接返す）。

## 4. API 契約（確定版）

### 4.1 エンドポイント

`POST /api/simulate`

### 4.2 リクエスト JSON スキーマ

全フィールドはオプション（省略時は `SimParams` の dataclass デフォルト値、および
`n_trials=100`, `base_seed=0`, `compare_strategies=false`）。`params` 内のキーは
`SimParams` のフィールド名と完全一致させる。`seed` は `params` 内で受け取っても無視する
（トップレベルの `base_seed` が唯一の乱数種指定経路。`run_many` が `base_seed+i` を各試行の
`seed` として上書きするため、`params.seed` を渡しても `run_many` 内部で
`SimParams(**{**params.to_dict(), "seed": seed})` により必ず上書きされる。混乱を避けるため
API は `params.seed` が渡されても Pydantic モデルに含めず無視する＝リクエストモデルに
`seed` フィールドを含めない）。

```json
{
  "params": {
    "alpha": 0.6,
    "beta": 3.0,
    "lam": 0.7,
    "k1": 1.0,
    "cost_curve_exponent": 2.0,
    "sigma_noise": 0.3,
    "gamma": 0.15,
    "partial_pay": 0.0,
    "r_min": 0.4,
    "max_consecutive_failures": 3,
    "difficulty_0": 1.0,
    "funds_0": 100.0,
    "difficulty_cap": 20.0,
    "budget_c0": 5.0,
    "budget_c1": 15.0,
    "max_rounds": 200,
    "strategy": "adaptive"
  },
  "n_trials": 100,
  "base_seed": 0,
  "compare_strategies": false
}
```

- `params` 全体を省略した場合はキー無し（`{}`）または JSON でフィールドを全省略してもよく、
  Pydantic モデルの各フィールドにデフォルト値を `SimParams()` のデフォルトと一致させて
  設定しておく（値のズレが起きないよう、Implementer は `SimParams` のデフォルト値をコピーして
  Pydantic モデルの `Field(default=...)` に使うこと。ハードコードの重複は許容する
  ―― `SimParams` 自体を Pydantic モデルにはしない。理由は dataclass と Pydantic
  BaseModel の二重責務を避け、リクエスト用モデルはあくまで「検証済みの入力」を表し、
  それを `SimParams(**validated.params.dict())` に変換してからエンジンに渡す、という
  責務分離を明確にするため）。
- `strategy` は `Literal["conservative", "cost_optimal", "adaptive"]` とする。
- `n_trials`: `int`, 範囲 `1 <= n_trials <= 500`（§6 参照）。
- `base_seed`: `int`, 範囲チェックは特になし（0以上を推奨するが必須ではない）。
- `compare_strategies`: `bool`, デフォルト `false`。`true` のとき `params.strategy` は
  無視され、3戦略すべてで実行される旨をレスポンスの `meta.compare_strategies` で確認できる。

### 4.3 レスポンス JSON スキーマ

```json
{
  "meta": {
    "n_trials": 100,
    "elapsed_seconds": 0.842,
    "compare_strategies": false,
    "strategies_run": ["adaptive"]
  },
  "aggregates": {
    "adaptive": {
      "success_rate": 0.71,
      "bankruptcy_rate": 0.12,
      "mean_survival_rounds": 34.5,
      "mean_net_profit": 152.3
    }
  },
  "per_trial": [
    {
      "seed": 0,
      "strategy": "adaptive",
      "survival_rounds": 40,
      "success_rate": 0.75,
      "net_profit": 210.4,
      "end_reason": "contract_terminated",
      "final_quadrant": "dominant_leader",
      "final_capability_margin": 0.83,
      "final_funding_runway": 12.6
    }
  ],
  "plot_data": {
    "quadrant_points": [
      {
        "x": 0.83,
        "y": 12.6,
        "quadrant": "dominant_leader",
        "seed": 0,
        "strategy": "adaptive"
      }
    ],
    "survival_histogram": {
      "values": [40, 12, 200, 8]
    }
  }
}
```

キー設計の要点:

- `aggregates` は **戦略名をキーとする辞書**にする（Bid Manager 案ではフラットな
  `aggregates: {...}` 単体だったが、`compare_strategies=true` のとき3戦略分の集計を
  返す必要があるため、単一戦略時も含めて常に `{strategy_name: {...}}` という同一構造で
  統一する。こうすることでフロントエンド側の描画コードが単一/比較の両方で分岐不要になる）。
  - `success_rate`: 当該戦略の全試行における `success_rate` の平均（Bid Manager ログの定義通り、
    各試行の `success_rate`＝ successes/survival_rounds を平均したもの）。
  - `bankruptcy_rate`: 当該戦略の全試行のうち `end_reason == "bankrupt"` の割合。
  - `mean_survival_rounds`: `survival_rounds` の平均。
  - `mean_net_profit`: `net_profit` の平均。
- `per_trial` は **`compare_strategies` の値によらず常にフラットな配列**（単一戦略なら
  長さ `n_trials`、比較時は長さ `n_trials * 3`）。各要素の `strategy` フィールドで
  どの戦略の結果かを判別する。
- `per_trial` の各要素の生成方法（Implementer 向け具体的手順）:
  1. `summaries, traces = run_many(sim_params, n_trials, base_seed=base_seed,
     keep_traces=True)` を戦略ごとに呼ぶ。
  2. `for summary, trace in zip(summaries, traces):` で1件ずつ、`last = trace[-1]` を取り、
     `final_capability_margin = float(last["capability_margin"])`,
     `final_funding_runway = float(last["funding_runway"])` を追加した dict を組み立てる
     （`final_quadrant` は `summary["final_quadrant"]` をそのまま使ってよい。
     `last["quadrant"]` と値は同一だが、二重に読むよりは `summary` 側を正とする）。
  3. `funding_runway` が `math.isinf(...)` の場合は `1e9`（有限の大きな値）に丸めてから
     `float()` で返す（JSON の `Infinity` 非対応対策。§4.4 参照）。
- `plot_data.quadrant_points` は `per_trial` から `x=final_capability_margin`,
  `y=final_funding_runway`, `quadrant=final_quadrant`, `seed`, `strategy` を抜き出した
  もの（＝`per_trial` の射影であり、独立に計算し直さない）。
- `plot_data.survival_histogram.values` は `per_trial` 全件の `survival_rounds` を
  そのまま並べた生配列（ヒストグラムのビン分けは Chart.js 側 = フロントエンドで行う。
  バックエンドはビニングしない）。
- `meta.strategies_run` は実行した戦略名のリスト（単一時は長さ1、比較時は
  `["conservative", "cost_optimal", "adaptive"]` 固定順）。

### 4.4 数値の JSON 安全化（numpy / inf 対策）

- `run_many` / `summarize_trace` の戻り値には Python 標準の `float`/`int`/`str`/`bool` が
  使われているが（`outsourcing_sim` 内部は `np.random.Generator` の乱数のみ使用し、
  戻り値の算術は Python float 同士の演算のため通常は numpy スカラー型が混入しない）、
  念のため **API 層の最終整形時に全数値フィールドへ明示的に `float(...)` / `int(...)` を
  適用**し、`isinstance(x, (np.floating, np.integer))` が万一混入していても弾けるようにする。
- `float("inf")`（`funding_runway` が起こしうる）は JSON 標準では非対応（`json.dumps` は
  `Infinity` を出力できるが RFC 準拠パーサやフロント側 `JSON.parse` で問題を起こし得るため）、
  API 層で `min(value, 1e9)` のように上限クリップしてから返す。この定数 `1e9` は
  `app.py` 内にモジュール定数として定義し、README にも「funding_runway は 1e9 を
  無限大の代替上限として扱う」旨を記載する。
- FastAPI の `response_model`（Pydantic）を使えば、モデルのフィールド型を `float` と
  宣言するだけで numpy スカラーは自動的に Python float にキャストされて出力される
  （Pydantic v2 は `float(np.float64(...))` 相当の変換を内部で行う）。ただし `inf` は
  Pydantic でも `Infinity` のまま JSON 化されうるため、**inf クリップは Pydantic 任せに
  せず、モデルに値を詰める直前に明示コードで行う**こと。

## 5. フロントエンド方針

- `static/index.html` 1ファイルに HTML + `<style>` + `<script>` を収める（ビルドステップ
  無し、npm 不要）。
- 依存は CDN の Chart.js のみ:
  `<script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>`
- 画面構成:
  1. パラメータフォーム（`SimParams` の主要フィールドを `<input>` として配置。
     `name` 属性は SimParams のフィールド名と一致させる: `alpha, beta, gamma, k1,
     cost_curve_exponent, difficulty_0, funds_0, r_min, max_consecutive_failures,
     sigma_noise, strategy(select), n_trials`）。
  2. プリセットボタン2つ:
     - 「Baseline」: フォームを `SimParams()` のデフォルト値にリセットし
       `compare_strategies=false` で送信。
     - 「Compare 3 strategies」: 現在のフォーム値のまま `compare_strategies=true` で
       送信（`strategy` フィールドの選択は無視される旨を UI 上に注記）。
  3. 「Run Simulation」ボタン: フォーム値から §4.2 のリクエスト JSON を組み立て、
     `fetch("/api/simulate", {method: "POST", ...})` で送信。
  4. 結果表示: `aggregates` 内の各戦略について `success_rate, bankruptcy_rate,
     mean_survival_rounds, mean_net_profit` を数値表示（比較時は戦略ごとに並べる）。
  5. 散布図: `plot_data.quadrant_points` を Chart.js の `scatter` タイプで描画し、
     `quadrant` の値ごとに `datasets` を分けて色分け（4色固定パレット）。
  6. ヒストグラム: `plot_data.survival_histogram.values` をフロント側で適当なビン幅
     （例: 10刻み、または Sturges の公式）に集計してから Chart.js の `bar` で描画。
  7. HTTP エラー（422 等）はレスポンスボディの `detail` をアラート/画面上のエラー欄に表示する。

## 6. バリデーション・ガードレール

- `n_trials`: Pydantic `Field(default=100, ge=1, le=500)` — 上限は **500** を採用する
  （Bid Manager ログの受け入れ基準 3.5「n_trials<=500 で応答が概ね5秒以内」と整合させ、
  上限そのものを 500 に固定してそれ以上のリクエストを 422 で拒否する）。
- `strategy`: `Literal["conservative", "cost_optimal", "adaptive"]` を使えば、無効な文字列は
  Pydantic が自動的に 422 Unprocessable Entity を返す（`STRATEGIES` 辞書のキーと必ず
  一致させること。将来 `STRATEGIES` にキーを追加する場合はこの `Literal` も追随して
  更新する必要がある点を README に注記する）。
- 数値パラメータの範囲チェック（Implementer が Pydantic の `Field(gt=..., ge=..., le=...)`
  で実装する最低限の目安。エンジン内部で数学的に破綻しない範囲を許容する）:
  - `alpha`: `0.0 < alpha <= 2.0`
  - `beta`: `0.0 < beta <= 20.0`
  - `lam`: `0.0 <= lam <= 1.0`
  - `k1`: `k1 > 0.0`
  - `cost_curve_exponent`: `0.5 <= cost_curve_exponent <= 5.0`
  - `sigma_noise`: `0.0 <= sigma_noise <= 2.0`
  - `gamma`: `0.0 <= gamma <= 2.0`
  - `partial_pay`: `0.0 <= partial_pay <= 1.0`
  - `r_min`: `0.0 <= r_min <= 1.0`
  - `max_consecutive_failures`: `1 <= max_consecutive_failures <= 50`（`int`）
  - `difficulty_0`: `difficulty_0 > 0.0`
  - `funds_0`: `funds_0 > 0.0`
  - `difficulty_cap`: `difficulty_cap >= difficulty_0`（相互検証は Pydantic v2 の
    `model_validator` で実装）
  - `budget_c0`: `budget_c0 >= 0.0`
  - `budget_c1`: `budget_c1 >= 0.0`
  - `max_rounds`: `1 <= max_rounds <= 1000`（`int`。これがシミュレーション1試行あたりの
    最大計算量を決めるため、性能ガードレールとしても機能する）
  - `base_seed`: `int`、範囲制約なし（負値も一応許容するが、通常 UI からは 0 以上を渡す）
- 範囲外の値やリテラル不一致は Pydantic のバリデーションにより **自動的に HTTP 422** で
  返る（FastAPI 標準動作）。Implementer は明示的な `raise HTTPException` を書く必要は
  基本的に無いが、`difficulty_cap >= difficulty_0` のようなフィールド間相互検証だけは
  `model_validator(mode="after")` を明示的に書く必要がある。
- 同時実行制御は初版スコープ外（Bid Manager ログの「明確に除外」に合意）だが、
  **単一リクエストの計算量上限**として `n_trials <= 500` と `max_rounds <= 1000` の
  二重の上限を設けることで、1リクエストあたりの最大ラウンド実行回数を
  `500 * 1000 = 500,000` ラウンドに抑える。これを性能ガードレールの根拠とする。

## 7. requirements.txt の確認結果

リポジトリルートの `requirements.txt` を確認した。現状の内容は以下の通り:

```
numpy>=1.24
pandas>=2.0
matplotlib>=3.7
scipy>=1.10
SALib>=1.4
pytest>=7.4
pyarrow>=14.0
statsmodels>=0.14
lifelines>=0.27
```

`fastapi`, `uvicorn`, `pydantic`, `httpx` はいずれも**含まれていない**（`.venv` の
site-packages にも未インストールであることを確認済み）。これらはダッシュボード専用の
追加依存であり、シミュレーションエンジン本体（`outsourcing_sim/`）には無関係なので、
**リポジトリルートの `requirements.txt` は変更せず**、
`product/abm-dashboard/requirements.txt` を新規作成してそちらに以下を追記する
（Implementer が最初にやるべき作業）:

```
fastapi>=0.110
uvicorn[standard]>=0.29
pydantic>=2.6
httpx>=0.27
```

- `pydantic` は FastAPI が依存として自動導入するが、バージョンを明示して固定する。
- `httpx` は FastAPI の `TestClient`（Starlette 経由）が内部で要求するため、
  テスト実行のために明示的に requirements に含める。
- インストール手順は README に
  `pip install -r product/abm-dashboard/requirements.txt` として記載する
  （ルートの `requirements.txt` とは別ファイルなので両方入れる場合は2回 `pip install`
  するか、CI 側で連結する）。

## 8. テスト方針（QA 向け）

`product/abm-dashboard/tests/test_api.py` に FastAPI の `TestClient`
(`from fastapi.testclient import TestClient`) を使った統合テストを書く。最低限、以下の
ケースを含めること:

1. **baseline 正常系**: `POST /api/simulate` に `{"n_trials": 5}`（`params`/`base_seed`
   省略、`compare_strategies` 省略=false）を送信し、`status_code == 200`。レスポンス
   JSON が §4.3 のスキーマに一致することを検証する:
   - `meta.n_trials == 5`, `meta.compare_strategies == false`,
     `meta.strategies_run == ["adaptive"]`（`SimParams` のデフォルト `strategy` が
     `"adaptive"` であるため）。
   - `aggregates` のキーが `{"adaptive"}` のみであること。
   - `len(per_trial) == 5`。
   - `per_trial` の各要素が `seed, strategy, survival_rounds, success_rate, net_profit,
     end_reason, final_quadrant, final_capability_margin, final_funding_runway` を
     全て含み、`final_quadrant` が4値のいずれかであること。
   - `len(plot_data.quadrant_points) == 5`。
   - `len(plot_data.survival_histogram.values) == 5`。
   - レスポンス全体を `json.dumps()` に通してもエラーにならない（＝numpy 型混入や
     `Infinity` が無いことの間接検証）。
2. **不正な strategy 名**: `{"params": {"strategy": "aggressive"}}` を送信し、
   `status_code == 422` であることを確認する。
3. **不正な n_trials（上限超過）**: `{"n_trials": 501}` で `status_code == 422`。
4. **不正な n_trials（0以下）**: `{"n_trials": 0}` で `status_code == 422`。
5. **compare_strategies=true**: `{"n_trials": 3, "compare_strategies": true}` を送信し、
   - `status_code == 200`
   - `meta.strategies_run == ["conservative", "cost_optimal", "adaptive"]`
   - `aggregates` のキーが3戦略すべてを含む
   - `len(per_trial) == 3 * 3 == 9`
   - `per_trial` 内の `strategy` の値の集合が3戦略すべてを含む
6. **相互検証エラー**: `{"params": {"difficulty_0": 10.0, "difficulty_cap": 5.0}}` の
   ように `difficulty_cap < difficulty_0` となる入力を送り `status_code == 422`
   （§6 の `model_validator` が機能していることの確認）。
7. **再現性（回帰防止）**: 同一リクエスト（同一 `base_seed`, 同一 `params`,
   同一 `n_trials`）を2回送信し、`per_trial` の内容が完全に一致することを確認する
   （`run_many` は `seed = base_seed + i` で決定的に seed を割り振り、`np.random.default_rng`
   はシード固定で再現可能なため、この一致は保証されるはず。もし一致しなければ
   エンジン呼び出し方法に誤りがある可能性が高い）。

これらのテストは `pytest product/abm-dashboard/tests/test_api.py` で実行できる想定。
CI へは今回スコープ外（Bid Manager ログの除外事項）だが、ローカルでの実行手順を README に
明記すること。

## 9. 未解決事項・引き継ぎ上の注意

- Bid Manager ログにあった「presets」という語は本設計では廃止し `compare_strategies: bool`
  に一本化した。README のプリセットボタンの名称（「Baseline」「Compare 3 strategies」）は
  UI 表示上のラベルであり、API のフィールド名とは独立している点を Implementer は混同しない
  こと。
- `funding_runway` の `inf` クリップ値 `1e9` は暫定値。QA が実データで散布図の見た目を
  確認し、必要なら調整してよいが、その場合は本ログと README の記述を合わせて更新すること。
- ディレクトリ名 `abm-dashboard` にハイフンが含まれるため、Python の `import` 文で
  直接パッケージ化できない。§3 で示した通り「起動時に `cd` してから `uvicorn app:app`」を
  第一の運用方法として README に明記すること。

---

## 次工程への申し送り

Implementer は以下のチェックリストに従って実装すること。QA は同じチェックリストを
テスト観点の一次ソースとして参照すること。

### ファイル構成（作成必須）
- [ ] `product/abm-dashboard/app.py` — FastAPI アプリ（変数名 `app`）
- [ ] `product/abm-dashboard/requirements.txt` — 下記4行を記載
      ```
      fastapi>=0.110
      uvicorn[standard]>=0.29
      pydantic>=2.6
      httpx>=0.27
      ```
- [ ] `product/abm-dashboard/static/index.html` — 単一ページ、Chart.js は CDN 読み込み
- [ ] `product/abm-dashboard/tests/test_api.py` — §8 の7ケース
- [ ] `product/abm-dashboard/README.md` — 起動手順（`cd product/abm-dashboard &&
      pip install -r requirements.txt && uvicorn app:app --reload --port 8000`）、
      API 例（§4.2/4.3 の JSON をそのまま転記）、プリセットボタンの説明

### API 仕様（確定・変更不可）
- [ ] エンドポイント: `POST /api/simulate`
- [ ] リクエストボディ: `{ params?: {...SimParams フィールド...}, n_trials?: int(1-500,
      default 100), base_seed?: int(default 0), compare_strategies?: bool(default false) }`
- [ ] `params.strategy` は `Literal["conservative","cost_optimal","adaptive"]`
- [ ] `compare_strategies=true` のとき `params.strategy` を無視し3戦略すべてを実行
- [ ] レスポンス: `{ meta: {n_trials, elapsed_seconds, compare_strategies, strategies_run},
      aggregates: {戦略名: {success_rate, bankruptcy_rate, mean_survival_rounds,
      mean_net_profit}}, per_trial: [...], plot_data: {quadrant_points: [...],
      survival_histogram: {values: [...]}} }`（§4.3 の JSON 例が正）
- [ ] `per_trial` の各要素の `final_capability_margin` / `final_funding_runway` は
      `run_many(..., keep_traces=True)` の `traces[i][-1]` から抽出すること
      （`outsourcing_sim/` 側は一切変更しない）
- [ ] `funding_runway` が `inf` の場合は `1e9` にクリップしてから返す
- [ ] 全数値は `float()`/`int()` で明示キャストしてから返す（numpy 型を残さない）

### バリデーション（確定・変更不可）
- [ ] `n_trials`: `1 <= n_trials <= 500`
- [ ] `max_rounds`: `1 <= max_rounds <= 1000`
- [ ] `difficulty_cap >= difficulty_0`（`model_validator` で相互検証）
- [ ] §6 に列挙した各パラメータの数値範囲
- [ ] 不正な入力はすべて Pydantic により自動 422 を返すこと

### テスト（QA が実施・Implementer が土台を用意）
- [ ] §8 の7ケースをすべて `tests/test_api.py` に実装
- [ ] `pytest product/abm-dashboard/tests/test_api.py` がグリーンであること

以上をもって、私（Architect）の設計フェーズを完了とする。
