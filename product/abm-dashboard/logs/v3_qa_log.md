# v3 QA Log — QA

作成者: QA（私）
日時: 2026-08-20T09:27:21+09:00

## 1. 検証結果 (Verification Checklist)

### 1. 却下されたデザインへの回帰がないことの確認
- **検証内容**: `index.html` のソースコード内にピアソン相関係数（Pearson correlation）の計算ロジックや、散布図座標を意図的にずらすジッター（`Math.random`等を用いた処理）が含まれていないかを確認。
- **結果**: ピアソン相関係数に関する記述は一切なく、`summarizeSweep()` では単調性の方向判定と変化率のみが実装されていました。散布図の座標も `x: p.x, y: p.y` のようにAPIの実測値がそのままマッピングされており、ジッター処理がないことを確認しました。

### 2. 散布図の正確性
- **検証内容**: 
  - 色が象限のみで決まっているか（`pointBackgroundColor`）
  - マーカー形状が戦略で決まっているか（`pointStyle`）
  - Chart.jsの標準凡例が非表示になっているか
  - プラグインで x=0, y=5 の基準線が描画されているか
  - 不透明度が 0.55 に設定されているか
- **結果**: 
  - `pointBackgroundColor` は `withAlpha(quadrantColors[p.quadrant] ..., 0.55)` として実装され、象限色＋不透明度0.55になっていました。
  - `pointStyle` は `strategyPointStyle[strategy] || "circle"` として設定されています。
  - Chart.jsのオプションにて `legend: { display: false }` が設定されています。
  - `quadrantThresholdPlugin` が追加されており、`getPixelForValue(0)` および `5` を用いて破線が正しく描画されるロジックを確認しました。

### 3. 凡例の一元化
- **検証内容**: `#quadrant-legend` 以外の独立した凡例パネルが追加されていないか、形状説明が比較モード時のみ `#quadrant-legend` 内に表示されるか。
- **結果**: 形状に関する説明は `renderQuadrantLegend(compareStrategies)` の中で `shape-legend-note` クラスの div として `#quadrant-legend` 内の先頭に1行だけ追加される実装になっており、仕様通りでした。

### 4. 四象限分布％と傾向コメント
- **検証内容**: API通信を追加することなく、既存の `per_trial` 配列から分布％と傾向コメントが計算・表示されているか。
- **結果**: `quadrantDistribution()` と `tendencyCommentary()` が実装されており、これらは `showSummary()` 関数内で既存のAPIレスポンス（`response.per_trial` 等）のみを入力として計算され、DOMに追加されていました。追加のネットワークリクエストは発生していません。

### 5. 感度分析（スイープ）機能
- **検証内容**: 
  - オプトイン（専用ボタン押下）で実行されるか
  - 対象が `k1`, `sigma_noise` に限定され、それぞれ3点、最大6回の `/api/simulate` コールに収まっているか
  - `n_trials <= 150` かつ同一 `base_seed` が利用されているか
  - `sigma_noise` が 2.0 にクランプされ、基準値0の場合はスキップされるか
  - 出力表が「低/基準/高の平均純利益」「方向」「最大変化幅(%)」であり、免責テキストが表示されているか
- **結果**: 
  - `#sensitivity-run-btn` のクリックイベントでのみ `runSensitivitySweep()` が発火します。
  - `const paramsToSweep = ["k1", "sigma_noise"];` とループ処理により最大6回の呼び出し制御を確認しました。
  - `const sweepNTrials = Math.min(150, Math.max(1, basePayload.n_trials));` により上限150が守られ、`base_seed` が引数として渡されています。
  - クランプ処理（`Math.min(2.0, ...)`）および `baseValue === 0` 時の `continue` 処理を確認しました。
  - 画面UI（テーブル要素）および免責テキストの文言は Architect の指定と完全に一致していました。

