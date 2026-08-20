# v4 QA Log — QA

作成者: QA（私）
日時: 2026-08-20T10:50:00+09:00

## 1. 概要
v4（リアルタイムスライダー化＋独走勝ち組型への逆算機能）の実装について、Architectの確定仕様（`v4_architect_log.md`）の§9「実装チェックリスト」に対応する10項目の検証を実施しました。

Implementerの自己申告に依存せず、実コード（`index.html`）の目視確認、差分確認、ユニットテストの実行、実サーバでの動作確認、JS構文チェックを実行しました。

## 2. 検証項目と結果

### 1. スライダー範囲の確認
**[Pass]**
- `k1`: `min: 0.01, max: 10.0, step: 0.01` (行382)
- `funds_0`: `min: 1.0, max: 2000.0, step: 1.0` (行390)
- `budget_c1`: `min: 0.0, max: 150.0, step: 0.5` (行393)
- `difficulty_0`の実効上限: `syncDifficultyCapConstraint`（行605-618）および `clampParamValue` 内で `difficulty_cap` の値に動的に連動していることを確認。

### 2. リアルタイムプレビューの実装確認
**[Pass]**
- デバウンス: `const PREVIEW_DEBOUNCE_MS = 250;` (行462)、`setTimeout` にて適用。
- 中断制御: `previewController = new AbortController();` と `previewController.abort();` を使用して前リクエストをキャンセル。
- 世代トークン: `previewToken` を用いて、古いレスポンス（`token !== previewToken`）を破棄していることを確認。
- オプション: `compare_strategies: false` (行1072)。
- 試行回数: `Math.min(PREVIEW_N_TRIALS, payload.n_trials)` (行1073、プレビュー用のn=20上限) となっている。

### 3. 逆算機能の呼び出し回数の確認
**[Pass]**
- 段階①（単体スイープ）: 7パラメータ × 3点 = 21回。`REVERSE_STAGE1_CALLS = 21` でパラメータ数が7個に固定されていることを確認。
- 段階②（グリッドサーチ）: `REVERSE_STAGE2_PREVIEW_CALLS = 9`, `REVERSE_STAGE2_PRECISE_CALLS = 3` で合計12回。
- 全体の呼び出し回数: 21 + 12 = 33回となっており、設計の上限を守っている。
- 無効化制御: 段階②のボタン (`reverseStage2RunBtn`) は、段階①完了（`reverseStage1Done == true`）かつパラメータ2個選択時のみ有効化される制御（行1209）がある。

### 4. 目的関数の確認
**[Pass]**
- 逆算機能での評価関数が `summarizeQuadrantSweep()`（pt差分）であることを確認。
- `mean_net_profit` ではなく `dominant_leader_pct` を主指標として評価している（行1373-1380）。

### 5. 却下された設計が入っていないことの確認
**[Pass]**
- モーダルダイアログ (`window.alert`, `window.confirm`) は新設されておらず、インラインテキストで見積もり等を表示している。
- 段階②のプレビュー9通りの結果は内部処理（`previewCandidates`）のみに留め、画面に表示する `renderReverseCandidates()` には精密検証を通過した上位3件の `finalCandidates` だけを渡している。

### 6. 既存v3要素の無改修確認
**[Pass]**
- `drawScatter`関数、四象限凡例の説明、`summarizeSweep()`（相対%変化方式、最大6回の感度チェック）など、既存要素のロジックが変更されていないことを確認。

### 7. バックエンド無改修確認
**[Pass]**
- コマンド: `git diff --stat -- product/abm-dashboard/app.py product/abm-dashboard/tests/test_api.py`
- 結果: 差分なし（`index.html` のみ変更されている）。

### 8. 回帰テスト
**[Pass]**
- コマンド: `python -m pytest product\abm-dashboard\tests\test_api.py -v`
- 結果: `7 passed in 0.53s` で全て成功。

### 9. 実サーバーでの動作確認
**[Pass]**
- 実行内容: ポート8040が空いていることを `netstat` で確認後、`python -m uvicorn app:app --port 8040` で起動。
- 確認結果: `curl -i http://localhost:8040/` および `/api/simulate` の POST リクエストを実行し、正常応答 (HTTP 200) を確認。
- 後処理: プロセスを停止し、`netstat -ano | findstr 8040` で `LISTENING` 状態のプロセスが残っていないことを確認済み。

### 10. JS構文チェック
**[Pass]**
- `index.html` 内の `<script>` 要素を抽出し `node --check` を実行。構文エラーなし (exit code 0)。

## 3. 総合判定
**総合判定: Pass**

すべての検証項目において、Architectが定めた確定仕様（v4_architect_log.md）に準拠して実装されており、意図しない呼び出しの急増や不適切なUI（モーダルや過剰な上限値）が排除されていることを確認しました。既存機能も破壊されていません。このまま次のステップへ進めて問題ありません。
