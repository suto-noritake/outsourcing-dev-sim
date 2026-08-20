# agentic_orgs — 受託会社システム／委託元会社システム（Phase 11）

これまで本リポジトリの製品開発（`product/abm-dashboard/`）では、「委託元からの要求・
フィードバック」は人間が都度チャットで手動投入し、「受託会社のパイプライン」はオーケストレーター
（人間+AI）がBid Manager→Architect→[Brand Designer]→Implementer→QAというsub-agentロールを
手動で発注することで再現してきた。

`agentic_orgs/` は、この両方の役割を **実際に GitHub Copilot CLI (`copilot`) をサブプロセスとして
呼び出す実行可能システム** として構築したものである。

- **`contractor_company/`（受託会社システム＝システムをつくる人）**: 要求書＋対象ワークスペースを
  受け取り、`team/*.md` で定義されたメンバーを順に実行し、成果物（納品サマリー等）を作る。
- **`client_company/`（委託元会社システム＝商品を考える人）**: ABMパラメータ（`funds`, `budget_c0/c1`,
  `difficulty_0`, `k1`, `gamma`, `alpha` 等）に応じた経営層ペルソナを使い、要求書を生成する。

**重要**: 両システムは実際に`copilot`バイナリを呼び出し、実際のAIクレジットを消費する
（モックではない）。半自動方式であり、1サイクルの各ステップ（要求生成→受託実行→納品審査）は
人間が確認しながら次のコマンドを実行する設計であり、フルオートのNサイクル連続実行はスコープ外。

## ディレクトリ構成

```
agentic_orgs/
├── common/
│   ├── copilot_cli.py       # copilot CLIを独立サブプロセスとして呼び出す共通ラッパー
│   ├── team_loader.py       # team/*.mdをパースし、有効メンバー・実行順序を解決する
│   └── requirements.txt
├── client_company/
│   ├── persona_mapping.py   # ABMパラメータ→委託元ペルソナ（野心度軸・厳格度軸）変換
│   ├── run.py                # CLIエントリポイント（要求書生成）
│   ├── team/ceo.md            # 経営層ペルソナメンバー（増減自由）
│   └── templates/             # 要求書・受け入れ基準・レビューのテンプレート
├── contractor_company/
│   ├── run.py                 # CLIエントリポイント（受託パイプライン実行）
│   ├── team/                  # bid_manager / architect / implementer / qa / brand_designer(既定無効)
│   └── templates/
└── logs/
    ├── v6_*_log.md            # このメタシステム自体の開発ログ（Bid Manager〜QA）
    └── runs/{company}/{case_id}/{run_id}/  # 実行時に生成される、案件・run・メンバー単位のログ
```

## チームメンバーのMarkdown管理

各社の `team/` 配下、メンバー1人＝1つの `.md` ファイル。YAML frontmatter＋人格プロンプト本文。

```markdown
---
id: architect
name: Architect
role: architect
enabled: true
model: claude-sonnet-5
reasoning_effort: high
specialty: [技術設計, ソースコード検証, 実機での数値実験]
order: 2
depends_on: [bid_manager]
permissions:
  allow_tools: ["shell", "edit"]
  deny_tools: ["shell(git push)"]
---

# 性格・役割プロンプト
あなたは……（自然言語で人格・判断ポリシー・重視する価値観を書く）
```

- **メンバーの増減はファイル操作だけで完結する**: 追加するなら`team/`に新規`.md`を置くだけ、
  一時的に外すなら`enabled: false`にするだけ、恒久的に外すならファイルを削除するだけ。
  コード変更は不要。
