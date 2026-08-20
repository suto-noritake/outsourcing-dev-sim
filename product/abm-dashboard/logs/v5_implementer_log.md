# v5 Implementer Log — 実装記録

作成者: Implementer（私）  
日時: 2026-08-20

## 1. 事前確認

私は実装前に以下を読了した。

- `logs/v5_bid_manager_log.md`（AC確認）
- `logs/v5_architect_log.md`（統計仕様確定）
- `logs/v5_brand_designer_log.md`（デザイン仕様確定）
- `static/index.html`（現行実装）
- `app.py`, `tests/test_api.py`（バックエンド契約確認）

確認結果として、Architect判断どおりバックエンド変更は不要と判断し、`index.html` のみを変更対象にした。

## 2. 実装1: 影響度ランキングの統計的信頼性向上

私は Architect の確定仕様をそのまま反映した。

- 呼び出し回数 21回（`REVERSE_STAGE1_CALLS`）を維持
- 段階①の `sweepNTrials = min(80, ...)` を維持
- `dominantLeaderStats` を追加し、`seed -> hit(boolean)` マップを保持
- `wilsonScoreInterval(k, n, z=1.96)` を実装（95%CI, 0–100%クリップ）
- `mcnemarZ(hitsA, hitsB)` を実装（継続性補正あり）
  - `z = (|b-c|-1)/sqrt(b+c)`, `b+c=0` は `z=0`
- `summarizeQuadrantSweep` を拡張し、以下を返すよう変更
  - `ciLow/ciBase/ciHigh`
  - `zLowBase/zHighBase`
  - `confidenceTier`（`significant` / `uncertain` / `unclear`）
  - `confidenceLabel`, `confidenceDetail`, `confidenceBadgeClass`
- 3段階判定ロジックは Architect 擬似コードどおり
  - 非単調: `unclear`
  - 単調かつどちらか有意: `significant`
  - 単調だが両方非有意: `uncertain`
- `renderReverseStage1Table` を拡張
  - 「方向の信頼度」列を追加（テキスト入りバッジ）
  - 低/基準/高%セルへ Wilson 95%CI tooltip を追加
  - 注意書きに McNemar 判定（有意水準5%、多重比較補正なし）と「不確実=効果なしではない」を追記
- `renderReverseParamChoices` を変更
  - 表示順（変化幅順）は維持
  - 段階②候補は `confidenceTier` 優先 + 同順位で `maxAbsDeltaPt` 降順

### 実装上の判断（曖昧点の補完）

- McNemar の式は Architect 指定が絶対値ベースだったため、符号付きzではなく指定どおりの絶対値式を実装した。
- 有意性は `|z| >= 1.96` を厳守し、p値表示は追加しなかった（「過度な確信を持たせない」「説明可能でシンプル」意図を優先）。

## 3. 実装2: フルリデザイン

私は Brand Designer の確定仕様に沿って CSS と見た目のみを刷新し、DOM構造と機能配置は維持した。

- `:root` を指定トークン群へ全面置換（色・タイポ・余白・角丸・影）
- `body` 基準を 14px → 15px へ更新
- `h2` 左アクセント線を廃止
- `panel` / `strategy-card` / `reverse-calc-card` / `reverse-reco-card` の面設計を更新
- ボタンを Primary/Secondary へ再定義（主操作のみアクセント色）
- 入力とスライダーを 40px基準で統一、range track/thumb を明示スタイル化
- テーブルを 13px + tabular-nums + table-head-bg + zebra + hover へ更新
- 汎用バッジ（success/warning/neutral）を追加
- 注記レイヤーを分離（`small-note`, `reverse-disclaimer`, `error`）
- レスポンシブ指定を追加（960/768/640/480）
- Chart.js 配色を指定色へ更新
  - 四象限色: `#138A5B/#C27A12/#2B6EF2/#C5424B`
  - 戦略色: `#5B4BDB/#0F8B83/#C9651E`
  - tooltip背景・閾値線・グリッド色も仕様に合わせて調整

## 4. 変更しなかったもの

- `app.py`, `tests/test_api.py` は未変更
- `/api/simulate` のリクエスト/レスポンス契約は未変更
- 段階① API 呼び出し回数・`n_trials`上限ロジックは未変更

## 5. 自己チェック

- 実施: `node --check`（`index.html` の `<script>` 部分を一時抽出して構文検証）
- 結果: **exit code 0（JS構文エラーなし）**

## 次工程への申し送り

QA には特に以下を確認してほしい。

1. 段階①テーブルで、信頼度バッジ3種が単調/非単調・有意/非有意に応じて正しく切り替わるか  
2. `%セル tooltip` に Wilson 95%CI が表示されるか  
3. 段階②候補が「表示順（変化幅順）」ではなく「信頼度優先」で選ばれているか  
4. 既存機能（スライダー同期、感度分析、逆算①②、散布図/ヒストグラム）が新スタイル下で崩れていないか  
5. 注意書き文言が「不確実=効果なしではない」意図を維持しているか
