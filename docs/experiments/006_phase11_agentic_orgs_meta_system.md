# 006: Phase11 実施レポート — 委託元/受託会社システムのメタ実装（`agentic_orgs/`）

## 目的

Phase6-10では「委託元からの要求・フィードバック」を人間が都度チャットで手動投入し、
「受託会社のパイプライン」をオーケストレーター（人間+AI）が手動でsub-agent発注することで
シミュレーションのメタ実践を行ってきた。Phase11では、この両方の役割自体を**実行可能な
システム**として構築し、実際に GitHub Copilot CLI (`copilot`) をサブプロセスとして呼び出す
「受託会社システム」「委託元会社システム」を実装した。これにより、ABMの数値パラメータと
実際のAIエージェント駆動開発プロセスを接続する新しいメタ層ができた。

対象実装: [`agentic_orgs/`](../../agentic_orgs/README.md)（使い方は同README参照）。

## 経緯: ユーザー要望とフィードバックによる設計変更

初回要望:

> 「この受託会社システム（システムをつくる人）、及び委託元会社システム（商品を考える人）を
> それぞれGitHub Copilot SDKで作りたいです。」

オーケストレーターは「GitHub Copilot SDK」という語を、実在する別パッケージではなく
**GitHub Copilot CLIのプログラム的インターフェース**（`copilot -p "<prompt>"`等）と解釈し、
ask_userで4点確認（実CLI呼び出し・実クレジット消費／半自動運用／ABMパラメータ連動の
委託元ペルソナ／受託会社は特定製品非固定）した上で計画を立案した。しかし計画レビュー時、
ユーザーから重要な差し戻しフィードバックがあった:

> 「内部エージェントの設定をマークダウンで管理できるようにしましょう。メンバーを増減したり
> もできるように、メンバーごとに性格や得意分野、性能（モデル）をなどを設定できます。また、
> メンバー毎にコンテキストは明確に分離しましょう。」

これを受け、内部チームメンバーをコードではなく**Markdown宣言（YAML frontmatter＋人格
プロンプト本文）で管理する方式**に設計変更し、**コンテキスト分離**（各メンバー呼び出しは
常に独立プロセス、情報伝達はファイル成果物のみ）を明示的な設計原則として組み込んだ。

## 開発プロセス（既存4ロールパイプラインを再利用）

このメタシステム自体は、UIを持たないためBrand Designerを使わず、既存4ロールで開発した。

| 役割 | モデル | reasoning_effort | 担当 |
|---|---|---|---|
| Bid Manager | `gpt-5-mini` | low | 要件をAC群に整理（Markdownチーム管理・コンテキスト分離を含む） |
| Architect | `claude-sonnet-5` | high | **実機で`copilot --help`等を実行**しCLI実仕様を確認した上で、契約・スキーマを確定 |
| Implementer | `gpt-5.3-codex` | high | 実装＋初期`team/*.md`一式作成＋軽量試験ケースでの1サイクル動作確認 |
| QA | `gemini-3.1-pro-preview` | high | 独立検証（メンバー増減の動作確認・コンテキスト分離の実機確認を含む） |

## 各ロールの要点

### Bid Manager (`v6_bid_manager_log.md`)

既存の`docs/multi_agent_dev_playbook.md`・`outsourcing_sim/params.py`・
`product/abm-dashboard/logs/model_manifest.md`を読み込んだ上で、**条件付きGo**と判断。
AC群A（全体アーキテクチャ）〜E（受託会社システム）を整理し、Markdown frontmatterの
最小フィールド案（`id`, `name`, `enabled`, `role`, `model`, `reasoning_effort`, `specialty`,
`order`, `depends_on`, `input_artifacts`, `output_artifacts`, `timeout_sec`）を提示した。
最大の懸念として「`copilot` CLIの実機仕様が未検証」を挙げ、Architectへの最優先申し送りとした。