### 6. バックエンドの回帰テスト
- **検証内容**: `app.py` および `tests/test_api.py` が未変更であることの確認、ならびに `pytest` の実行。
- **結果**: `git diff` および `git status` にて両ファイルが変更されていないことを確認。さらに `pytest` を実行し、7件のテストがすべてパスすることを確認しました。（結果出力は後述）

### 7. デザインリフレッシュ
- **検証内容**: Architect 指定の CSS トークン（`:root` の変数、フォントスタック、シャドウなど）が適用されているか。
- **結果**: `index.html` の `<style>` に指定された CSS トークンが過不足なく定義・適用されていることを確認しました。

### 8. ライブ稼働確認とプロセス終了
- **検証内容**: `uvicorn` をバックグラウンドで起動し、実稼働APIエンドポイントにアクセスできるか確認した後、プロセスを確実に終了させる。
- **結果**: ポート `8030` で起動し、`Invoke-RestMethod` にて `/api/simulate` へのPOSTリクエストを送信。正常なJSONレスポンス（`meta`, `aggregates`, `per_trial`, `plot_data`）が返ることを確認しました。その後、PIDを特定してプロセスを終了し、`netstat -ano | findstr :8030` の出力が空になる（リスニングポートが残っていない）ことを確認しました。

### 9. その他のバグ有無
- **検証内容**: JavaScript の構文エラー、Chart.js の設定キーミス、HTMLタグの閉じ忘れ、スイープループのオフバイワンエラーなどを調査。
- **結果**: 
  - `node --check` コマンドによりJS構文が正常であることを確認。
  - Chart.js の設定階層（`plugins.legend.display`, `scales.x.title` 等）は v4 仕様に準拠。
  - HTML の `<div>`, `<span>`, `<label>` の開始・終了タグ数は完全に一致。
  - スイープ実行時のループ処理にもオフバイワンなどのバグは見当たらず、完璧な実装でした。

---

## 2. pytest 実行ログ

```text
============================= test session starts =============================
platform win32 -- Python 3.12.3, pytest-9.1.1, pluggy-1.6.0 -- C:\Users\4096361\.copilot\repos\outsourcing-dev-sim\.venv\Scripts\python.exe
cachedir: .pytest_cache
rootdir: C:\Users\4096361\.copilot\repos\outsourcing-dev-sim
configfile: pyproject.toml
plugins: anyio-4.14.2
collecting ... collected 7 items

product/abm-dashboard/tests/test_api.py::test_baseline_success_shape PASSED [ 14%]
product/abm-dashboard/tests/test_api.py::test_invalid_strategy_returns_422 PASSED [ 28%]
product/abm-dashboard/tests/test_api.py::test_n_trials_above_limit_returns_422 PASSED [ 42%]
product/abm-dashboard/tests/test_api.py::test_n_trials_zero_returns_422 PASSED [ 57%]
product/abm-dashboard/tests/test_api.py::test_compare_strategies_shape PASSED [ 71%]
product/abm-dashboard/tests/test_api.py::test_difficulty_cap_must_be_ge_difficulty_0 PASSED [ 85%]
product/abm-dashboard/tests/test_api.py::test_reproducibility_same_seed PASSED [100%]

============================== warnings summary ===============================
.venv\Lib\site-packages\fastapi\testclient.py:1
  C:\Users\4096361\.copilot\repos\outsourcing-dev-sim\.venv\Lib\site-packages\fastapi\testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
======================== 7 passed, 1 warning in 0.43s =========================
```

---

## 3. 残留プロセスのクリア確認

APIサーバのテスト起動終了後、リスニングポートが残っていないことを最終確認。

```powershell
PS C:\Users\4096361\.copilot\repos\outsourcing-dev-sim> netstat -ano | findstr :8030
(出力なし = クリア確認済み)
```

---

## 最終判定

Pass

Implementer の実装は Architect の指示を正確に反映しており、不採用となった設計（ピアソン相関係数やジッター）の混入もありません。新たなバグも検出されなかったため、v3 の実装を合格とします。