- 必須フィールド: `id`（一意）, `name`, `role`, `model`, `order`。
  任意フィールドと既定値、型・エラー方針の詳細は `logs/v6_architect_log.md` の
  「B. team/*.md frontmatterスキーマ」節を参照。
- `depends_on` の循環依存、必須欠落、id重複は `team_loader.load_team()` が**致命的エラー**として
  検出し、1件でも不備があればパイプラインは1回もCLIを呼び出さずに中断する。未知フィールドは
  警告のみで継続する。

## コンテキスト分離の原則

- 各メンバーの`copilot`呼び出しは**毎回新規・独立したサブプロセス**である
  （`copilot_cli.py`は`--continue`/`--resume`/`--session-id`を一切組み立てない）。
  実行ログ内の`session_id`が呼び出しごとに異なることで実機確認済み（`logs/v6_qa_log.md`参照）。
- メンバー間の情報伝達は**ファイル成果物のみ**。次メンバーのプロンプトには、前メンバーの
  生の会話ログを埋め込まず、確定済みの成果物ファイルへの**パス参照**のみを渡す。
- ログ・成果物は `logs/runs/{company}/{case_id}/{run_id}/{member_id}.*` の形で、
  会社・案件・実行回・メンバー単位に完全分離される。

## 使い方

### セットアップ

```powershell
pip install -r agentic_orgs\common\requirements.txt
```

### 1. 委託元会社システムで要求書を生成する

```powershell
python agentic_orgs\client_company\run.py `
  --case-id my_case --task-theme "シンプルなCLI電卓を作って" `
  --funds 1500 --budget-c0 50 --budget-c1 20 --difficulty0 1.2 `
  --k1 1.0 --gamma 0.2 --alpha 0.6
```

→ `agentic_orgs/logs/runs/client_company/my_case/run_<timestamp>_<hex>/artifacts/request_brief.md`
（＋`acceptance_criteria.md`）が生成される。

### 2. 受託会社システムでパイプラインを実行する

```powershell
python agentic_orgs\contractor_company\run.py `
  --request-file "agentic_orgs\logs\runs\client_company\my_case\run_..\artifacts\request_brief.md" `
  --workspace-dir "C:\path\to\target\repo" `
  --case-id my_case
```

- `--until <member_id>` を指定すると、指定メンバー完了時点でパイプラインを止められる
  （コスト抑制・段階確認に有効。低コストな動作確認は必ずこれを使うこと）。
- `--team-dir` を差し替えれば、既定の `contractor_company/team/` 以外のチーム編成でも実行できる
  （例: デザイン系案件だけ`brand_designer.md`を`enabled: true`にした別ディレクトリを用意する等）。
- 出力: `agentic_orgs/logs/runs/contractor_company/<case_id>/<run_id>/delivery_summary.md`
  （委託元会社システムの`review_delivery.py`相当の入力に使える形式）。

### 3. 納品物を委託元会社システムでレビューする

`delivery_summary.md` を委託元側のレビュー用テンプレート（`client_company/templates/
review_feedback_template.md`）と合わせて`client_company/run.py`相当の仕組みに渡し、
承認/差し戻しの判断を生成する（半自動運用のため、この受け渡しは人間が次コマンドとして実行する）。

## 安全上の注意（必ず守ること）

1. **実クレジットを消費する**。動作確認・試験実行は必ず低コスト設定で行う：
   軽量モデル（例: `gpt-5-mini`）、低い`reasoning_effort`、`--max-ai-credits`で上限を設定し、
   `--until`でパイプラインを早期に止める。
2. `copilot`はプリインストールされた環境限定で動作する。実行前に`copilot --version`で疎通確認する
   （CLIは自動更新されるため、`--help`の内容が変わっていないか定期的に見直すこと。
   `logs/v6_architect_log.md`に確認当時のバージョン・オプション詳細を記録している）。
3. 受託会社システムが対象にする「新規リポジトリ」は、このリポジトリの外側の任意パスを想定する。
   既存プロジェクトを壊さないよう、`--workspace-dir`の指定を必ず確認する。

## 関連ログ・ドキュメント

- `logs/v6_bid_manager_log.md` / `v6_architect_log.md` / `v6_implementer_log.md` / `v6_qa_log.md`
  — このメタシステム自体を4ロールパイプラインで開発した際の各ロールの判断記録
- ルート `docs/experiments/006_phase11_agentic_orgs_meta_system.md` — 実施レポート
- ルート `docs/multi_agent_dev_playbook.md` — 「2.2 チームメンバーのMarkdown宣言的管理」パターン