### Architect (`v6_architect_log.md`)

**実際にPowerShellで`copilot --version`／`copilot --help`を実行し、さらに最小コスト
（`gpt-5-mini`, `effort low`, `--max-ai-credits 30`）で3回`copilot -p`を試験実行して**、
以下を実機確認した:

- `-p/--prompt`, `--model`, `--effort`（7段階列挙）, `--allow-tool`系, `-C`/`--add-dir`,
  `--max-ai-credits`（最小30）, `--output-format json` が実在する。
- `--continue`/`--resume`/`--session-id`を指定しない限り、**毎回新規`sessionId`が自動発行**
  される（＝コンテキスト分離の一次的な実機証拠）。
- `--output-format json`時は`--silent`を付けてもイベントストリーム全体が出力される
  （`--silent`が効くのはtextモードのみ）。
- 存在しないモデル名を指定すると`Error: Model "..." is not available.`＋終了コード1で
  即エラー終了する（ハングしない）。

これらの実機証拠に基づき、`copilot_cli.py`の契約（固定引数構成、プロンプトはファイルパス
参照方式、成否判定条件、独立プロセス保証）、`team_loader.py`の設計（Kahn法による循環検出、
エラー分類）、ディレクトリ構成、そしてペルソナ変換の一次パラメータを
（`gamma`, `difficulty_0`, `budget_c0`, `budget_c1`, `partial_pay`, `r_min`,
`max_consecutive_failures`の6個、`funds_0`除外）確定した。

**重要な知見**: Bid Managerの下書き（AC-A3のログ集約先案）と、`funds_0`をペルソナ根拠に
含めるかどうかの曖昧さを、Architectがソースコード検証で修正した。これは過去のv2〜v5でも
繰り返し観測された「低ティアロールの下書きを高ティアロールが実資産で検証・訂正する」
パターンの、Phase11版の具体例である。

### Implementer (`v6_implementer_log.md`)

Architect仕様通りに`common/copilot_cli.py`・`common/team_loader.py`・
`client_company/persona_mapping.py`・両社の`run.py`・初期`team/*.md`一式
（`bid_manager.md`, `architect.md`, `implementer.md`, `qa.md`, `brand_designer.md`
[既定`enabled: false`], `ceo.md`）を実装した。実装前の安全確認として`copilot --help`を
再実行し、Architectログとの差分（`gpt-5-mini`は`effort=minimal`非対応、`effort=low`に
統一）を発見・反映した。

実クレジットを消費する最小限の1サイクル動作確認（`gpt-5-mini`, `effort low`,
`--max-ai-credits 30`、「シンプルなCLI電卓を作って」というテーマ、contractor側は
`--until bid_manager`でコスト抑制）を実施し、client_company・contractor_company双方が
成功、成果物ファイル・ログが期待通り生成されることを確認した。

### QA (`v6_qa_log.md`)

**総合判定: Pass**。コードレビューでArchitect仕様との整合（固定引数構成、
`--continue`/`--resume`/`--session-id`不使用、ペルソナ変換ロジックからの`funds_0`除外）を
確認した上で、一時テストスクリプトを実際に書いて実行し:

- 新規メンバー追加のみでチーム構成が変わること
- `enabled: false`のメンバーが除外されること
- 循環依存（A depends_on B, B depends_on A）が致命的エラーとして検出されること
- 必須フィールド欠落・id重複がエラーになること

をすべて実機動作で検証した。さらに実装済みの実行ログ（`meta.json`）を照合し、
**呼び出しごとに異なる`session_id`が実際に発行されていること**を独立に確認、
意図的な短時間タイムアウト（5秒）を発生させてタイムアウト処理が正しく機能することも
確認した。不具合は発見されず、修正なしでPassとした。

## オーケストレーターによる独立再検証

サブエージェントの自己申告を鵜呑みにせず、以下を独自に再確認した:

