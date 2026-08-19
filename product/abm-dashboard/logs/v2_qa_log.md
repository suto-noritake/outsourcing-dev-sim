# v2 QA 検証ログ — QA (検証担当)

作成者: QA (検証担当)
日時: 2026-08-19T19:37:37+09:00

## 1. 検証サマリー

本ログでは、Bid Manager が定義し Architect が修正・詳細化した v2 の各受け入れ基準 (AC) について、Implementer の実装が基準を満たしているか、また既存機能へのデグレが発生していないかを、実際のソースコードとテスト実行を通じて独自に検証しました。

## 2. 受け入れ基準 (AC) の個別検証結果

### 2.1 AC1: 日本語フルローカライズ（表示文言）
- **確認内容**: `static/index.html` 内の `<html lang="ja">` の設定、UI の各種テキスト（見出し、ボタン、凡例等）に英語が残っていないこと。またバックエンドとの JSON 契約 (API 送受信時の enum 値) は英語のまま維持されていること。
- **結果**: **Pass**
- **エビデンス**: 
  - 英語文言の残存なし（`Simulation`, `Dashboard`, `Parameters` 等の検索でヒット0件）。
  - `STRATEGY_LABEL_JA` および `QUADRANT_LABEL_JA` マッピングが正しく実装され、API送信時は元の英語キー (`adaptive` 等) が使われる設計であることをソースから確認。
  - README.md の冒頭に「かんたんな使い方（Windows）」として日本語手順が追記されていることを確認。

### 2.2 AC2: パラメータ説明（インラインヘルプ）
- **確認内容**: `static/index.html` の各入力項目の `title` 属性（ツールチップ）が、Architect 修正版（§2）の平易な説明文と完全に一致していること。
- **結果**: **Pass**
- **エビデンス**: `beta`（成功・失敗の白黒のつきやすさ）、`lam`（信頼度（評判）の変わりやすさ）、`k1`（コストの基準倍率）、`budget_c0`、`budget_c1` などのツールチップの内容が Architect の正しい修正テキストと一言一句一致することを目視確認。

### 2.3 AC3: 結果説明（可視化と数値）
- **確認内容**: サマリーパネルの指標値（成功割合等）の直下に1行説明が表示されていること。散布図の凡例の直下に四象限の「状態の意味＋示唆」が常設表示されていること。ツールチップが日本語化されていること。
- **結果**: **Pass**
- **エビデンス**: 
  - HTMLソース内で `.metric-help` div により `METRIC_META` から抽出した説明文がレンダリングされることを確認。
  - `renderQuadrantLegend()` により `.quadrant-legend` に四象限の説明と示唆が常設要素として差し込まれる実装を確認。
  - Chart.js のツールチップ `callbacks.label` の内容が完全に日本語化されていることを確認。

### 2.4 AC5: 図の引き伸ばし防止（Chart レイアウト）
- **確認内容**: 両チャートが `.chart-container`（高さ固定）にラップされ、`maintainAspectRatio: false` が設定されていること。不要になった `canvas` タグ自体の max-height 指定が削除されていること。
- **結果**: **Pass**
- **エビデンス**: 
  - CSS に `.chart-container { position: relative; height: 400px; width: 100%; }` および `@media (max-width: 480px)` 用の高さ指定 (280px) があることを確認。
  - JS 内の `options: { responsive: true, maintainAspectRatio: false }` を両チャートで確認。旧ルールの削除も確認済み。

### 2.5 AC4: ワンクリック起動ランチャー
- **確認内容**: `.vbs` および `.bat` のロジックの正確性。相対パス解決、ポート競合回避、ヘルスチェックループ、mshta によるエラーダイアログの挙動。実際にバックグラウンド起動できるか。
- **結果**: **Pass**
- **エビデンス**: 
  - スクリプト内の `%~dp0..\..\.venv\Scripts\python.exe` は環境非依存で正しくリポジトリの venv を指すことを確認。
  - CLI 上から `launch_dashboard.bat` を実行し、ポート 8000 で実際にプロセスが LISTEN すること、および `Invoke-WebRequest` にて `200 OK` が返ることを確認（確認後プロセス停止済み）。
  - `launch_dashboard.vbs` が `0` (非表示), `False` (非同期) オプションを用いて `.bat` を呼んでいることを確認。

### 2.6 バックエンド回帰テスト (API 契約の維持)
- **確認内容**: API の JSON フォーマットやバリデーションが破壊されていないこと。
- **結果**: **Pass**
- **エビデンス**: 
```text
============================= test session starts =============================
platform win32 -- Python 3.12.3, pytest-9.1.1, pluggy-1.6.0 -- C:\Users\4096361\.copilot\repos\outsourcing-dev-sim\.venv\Scripts\python.exe
cachedir: .pytest_cache
rootdir: C:\Users\4096361\.copilot\repos\outsourcing-dev-sim
configfile: pyproject.toml
plugins: anyio-4.14.2
collecting ... collected 7 items

product/abm-dashboard/tests/test_api.py::test_baseline_success_shape PASSED [ 14%]
...
product/abm-dashboard/tests/test_api.py::test_reproducibility_same_seed PASSED [100%]
======================== 7 passed, 1 warning in 0.45s =========================
```

## 3. 本環境で直接検証できなかった項目

本作業環境は非対話型のターミナル環境（CLI）であるため、以下のGUI操作に依存する項目については最終的な目視検証を省略し、ソースコードおよび設定上の理論的担保のみとしています。
- `launch_dashboard.vbs` をダブルクリックした際、「一瞬も黒い画面が出ないこと」および「自動的にブラウザが立ち上がること」の実機体感。
- ウィンドウをリサイズした際に Chart.js が歪まずに追従する視覚的挙動。
- エラー時に起動する `mshta` による Windows メッセージボックスの実際のダイアログ表示。

## 4. 最終判定

実装内容は Architect の指示を正確に反映しており、既存の API 実装を破壊することなく全ての要求事項を満たしています。不具合も見当たりませんでした。

**## 最終判定**
Pass
