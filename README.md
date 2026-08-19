# outsourcing-dev-sim

AIエージェントを用いた「技術受託開発」のシミュレーション。

**委託元（発注側、資金潤沢・高難度要求）** と **受託会社（開発側、技術力はあるが資金制約あり）**
の関係を、AIエージェントによる開発を前提にモデル化し、多数回シミュレーションすることで
今後の技術受託開発のあり方を分析することを目的とする。

- **技術力** = モデル性能（能力レベル）× 投入エージェント数
- **資金** = AIクレジット残高（消費速度・調達額）

## 進め方（3段階）

1. **抽象エージェントベースモデル（ABM）**で大量試行し、統計的に有意な傾向を探索する
2. **厳密な実験設計**（パラメータ空間、反復回数、感度分析、検証方法）を並行して整備する
3. 抽象モデルで見つかった「気になる設定」について、**実際のLLMマルチエージェント実験**
   （実際に交渉・実装作業を行わせる）で検証・キャリブレーションする

## ドキュメント

- [`docs/DESIGN.md`](docs/DESIGN.md) — Phase 1: 概念・数理モデルの設計（状態変数、技術力/成功確率/コスト関数、
  技術優位度×資金体力の2軸4象限フレームワーク）
- [`docs/experiment_design.md`](docs/experiment_design.md) — Phase 3: 実験設計マトリクス（仮説、13パラメータの水準表、
  パイロット→スクリーニング→集中実験→統計解析の4段階プロセス）
- [`docs/llm_experiments.md`](docs/llm_experiments.md) — Phase 4: LLMマルチエージェント実験
  （委託元・受託会社それぞれの社内複数ロール構造）
- `docs/experiments/` — 実行した実験のrun manifest・結果記録（再現性用、001〜004）
- [`docs/report.md`](docs/report.md) — **Phase 5: 最終レポート**（Phase2-4の統合結果・考察・限界）

## Phase 6: 製品化 — ABMインタラクティブダッシュボード

[`product/abm-dashboard/`](product/abm-dashboard/) — シミュレーションの主要パラメータをブラウザで
調整し、その場でモンテカルロ試行を実行して成功率・破産率・4象限分布などを可視化できる
Webダッシュボード（**製品自体はLLMを使わない**、`outsourcing_sim`をそのまま計算エンジンとして
再利用）。起動手順は [`product/abm-dashboard/README.md`](product/abm-dashboard/README.md) を参照。

この製品自体は、Phase4で設計した「社内複数ロール構造」を実際の開発プロセスに適用し、
Bid Manager / Architect / Implementer / QA の4役割を実モデル・実推論強度を割り当てた
sub-agentとして実行して開発した。各役割の思考ログと使用モデル一覧は
[`product/abm-dashboard/logs/`](product/abm-dashboard/logs/) に記録している
（`model_manifest.md`に役割別モデル割当の一覧）。

**v2アップデート（実クライアントフィードバック対応）**: 出荷後に実際のクライアント（経営層）から
「英語ばかりで分かりにくい」「パラメータ・結果の意味が不明」「サーバー起動が面倒」「図が歪む」
という指摘を受け、同じ4ロールパイプラインでUI全面日本語化・パラメータ/結果の解説追加・
Windowsダブルクリック起動ランチャー・チャートレイアウト修正を実施（`v2_*_log.md`）。この過程で
低ティアモデル（Bid Manager）が作成したパラメータ説明文に事実誤認が複数含まれ、高ティアモデル
（Architect）がソースコードとの突き合わせで修正するという、Phase4の「役割ごとの技術リテラシーが
成果物品質を左右する」という仮説を実開発プロセスで裏付ける出来事があった（詳細は
`model_manifest.md`）。

## リポジトリ構成

```
outsourcing_sim/           # 抽象ABMのPythonパッケージ
scripts/                    # モンテカルロ実行・スクリーニング・分析用スクリプト
tests/                      # ユニットテスト
docs/                       # 設計ドキュメント・実験記録
product/abm-dashboard/      # Phase6: ABMインタラクティブダッシュボード（製品）
```

## セットアップ

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## 実行例

```powershell
# パイロット試行（baseline設定でn回試行し分散を推定）
python scripts\run_pilot.py --n 200

# モンテカルロ + パラメータスイープ
python scripts\run_monte_carlo.py --config configs\baseline.yaml --n-seeds 500

# 結果の分析・可視化（技術優位度×資金体力の象限プロット含む）
python scripts\analyze_results.py --input results\latest.parquet
```