- `git status --porcelain`で新規追加ファイル一式（`agentic_orgs/`全体）を確認。
- `python -m py_compile`で全実装ファイルの構文エラーがないことを確認。
- `copilot --version`を再実行しCLI疎通（バージョン1.0.80）を確認。
- スモーク実行の`meta.json`を直接開き、`session_id`がclient側・contractor側で異なる値
  （それぞれ独立UUID）であること、`--continue`/`--resume`/`--session-id`に類する引数が
  コマンドライン配列に一切含まれていないことを確認。
- 生成された成果物一式（`request_brief.md`, `acceptance_criteria.md`, `bid_manager_log.md`,
  `delivery_summary.md`）が実在し、内容が空でないことを確認。
- 残存プロセス確認: `subprocess.run()`（同期実行）で呼び出しているため、スモーク実行済みの
  `copilot`プロセスがハング・残存していないことを確認。

## 考察・今後のプロジェクト全体への示唆

1. **「役割ごとの技術リテラシー（モデルティア）が成果物品質を左右する」という仮説
   （Phase4起源、v2〜v5で繰り返し裏付け）は、メタシステム自体の開発でも再現された。**
   Bid Managerの下書きの曖昧さ・軽微な誤りを、Architectが実機検証（ソースコード＋実際に
   CLIを動かす数値実験）で修正する構造は一貫している。
2. **「不確実な外部仕様は、推測で固定せず実機で確認してから設計する」という原則
   （v4以降のArchitectの一貫した姿勢）が、今回は「実行環境自体（`copilot` CLI）の仕様確認」
   にまで拡張された。** 計画段階ではplan-modeのサンドボックスにより`copilot --version`
   すら確認できなかったが、実装フェーズでArchitectが最初に行うべきタスクとして明確に
   位置付けたことで、仮定に基づく設計の手戻りを防げた。
3. **Markdown宣言的チーム管理は、このプロジェクトが以前から使ってきたSQL
   `todos`/`todo_deps`による進行管理パターンと同型である。** 実行順序・依存関係を
   宣言的データとして表現し、コードから分離するという設計原則は、開発プロセスの管理
   （SQL）と、開発プロセスを実行するエージェント組織そのものの管理（Markdown）の
   両方に一貫して適用できることが分かった。
4. **コンテキスト分離の原則は、単なる設計思想ではなく実機で検証可能な性質として
   実装できた。** `session_id`の非再利用を実行ログから直接確認できたことで、
   「メンバー間で会話履歴が漏れ込んでいないか」という抽象的な懸念に対して、
   具体的な検証手段（ログ照合）を持てるようになった。今後、実際の商用案件で
   このシステムを稼働させる際も、同じ検証手順を再利用できる。
5. **半自動運用（各ステップを人間が確認しながら進める）の選択は、実クレジット消費を
   伴うシステムでは妥当なリスク管理だった。** 今回の動作確認も、`--until`オプションで
   意図的に早期停止させることで、コストを最小化しながら段階的に信頼性を積み上げる
   運用ができた。

## 成果物一覧

- `agentic_orgs/common/{copilot_cli.py, team_loader.py, requirements.txt}`
- `agentic_orgs/client_company/{persona_mapping.py, run.py, team/ceo.md, templates/*.md}`
- `agentic_orgs/contractor_company/{run.py, team/*.md, templates/*.md}`
- `agentic_orgs/README.md` — 使い方・設計原則のドキュメント
- `agentic_orgs/logs/v6_{bid_manager,architect,implementer,qa}_log.md` — 各ロールの生ログ
- `agentic_orgs/logs/runs/{client_company,contractor_company}/smoke_cli_calc/...` —
  最小コストで実施した実クレジット消費を伴う1サイクル動作確認の実行記録
- 本レポート、および`docs/multi_agent_dev_playbook.md`「2.2 チームメンバーのMarkdown
  宣言的管理」節（一般化された再利用可能パターンとして追記）
