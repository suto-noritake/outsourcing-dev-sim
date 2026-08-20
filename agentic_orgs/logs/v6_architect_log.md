# v6 Architect Log

私はArchitectとして、まずBid Managerのログ（`agentic_orgs/logs/v6_bid_manager_log.md`）を読んだ。Bid Managerの整理は骨格として妥当だが、本人も明記している通り「`copilot` CLIの実機仕様を未確認のまま」複数のACを書いており、特にAC群C（コンテキスト分離）とAC群B（frontmatter運用）は実機仕様次第で成立しない可能性があった。したがって私は**推測での確定を一切行わず**、`copilot --help`系を実際に実行し、さらに3回の最小コスト実プロンプト実行で非対話実行の挙動そのものを検証した上で、以下の確定仕様を作成した。

## 1. `copilot` CLI 実機確認結果

### 1.1 実行環境
- `Get-Command copilot` で実体を確認: `C:\Users\4096361\AppData\Local\Microsoft\WinGet\Packages\GitHub.Copilot_Microsoft.Winget.Source_8wekyb3d8bbwe\copilot.exe`
- `copilot --version` → `GitHub Copilot CLI 1.0.80`（`Get-Command`のFileVersionInfoでは1.0.77だったが、起動時オートアップデートにより1.0.80になっていた。**バージョンが実行の都度変わりうる**ことに注意）。
- 認証済み状態で動作した（`login`を要求されなかった）。この検証環境固有の前提であり、Implementerが別環境で動かす場合は認証状態を別途確認する必要がある。

### 1.2 `copilot --help` の要点（Bid Managerが挙げた確認項目への回答）

| 確認項目 | 実機仕様 |
|---|---|
| 非対話実行フラグ | `-p, --prompt <text>` が正。Bid Managerの想定通り存在した。`-i, --interactive <prompt>` は対話モードを起動してからプロンプトを自動投入するもので**非対話用ではない**（混同注意）。 |
| モデル指定 | `--model <model>` が正。`COPILOT_MODEL`環境変数でも設定可（`--model`が優先）。`copilot help config`の`model`項目に選択肢一覧があり、実在確認した: `claude-sonnet-5`, `claude-opus-5`, `claude-sonnet-4.6`, `claude-sonnet-4.5`, `claude-haiku-4.5`, `gpt-5.6-terra`, `gpt-5.6-luna`, `gpt-5.4`, `gpt-5.4-mini`, `gpt-5.3-codex`, `gpt-5-mini`, `gemini-3.1-pro-preview` 他多数。既存`model_manifest.md`が使う4モデル（`gpt-5-mini`/`claude-sonnet-5`/`gpt-5.3-codex`/`gemini-3.1-pro-preview`）は**全て現行カタログに実在**することを確認した。 |
| reasoning_effort相当 | `--effort, --reasoning-effort <level>`。選択肢は `none, minimal, low, medium, high, xhigh, max` の7段階（Bid Manager/既存マニフェストの `low`/`high` はこの部分集合であり両立する）。 |
| ツール権限制御 | `--allow-tool[=tools...]` / `--deny-tool[=tools...]` / `--allow-all-tools`。パターン構文は `kind(argument)` 形式で、`shell(git:*)`（プレフィックス一致は`:*`）、`write(path?)`、`<mcp-server>(tool?)`、`url(domain?)` の4種。**denyがallowより常に優先**。`--allow-all-tools`は「非対話モードでは実質必須」とヘルプ本文に明記されていた（`(env: COPILOT_ALLOW_ALL); required for non-interactive mode` の記載）。 |
| 作業ディレクトリ/対象ディレクトリ | `-C <directory>`（何よりも先にcwdを変更）と `--add-dir <directory>`（追加で読み書き許可するディレクトリ、複数指定可）の2種。デフォルトのファイルアクセス許可範囲は「cwdとそのサブディレクトリ＋システム一時ディレクトリ」（`copilot help permissions`より）。 |
| AIクレジットセッション上限 | `--max-ai-credits <credits>` が存在。**最小値30**（`copilot help limits`より）。ソフトキャップであり、1回のモデル応答がキャップを超過してから次呼び出しがブロックされる仕様（超過検知は事後）。 |
| 出力形式 | `--output-format <text\|json>`。`json`指定時はJSONL（1行1JSONオブジェクト）でイベントストリーム全体が出力される。`-s, --silent`は「統計情報を省き応答のみ出す」だが、**JSON出力時はsilentを付けてもイベント全体が出力される**ことを実機で確認した（text出力時のみsilentが効き、応答テキストのみになる）。 |
| 非対話実行の終了コード | 正常終了は`0`。実機で存在しないモデル名を指定したところ`Error: Model "..." from --model flag is not available.`と表示され**終了コード`1`**を確認した。JSON出力モードでは最終行の`{"type":"result", ..., "exitCode":0, ...}`イベントにも同じ終了コードが載る。 |

### 1.3 実機での最小コスト検証（3回、いずれも安価なモデル・低reasoning_effortで実施）

検証は `agentic_orgs\_verify_scratch`（作業後に削除済み）で実施した。実クレジットを消費する行為であるため、**最小限**に留めた。

1. **非対話実行の基本動作確認**
   ```
   copilot -p "Reply with exactly one word: PONG. Do not use any tools." `
     --allow-all-tools --silent --model gpt-5-mini --effort low `
     --max-ai-credits 30 --output-format json --no-color
   ```
   → 正常応答（`assistant.message`イベントの`content`が`"PONG"`）。**重要な発見**: 最終行 `{"type":"result","sessionId":"3871e0e1-...","exitCode":0,"usage":{...}}` に**新規生成されたsessionId**が載っていた。私は`--continue`/`--resume`/`--session-id`のいずれも指定していないので、**CLIは何も指定しなければ常に新規セッションを生成する**ことを実機で確認した。これはAC群C（コンテキスト分離）の根拠として使える一次証拠である。
2. **`--output-format`未指定＋`--silent`のテキストモード確認**
   → 標準出力は`"PONG2\n\n"`のみ。JSONモードと違い、テキストモードの`--silent`は本当に応答本文のみを返す。ログ取得方式の選択に直結する重要な差異。
3. **異常系（存在しないモデル名）の確認**
   → `Error: Model "this-model-does-not-exist-xyz" from --model flag is not available.` を標準出力（またはstderr、`2>&1`で合流させたため区別せず取得）に出力し、**終了コード1**で終了。ハングせず即座にエラー終了することを確認した（非対話モードでの安全性が担保されている）。

以上により、Bid Managerが「最大の不確実性」とした①非対話実行可否、②モデル/reasoning_effort指定、③セッション分離の可否、④終了コード規約は、**いずれも実機で確認済み**とし、以降の設計はこの確認結果の上に構築する。

### 1.4 実機確認できなかった／未確定のまま残す事項（正直に明記する）

- **ファイル読み取り系ツールが`--allow-all-tools`なしでも確認なしに使えるか**は`--help`だけでは確定できなかった。ヘルプ本文には「非対話モードでは`--allow-all-tools`が実質必須」とあるのみで、読み取り専用ツールの例外があるかは記載がない。ここを詰めるための追加の実プロンプト実行は、クレジット消費とハングのリスク（確認プロンプトが出ても非対話モードには応答者がいない）を考慮し、**今回は行わなかった**。Implementerが実装着手前に、`--allow-all-tools`を外した状態で読み取り専用の最小プロンプト（例:「このディレクトリのファイル一覧を教えて」）を1回だけ試し、ハングしないか・確認なしで完了するかを確認すること。ハングする場合は`timeout`付きで安全に検証すること。
- **`--agent <agent>`オプションの実体（カスタムエージェント定義ファイルの置き場所・書式）**は`--help`のトップレベル一覧に存在が示されるのみで、深掘りしていない。今回のMarkdownチーム管理は`--agent`機構に依存せず、素の`-p`プロンプト（人格プロンプト本文＋タスク指示を連結したもの）で構成する設計とし、`--agent`機構は使わない前提で進める。将来的な代替案として記録するに留める。
- **ツール名の完全なカタログ**（`shell`/`write`/`url`/MCPサーバ名以外に何があるか）は確認していない。権限設計は「安全側に倒す」方針（後述）でカバーする。
- 実行したのは1.0.80時点の挙動であり、CLIは自動更新される。Implementer着手時に**同じ確認コマンドを再実行し差分がないか一度だけ確認する**こと。

## 2. Bid Manager AC群のレビュー（実現可能性判定）

| AC群 | 判定 | コメント |
|---|---|---|
| A（全体アーキテクチャ） | **概ね採用、A3は修正** | AC-A3「実行ログをagentic_orgs/logs/配下に集約」は、既にこのディレクトリに本v6開発工程自身のログ（`v6_bid_manager_log.md`等）が存在するため、**稼働時ランタイムログと衝突しない名前空間分離が必要**と判断した。詳細は3節。 |
| B（Markdownチーム管理） | **採用（スキーマを厳密化）** | frontmatter項目案は妥当。ただし「未知フィールドの扱い」「循環検出」「validation失敗時の粒度（フェイルファストか警告か）」が未定義だったため、4節で確定する。 |
| C（コンテキスト分離） | **採用（実機根拠あり）** | 1.3節の実機確認により、「`--continue`/`--resume`/`--session-id`を一切使わず毎回`subprocess.run()`する」という実装方針だけで、AC-C1〜C4は機械的に満たせることを確認した。C6の「ファイルI/O境界の明示」は、プロンプトに成果物ファイルの**内容を直接埋め込まず、ファイルパスのみを渡し、CLI自身の読み取りツールに読ませる**方式で明確化する（5節・7節）。 |
| D（委託元会社システム） | **採用（一次パラメータを絞り込み）** | Bid Manager案の`funds_0`は`params.py`のコメント上も明確に「B（受託会社）側資源」であり、A社ペルソナの一次根拠から**除外**する。理由は6節。 |
| E（受託会社システム） | **採用** | 汎用性要件（AC-E4）を満たすため、パイプライン成果物の格納場所を「対象ワークスペース内」ではなく「本メタシステム自身のリポジトリ内」に固定する設計とした（3節・7節で詳細）。 |

## 3. `agentic_orgs/` ディレクトリ構成（確定）

```
agentic_orgs/
├── common/
│   ├── copilot_cli.py        # copilot CLI起動の共通ラッパー（両社共有）
│   ├── team_loader.py        # team/*.md のロード・検証・DAG解決（両社共有）
│   └── requirements.txt      # このサブシステム専用の追加依存（PyYAML等）
├── client_company/
│   ├── team/                 # 経営層ペルソナ定義（*.md）
│   │   ├── requester.md      # 要求書作成担当ペルソナ
│   │   └── reviewer.md       # 納品審査担当ペルソナ
│   ├── templates/
│   │   ├── request_brief_template.md
│   │   ├── acceptance_criteria_template.md
│   │   └── review_feedback_template.md
│   ├── persona_mapping.py    # ABMパラメータ→ペルソナ変換ロジック（6節の一次パラメータを実装）
│   └── run.py                # エントリポイント（要求書生成 / 納品審査の1サイクル実行）
├── contractor_company/
│   ├── team/
│   │   ├── bid_manager.md
│   │   ├── architect.md
│   │   ├── implementer.md
│   │   ├── qa.md
│   │   └── brand_designer.md # 任意ロール。既定 enabled: false
│   ├── templates/             # 各メンバー成果物のテンプレ（AC群の型を強制するための雛形）
│   └── run.py                 # エントリポイント（半自動パイプライン。--until <member_id> で途中停止可）
└── logs/
    ├── v6_bid_manager_log.md  # 本v6メタ開発工程自体のログ（既存、そのまま維持）
    ├── v6_architect_log.md    # 本ログ
    ├── (今後) v6_implementer_log.md, v6_qa_log.md
    └── runs/                  # 【新設】実運用時（client/contractor companyを実際に動かした時）のログ置き場
        └── {company}/{case_id}/{run_id}/
            ├── manifest.json          # run全体のメタ情報（開始/終了時刻・メンバー一覧・各々の成否）
            ├── {member_id}.stdout.log # 生のCLI標準出力（JSONLそのまま。パース前の一次情報源）
            ├── {member_id}.stderr.log
            ├── {member_id}.meta.json  # exit_code, session_id, duration_sec, model, effort等
            └── artifacts/             # 各メンバーのoutput_artifacts実体
                ├── bid_manager_log.md
                ├── architect_log.md
                ├── request_brief.md
                └── ...
```

**AC-A3からの意図的な変更点（理由付き）**: Bid Manager案は「稼働ログをagentic_orgs/logs/直下に集約」だったが、直下は既に本メタ開発工程自身のログ（`v6_*_log.md`）が置かれている。両者を同じ階層に混在させると「メタシステムを作る過程のログ」と「メタシステムが実際に受託案件を処理した結果のログ」が区別できなくなる。私は`logs/runs/`というサブ名前空間を新設し、稼働時ログをここに限定することで、AC-A3の「agentic_orgs/logs/配下に集約」という制約自体は保ったまま、衝突を回避した。

**成果物の置き場所についての判断（AC-A6/AC-E4関連）**: 受託会社システムは「任意の対象ワークスペース」を扱える汎用設計が要件である。対象ワークスペースは本リポジトリの外にある全く別のプロジェクトである可能性がある。そのため、パイプラインの成果物（各ロールのログ・要求書・設計書・QA判定）は**対象ワークスペースの中には書き込まず**、常に本メタシステム自身のリポジトリ（`agentic_orgs/logs/runs/...`）に格納する。対象ワークスペースに書き込むのはImplementerが指示された実装作業（コード変更そのもの）だけに限定する。これは既存の`product/abm-dashboard/logs/`方式（対象プロダクト自身のディレクトリにログを置く）とは異なる判断だが、「対象ワークスペースを汚さない」「他人の入れ物かもしれない任意リポジトリに無断で新規ディレクトリを作らない」という安全側の判断であり、AC-E4の一般化要件を満たすために必要な変更である。

`run_id`の命名規則: `run_{YYYYMMDD}-{HHMMSS}_{6桁hex}`（例: `run_20260820-184203_a1c92f`）。`case_id`は呼び出し側が指定する案件識別子（省略時`default`）。

## 4. `team/*.md` frontmatterスキーマ（確定）

### 4.1 必須フィールド

| フィールド | 型 | 説明 |
|---|---|---|
| `id` | string | メンバー識別子。正規表現 `^[a-z][a-z0-9_-]*$` に一致する必要がある。**team内で一意**。 |
| `name` | string | 表示名（人間可読）。 |
| `role` | string | 役割名。自由文字列だが、既存プレイブックとの整合のため `bid-manager` / `architect` / `implementer` / `qa` / `brand-designer` / `requester` / `reviewer` を推奨語彙として`team_loader.py`のドキュメントに明記する（列挙型として強制はしない＝AC-E2「役割知識をコード側にハードコードしない」との両立のため）。 |
| `model` | string | `--model`にそのまま渡す値。**team_loader.py側では既知モデル一覧に対する静的検証はしない**（4.3節で理由を説明）。 |
| `order` | integer | 実行順の一次キー（同一依存レイヤー内の決定的順序に使う）。 |

### 4.2 任意フィールド（デフォルト値付き）

| フィールド | 型 | デフォルト | 説明 |
|---|---|---|---|
| `enabled` | bool | `true` | `false`ならロード対象一覧には載るが実行対象から除外（AC-B2）。 |
| `reasoning_effort` | string | `"medium"` | `--effort`に渡す値。**列挙型として厳格検証する**: `none, minimal, low, medium, high, xhigh, max`（1.2節で確認したCLIの固定選択肢）。範囲外の値は設定エラー。 |
| `specialty` | string または string配列 | `[]` | プロンプト本文に付加する得意分野の説明。実行ロジックには影響しない純粋な文脈情報。 |
| `depends_on` | string配列（member id） | `[]` | 依存先メンバーID。存在しないidを指す場合は設定エラー。 |
| `input_artifacts` | string配列 | `[]` | 期待入力（前工程成果物ファイル名の論理名。例: `bid_manager_log.md`）。実ファイルパスへの解決は実行時に`run.py`が`artifacts/`ディレクトリ基準で行う。 |
| `output_artifacts` | string配列 | `[]` | 生成を期待する成果物のファイル名。実行後、`run.py`は列挙された全ファイルが実在するかを検証し、欠落があれば当該メンバーを失敗扱いにする（"やったふり"防止、プレイブック6節のオーケストレーターチェックリストの機械化）。 |
| `timeout_sec` | integer | `1800`（30分） | `subprocess`実行のタイムアウト。Implementer/QAなど検証重めのロールは`3600`等に引き上げてよい。 |
| `max_ai_credits` | integer または null | `null`（無制限） | `--max-ai-credits`に渡す。指定する場合は**最小30**（CLI制約）。省略時は無制限（＝運用側が別途注意する）。 |
| `permissions.allow_all_tools` | bool | `false` | `true`なら`--allow-all-tools`を付与。 |
| `permissions.allow_tools` | string配列 | `[]` | `--allow-tool`に1件ずつ渡すパターン文字列（例: `"write"`, `"shell(git:*)"`）。 |
| `permissions.deny_tools` | string配列 | `["shell(git push)"]` | `--deny-tool`に渡す。**このデフォルト値（git push拒否）は`team_loader.py`が常にマージで追加し、メンバー側の指定で上書き・削除できない**（全メンバー共通のガードレール）。 |
| `permissions.allow_urls` | string配列 | `[]` | `--allow-url`に渡す。省略時はURLアクセス不可（本v6のロールは既定でネット接続不要という判断）。 |
| `permissions.add_dirs` | string配列（絶対パス） | `[]` | `--add-dir`に渡す追加ディレクトリ（対象ワークスペース以外に読み書きが必要な場合）。 |

`permissions`を丸ごと省略した場合は、上記デフォルト値（=実質「書き込み・シェル・URL全て不可」の読み取り専用寄りの安全側設定）が適用される。つまりImplementerロールのように書き込み・シェル実行が必須のメンバーは、**必ず明示的に`permissions`を書かねばならない**。これは「暗黙に強い権限を渡さない」という安全設計であり、4.4節の未知フィールド方針とも整合する。

本文（frontmatter以降のMarkdown本文）は、そのメンバー固有の人格・判断ポリシー・禁止事項・レビュー観点を自然言語で記述する領域とし、`team_loader.py`はここをパースせず**生テキストとしてプロンプト組み立てに渡すのみ**とする。

### 4.3 モデル名を静的検証しない理由

`copilot help config`のモデル一覧は**CLIのバージョンやユーザーのプラン・組織設定に依存して変わりうる**カタログである。今回1.0.80で実在確認した一覧をteam_loader.pyにハードコードして検証すると、CLIが更新される度に「実際には使えるのに設定エラー扱いになる」誤検知が発生しうる。したがって、モデル名の正当性検証は**team_loader.py（静的パース時）では行わず、copilot_cli.py（実行時）が実機のエラー応答（`Error: Model "..." is not available.` → 終了コード1）をそのまま当該メンバーの失敗として扱う**方式に一本化する。これにより「モデルが存在するか」の一次情報源は常にCLI自身になり、二重管理によるドリフトを防ぐ。

### 4.4 未知フィールド・エラー方針（AC-B5の具体化）

| 状況 | 扱い |
|---|---|
| 必須フィールド欠落（`id`/`name`/`role`/`model`/`order`のいずれか） | **致命的エラー**。当該ファイルはロード失敗としてteam全体のロードを中断し、ファイルパスと欠落フィールド名を報告する。 |
| 型不整合（例: `order`が文字列） | **致命的エラー**。 |
| `id`の重複 | **致命的エラー**。どちらを採用するか推測せず、重複している2つのファイルパスを列挙してロード全体を中断する。 |
| `reasoning_effort`が列挙外の値 | **致命的エラー**（4.2節の固定選択肢との不一致）。 |
| `depends_on`が存在しない`id`を指す | **致命的エラー**。 |
| `depends_on`に循環がある | **致命的エラー**（4.5節のアルゴリズムで検出）。 |
| frontmatterに定義していない未知キーが存在 | **警告として記録するが非致命的**。`manifest.json`に`warnings`配列として残し、ロードは継続する（将来のスキーマ拡張やタイプミスの早期発見のため、握りつぶさずに可視化するがパイプライン全体は止めない）。 |
| `model`が実在しない値 | **team_loader.py段階では検証しない**（4.3節）。実行時にcopilot_cli.pyが検出し、当該メンバーの実行失敗として扱う。 |

「致命的エラー」は`team_loader.py`が例外（例: `TeamLoadError`）を送出し、`run.py`はパイプライン開始前に処理全体を中止する（1メンバーもコストのかかるCLI呼び出しを行わない）。これにより、frontmatterの些細な書式崩れで無駄にクレジットを消費することを防ぐ。

### 4.5 `depends_on`循環検出アルゴリズム

Kahnのアルゴリズム（BFSベースのトポロジカルソート）を採用する。

1. 全メンバーの`depends_on`から有向グラフを構築する（`depends_on`に列挙されたidが「先に実行されるべきノード」への辺）。
2. 各ノードの入次数（自分の`depends_on`の要素数）を計算する。
3. 入次数0のノード群をキューに積む。
4. キューから1つ取り出して「実行可能レイヤー」に加え、そのノードに依存している他ノードの入次数を1減らし、0になったものをキューに追加する。これを繰り返す。
5. 全ノード数だけレイヤーに積めれば非循環。**キューが空になった時点でレイヤーに積めていないノードが残っていれば、それらが循環に関与しているノード群であり、そのid一覧を含めて致命的エラーを報告する。**
6. 同一レイヤー内（互いに依存関係がない者同士）の実行順は`order`昇順、次点で`id`昇順の決定的ソートで確定する。

**同一role複数メンバーの並列/逐次規則（AC-B6）**: 上記アルゴリズムが出す「レイヤー」は理論上並列実行可能な集合を表すが、v6のスコープ（AC-A5: 半自動1サイクル、無人N連続運転を前提にしない）に鑑み、**v6ではレイヤー内であってもOSレベルの並列subprocess実行は行わず、レイヤー順・レイヤー内`order`順に逐次実行する**。理由は、(a) クレジット消費の予測可能性を優先する、(b) 同時に複数の`copilot`プロセスを走らせた際のログ・成果物書き込みの競合を今回検証していない、(c) 人間が各ステップを確認しながら進めるUXという要件（AC-A5）と、逐次実行の方が相性が良い、の3点。将来的に真の並列実行が必要になった場合は、`parallel_group`フィールドの追加とロック機構の設計を別途行う前提とし、v6のスコープ外として明記する。

## 5. `copilot_cli.py`（共通ラッパー）の契約（確定）

### 5.1 関数シグネチャ（擬似コード）

```python
@dataclass
class MemberInvocationResult:
    member_id: str
    exit_code: int | None       # None の場合は timed_out=True（プロセスがタイムアウトで強制終了された）
    timed_out: bool
    session_id: str | None      # JSON出力の最終 "result" イベントから抽出
    stdout_path: Path           # 生JSONLログの保存先（{member_id}.stdout.log）
    stderr_path: Path
    meta_path: Path             # {member_id}.meta.json への保存先
    started_at: datetime
    ended_at: datetime
    duration_sec: float
    success: bool                # exit_code == 0 かつ timed_out == False かつ output_artifacts が全て実在

def invoke_copilot_member(
    member: TeamMember,               # team_loader.py が返す検証済みメンバー定義
    prompt: str,                      # 組み立て済みの短い指示文（5.3節参照。成果物の中身は埋め込まない）
    *,
    workspace_dir: Path,              # -C に渡す対象ワークスペース（案件によって毎回異なる）
    run_log_dir: Path,                # このrunのログ格納先（agentic_orgs/logs/runs/{company}/{case_id}/{run_id}/）
    run_name_prefix: str,             # -n に渡すセッション名 "{company}-{case_id}-{run_id}-{member_id}"
) -> MemberInvocationResult:
    ...
```

### 5.2 固定で付与するコマンドライン引数（毎回・全メンバー共通）

```
copilot -p "<prompt>" ^
  --output-format json ^
  --no-color ^
  --no-custom-instructions ^
  --disable-builtin-mcps ^
  --no-remote --no-remote-export ^
  -C "<workspace_dir>" ^
  --add-dir "<run_log_dir>" ^
  --model "<member.model>" ^
  --effort "<member.reasoning_effort>" ^
  -n "<run_name_prefix>" ^
  --log-dir "<run_log_dir>\_copilot_internal\<member_id>" ^
  [--max-ai-credits <member.max_ai_credits>]   # 指定がある場合のみ
  [--allow-all-tools]                          # permissions.allow_all_tools が true の場合
  [--allow-tool=... 複数]                       # permissions.allow_tools の各要素
  [--deny-tool=... 複数]                        # permissions.deny_tools の各要素（"shell(git push)"を常時含む）
  [--allow-url=... 複数]                        # permissions.allow_urls の各要素
  [--add-dir ... 複数]                          # permissions.add_dirs の各要素
```

固定引数の採用理由:
- `--no-custom-instructions`: 対象ワークスペースや本リポジトリのAGENTS.md等がロールペルソナに無関係な指示を混入させることを防ぐ（コンテキスト分離の一環）。
- `--disable-builtin-mcps`: 検証時、`workiq`（needs-auth）や`github-mcp-server`の読み込みで起動時間とノイズが増えることを確認した。本v6のロールはGitHub操作を必須としないため、既定で無効化し、必要なメンバーだけ`permissions`で個別に有効化を検討する（v6スコープでは無効化のままでよいと判断）。
- `--no-remote --no-remote-export`: パイプライン内部の使い捨てセッションをGitHub web/mobileにエクスポートしない。
- `--add-dir <run_log_dir>`: 5.4節で述べる「対象ワークスペースの外にあるログ格納先」への書き込みを許可するために必須。
- `--log-dir`をメンバーごとに分離: CLI自身の内部ログ（`~/.copilot/logs/`相当）がメンバー間で混ざらないようにする（AC-C5の追加防御）。

### 5.3 プロンプト組み立て方針（Windows前提の実務上の理由）

プロンプト文字列には**前工程成果物の中身をテキストとして埋め込まない**。理由は2つある。

1. **AC-C2の要件**（前工程の会話履歴ではなく成果物ファイルの内容のみを渡す）を、実装上も徹底するため。プロンプトには成果物の**絶対パス**のみを記し、「このファイルを読んでから作業せよ」という指示にする。実際にファイルを読むのはメンバー側のCLIプロセスが持つ読み取り系ツールである。
2. **Windowsのコマンドライン長制限の回避**。成果物（設計書・要求書等）は数KB〜数十KBになりうる。`-p`引数にそのまま埋め込むと、`subprocess`が`CreateProcess`を呼ぶ際の実務上安全なコマンドライン長（引用符・日本語のマルチバイト展開を考慮すると数千文字程度が安全域）を超えるリスクがある。ファイルパス参照方式ならこの問題自体が発生しない。

したがって`-p`に渡す実際の文字列は、概ね次の定型形になる（人格プロンプト本文＋タスク定型文＋入力/出力ファイルパスの列挙）。人格本文自体（`team/*.md`の本文）は`--prompt`文字列の一部として埋め込む前提だが、これは高々数百〜数千文字程度であり長さ上のリスクは小さいと判断した。ただし人格本文が将来大きくなる場合は、同様にファイル参照方式へ切り替える余地を残す。

### 5.4 独立プロセス保証の実装方法

- **毎回`subprocess.run()`（またはタイムアウト制御のため`subprocess.Popen` + `communicate(timeout=...)`）で新規プロセスを起動する。** 呼び出し側コード（`run.py`/`copilot_cli.py`）は`--continue`・`--resume`・`--session-id`のいずれも**絶対に指定しないコードパスのみ**を持つ（実装上、これらのCLIオプションを組み立てるロジック自体をcopilot_cli.py内に一切書かないことで、将来の実装ミスによる誤用を構造的に防ぐ）。
- 1.3節の実機確認により、これだけで確認なしに毎回新規`sessionId`が発行されることを確認済みである。
- **検証（保険）**: `invoke_copilot_member`はJSON出力の最終`result`イベントから`sessionId`を抽出し、同一run内で過去に使用したsessionIdの集合と突き合わせ、重複があれば（本来起こり得ないが）警告ログを出す自己検査を組み込む。これはAC-C4の「実行方式またはCLI仕様で説明できる」を、実行時アサーションとしても裏付けるための追加の安全策である。
- 環境変数は明示的に許可したものだけ子プロセスに渡す（`os.environ`をそのまま継承せず、`PATH`・認証まわりの最小セット＋`PYTHONUTF8=1`相当のUTF-8強制設定を明示的に構成した辞書を`subprocess`の`env`引数に渡す）。これにより親（オーケストレーター）セッションの状態がサブプロセスに暗黙に漏れ込む経路を塞ぐ。

### 5.5 タイムアウト・ログキャプチャ・終了コード判定

- `subprocess.run(..., timeout=member.timeout_sec, capture_output=True, text=True, encoding="utf-8", errors="replace")`を用いる。
- 標準出力・標準エラーは**パース前に無加工のまま**`{member_id}.stdout.log` / `{member_id}.stderr.log`に書き出す（パース失敗があっても一次情報が失われないようにする。プレイブックの「成果物ファイル未生成」問題への対処と同じ思想）。
- `--output-format json`のJSONL出力は1行ずつ`json.loads`する。行のパースに失敗した行があっても中断せず、警告として記録し処理を継続する。
- 成否判定は次の**AND条件**とする: `subprocess`の終了コード`== 0` **かつ** タイムアウトしていない **かつ** JSON出力の最終`result`イベントの`exitCode == 0` **かつ** `output_artifacts`に列挙された全ファイルが`artifacts/`に実在する。1つでも欠ければ`success=False`とし、依存する後続メンバーは実行しない（パイプライン停止・エラー報告）。
- タイムアウト時は子プロセスツリーを強制終了する（Windowsでは`Popen`のPIDに対し`taskkill /PID <pid> /T /F`相当、またはPython 3.10+の`subprocess`の`timeout`到達時に自前で`.kill()`し、必要なら`psutil`等を使わずWindows標準の`taskkill`をサブプロセスとして呼ぶ）。放置プロセスが残らないことを、プレイブック6節の「起動したプロセスは必ず停止しているか確認する」の精神に倣い、`run.py`終了時に`Get-Process -Id <pid> -ErrorAction SilentlyContinue`相当のチェックをログに残す。

## 6. `team_loader.py` の設計（確定）

### 6.1 処理フロー

1. 指定ディレクトリ（`contractor_company/team/`または`client_company/team/`）から`*.md`をglobする。`_`始まりのファイルおよび`README.md`はチームメンバー定義として扱わない。
2. 各ファイルについて、先頭が`---\n`で始まることを確認し、2つ目の`---\n`（または`---\r\n`）までをfrontmatterブロックとして切り出す。これ以降の残りを本文とする。frontmatter区切りが見つからない場合は致命的エラー（「YAML frontmatterが見つからない」）。
3. frontmatterブロックを`yaml.safe_load()`でパースする（`PyYAML`を新規に`agentic_orgs/common/requirements.txt`へ追加する。理由: リポジトリの既存`requirements.txt`にはYAMLパーサが含まれておらず、frontmatter方式を採用する以上、軽量かつ標準的な`PyYAML`の追加が最も素直である）。
4. 4章のスキーマに従い型・必須項目・列挙値・`depends_on`参照先の存在をチェックする。違反があれば`TeamLoadError`に蓄積する（**1ファイルのエラーで即座に例外を投げず、全ファイルを検査してからまとめて報告する**。これにより1回の実行で複数の設定ミスをまとめて把握できる）。
5. `id`の重複を全ファイル横断でチェックする。
6. 4.5節のKahnアルゴリズムで`depends_on`の循環を検出する。循環があれば、関与するidの一覧とともに致命的エラーとする。
7. 検証をすべて通過したメンバー一覧から`enabled: false`のメンバーを除外し（AC-B2）、実行対象一覧としてレイヤー分解済みの順序リストを返す。
8. 未知フィールドの警告は`TeamLoadResult.warnings`に集約し、呼び出し側（`run.py`）が`manifest.json`に記録する。

### 6.2 公開インターフェース（擬似コード）

```python
@dataclass
class TeamMember:
    id: str
    name: str
    role: str
    model: str
    order: int
    enabled: bool = True
    reasoning_effort: str = "medium"
    specialty: list[str] = field(default_factory=list)
    depends_on: list[str] = field(default_factory=list)
    input_artifacts: list[str] = field(default_factory=list)
    output_artifacts: list[str] = field(default_factory=list)
    timeout_sec: int = 1800
    max_ai_credits: int | None = None
    permissions: Permissions = field(default_factory=Permissions)
    body: str = ""              # frontmatter以降の生本文
    source_path: Path = None

@dataclass
class Permissions:
    allow_all_tools: bool = False
    allow_tools: list[str] = field(default_factory=list)
    deny_tools: list[str] = field(default_factory=lambda: ["shell(git push)"])
    allow_urls: list[str] = field(default_factory=list)
    add_dirs: list[str] = field(default_factory=list)

@dataclass
class TeamLoadResult:
    members: list[TeamMember]     # enabled=Trueのみ、実行レイヤー順にフラット化済み
    warnings: list[str]

class TeamLoadError(Exception):
    """致命的な設定エラー。1つ以上のエラーメッセージをまとめて保持する。"""

def load_team(team_dir: Path) -> TeamLoadResult: ...
```

## 7. コンテキスト分離の実装方針（明文化）

私は以下の3層で「独立プロセスであることの保証」を担保する設計とした。

1. **構造的保証（設計レベル）**: `copilot_cli.py`の実装コードパス上に、`--continue`・`--resume`・`--session-id`を組み立てる分岐を一切書かない。これらのオプションはBid Managerの懸念通り「セッション継続」を意味するため、コードとして存在しなければ誤って使われようがない。
2. **実行時保証（プロセスレベル）**: 各メンバー呼び出しは`subprocess.run()`による独立OSプロセスであり、5.4節の通り環境変数も明示的に絞って渡す。前メンバーの対話履歴はメモリ上にも一切保持されず（Pythonプロセス側もCLIプロセス側も別プロセスとして起動・終了する）、次のメンバー呼び出し時には新しい`subprocess.run()`が新しい`copilot.exe`プロセスを生成する。
3. **検証時保証（監査レベル）**: 1.3節で確認した通り、CLIは何も指定しなければ新規`sessionId`を発行する。`copilot_cli.py`はこの`sessionId`を`meta.json`に記録し、同一run内でのsessionId重複がないかを自己検査する（5.4節）。また`manifest.json`には各メンバーの`started_at`/`ended_at`/`pid`（可能なら）を記録し、オーケストレーター（人間または上位AI）が事後に「本当に別プロセスだったか」を`manifest.json`とOSのプロセス履歴で追認できるようにする。

「ファイル成果物のみが例外」というAC-C6の要件は、5.3節のプロンプト設計（成果物の中身を埋め込まず、ファイルパスのみを渡す）と、6章の`input_artifacts`/`output_artifacts`フィールドの組で実現する。`run.py`は、あるメンバーの`output_artifacts`が、次に実行するメンバーの`input_artifacts`として`artifacts/`ディレクトリ上に実在することを、実行前の事前条件チェックとして機能させる（存在しなければ、依存元メンバーが実は失敗していたことの検出にもなる）。

## 8. ABMパラメータ→委託元ペルソナ変換：一次根拠パラメータ（確定）

私は`outsourcing_sim/params.py`のコメント区分（`# --- A (client) policy parameters ---` / `# --- budget policy ---` / `# --- environment parameters ---`）と、`docs/experiments/005_phase6_product_multiagent_case_study.md`に記録されている**過去のArchitectがBid Manager案を実際に是正した事例**（`gamma`を「B社の技術力成長速度」と誤解していた／`budget_c0`・`budget_c1`を「B社のコスト計算定数」と誤解していた、という誤りが実際に発生し、Architectがソースコードで訂正した）を突き合わせて検証した。今回のBid Manager案はこの過去の誤りを踏まえて`gamma`＝A社のエスカレーション率、`budget_c0/c1`＝A社の予算式係数、と**正しく**書けていることを確認した。その上で、私は次の理由で一次根拠パラメータを絞り込む。

### 8.1 採用する一次パラメータ（6個）

`params.py`のコメント区分で明示的に「A（client）policy」または「budget policy」に分類されているもの、および委託元の初期要求水準を直接表す`difficulty_0`のみを一次根拠として採用する。

| パラメータ | 既定値 | ペルソナ軸への効き方 |
|---|---|---|
| `gamma` | 0.15 | 高いほど「野心的・要求を急速に高度化する」トーン。 |
| `difficulty_0` | 1.0 | 高いほど「初回から高難度・大規模な要求を出す」。 |
| `budget_c0` | 5.0 | 高いほど「最低保証予算が手厚い＝太っ腹」。 |
| `budget_c1` | 15.0 | 高いほど「難易度・評判に応じた予算の伸びが大きい＝業績連動で気前が良い」。`outsourcing_sim/simulate.py`の`_budget_for()`実装 `budget_c0 + budget_c1 * difficulty * (0.5 + 0.5 * reputation)` をソースコードで確認し、根拠とした。 |
| `partial_pay` | 0.0 | 高いほど「失敗しても部分報酬を出す＝寛容」。 |
| `r_min` | 0.4 | 高いほど「評判が少しでも落ちると契約打ち切りにする＝レビューが厳格」。 |
| `max_consecutive_failures`（K） | 3 | **低いほど**「連続失敗に厳しい＝レビューが厳格」（他5項目と符号が逆であることに注意）。 |

### 8.2 明示的に除外するパラメータとその理由

- **`funds_0`**: `params.py`のコメントは`# initial contractor funds`であり、**受託会社（B社）側の資源**であって委託元（A社）の性格を表す変数ではない。Bid Manager自身も「一次入力にするかはArchitect判断」と留保していたが、私はソースコードの変数名・コメントに照らして**明確に不適切**と判断し除外する。委託元ペルソナのプロンプトで言及する場合も「相手（B社）の体力に関する参考情報」という補助的な文脈情報に限定し、性格・トーンを決める一次根拠には使わない。
- **`alpha, beta, k1, cost_curve_exponent, lam, sigma_noise`**: これらは`params.py`で「structural parameters」に分類されており、ゲーム全体の力学パラメータであってA社固有の意思決定方針ではない（`docs/experiments/002_stage1_screening.md`でも`k1`や`beta`は感度分析上重要だが、これは「市場全体の条件の厳しさ」であり「A社という個別法人の性格」ではないと解釈した）。よってペルソナ根拠には含めない。
- **`strategy`**: `params.py`のコメント通り`# --- B (contractor) strategy ---`であり、B社側の戦略変数。委託元ペルソナには無関係。

### 8.3 プロンプトへの落とし込み方（2軸への集約）

6個の一次パラメータをそのまま6個の独立した性格記述にすると、Implementerがプロンプトを書く際に人格として一貫性のない文章になりやすい。私は次の2軸に集約することを推奨する（`persona_mapping.py`が担う変換ロジック）。

- **野心度軸**（`gamma`, `difficulty_0`, `budget_c0/c1`の複合）: 高いほど「早く・大きく成長させたい、要求も予算も積極的」なトーン。
- **厳格度軸**（`r_min`, `max_consecutive_failures`の逆数的扱い, `partial_pay`の逆）: 高いほど「失敗に不寛容、評価がシビア」なトーン。

各パラメータについて、`params.py`のデフォルト値を基準（1.0倍）とした比率で「低（<0.7倍）／中（0.7〜1.3倍）／高（>1.3倍）」の3段階に分類し、各軸に属するパラメータの段階を単純多数決（同数なら中央寄り）で軸のレベルを決定する、という**単純で説明可能なルール**を採用する。複雑な加重平均や機械学習的手法は採用しない。理由は、AC-D1「同じABMパラメータセットを与えたとき、委託元の要求トーンとレビュー厳しさの根拠を説明できる」を満たすには、閾値ベースの単純な多数決の方が人間にもLLMにも説明可能性が高いためである。

**AC-D4（ペルソナ文と要求本文の分離）の実現方法**: 2軸から導かれる性格描写（例:「野心度: 高、厳格度: 中」→「あなたは急成長を狙う野心的な発注担当者です。要求は積極的に高度化させますが、明らかな不履行でない限り改善の機会は与えます」）は`client_company/team/requester.md`・`reviewer.md`の**本文（自然言語ペルソナ記述）**にのみ反映する。一方、`difficulty_0`や`budget_c0/c1`の**具体的な数値そのもの**は、`request_brief_template.md`が生成する要求書本文（納期・予算感・優先度などの具体的記述）に直接反映し、"性格の演出"と"契約条件の実体"を明確に別ファイル・別セクションに分ける。

## 9. 実クレジット消費を抑えるための注意点

私自身、本ログ作成のために実際に3回`copilot -p`を実行し、実クレジットを消費した（いずれも`gpt-5-mini`・`effort=low`・`--max-ai-credits 30`のキャップ付きで、ツール不使用の1トークン級の応答のみを要求する内容に限定した）。この経験を踏まえ、Implementerへの注意点を以下に確定する。

1. **Implementerが行う動作確認は、実装した`copilot_cli.py`・`team_loader.py`の配線が正しいかを検証する目的に限定し、実際のBid Manager/Architect/Implementer/QAロールの「本番品質のフル実行」を通しで何度も回してはならない。** 最小限のダミー人格ファイル（例:「Reply with exactly one word.」程度の指示しか持たないテスト用`team/_test_member.md`）で1〜2回、パイプラインの配線（引数組み立て・ログ保存・成否判定・依存関係解決）が動くことを確認すれば十分である。
2. **モデルは既定で最も安価な`gpt-5-mini`・`effort: low`または`minimal`を使い、`--max-ai-credits`を最小値30に設定した状態で動作確認を行うこと。** 高性能モデル（`claude-sonnet-5`等）・高reasoning_effortでの通し実行は、実際の受託パイプライン運用時（人間が使う本番実行）のためにとっておく。
3. **ツールを使わせない検証（`--allow-tool`を絞る、または明示的に「ツールを使わず一言だけ返答せよ」という指示にする）で、まず配線を確認してからツール利用を伴う検証に進むこと。** ツール呼び出し（特にファイル書き込み・シェル実行）はトークン消費・実行時間ともに大きくなりやすい。
4. **失敗した検証をやみくもにリトライしない。** まず`{member_id}.stdout.log`/`.stderr.log`の生ログを読んで原因を特定してから再実行する。CLIの終了コード・エラーメッセージは1.2節・1.3節の通り明確に得られるため、原因不明のまま再実行を繰り返す必要はないはずである。
5. **タイムアウト・異常終了時に子プロセスが残存していないか、`Get-Process`等で確認する。** 実クレジット消費とは別に、放置プロセスがリソースを食い続けるリスクがある。

## 次工程への申し送り（Implementer向け確定仕様サマリー）

以下、そのまま実装に着手できる粒度でまとめる。詳細根拠は本ログの該当節を参照すること。

### A. ディレクトリ構成（3節）
```
agentic_orgs/
├── common/{copilot_cli.py, team_loader.py, requirements.txt}
├── client_company/{team/*.md, templates/*.md, persona_mapping.py, run.py}
├── contractor_company/{team/*.md（bid_manager/architect/implementer/qa/brand_designer）, templates/, run.py}
└── logs/
    ├── v6_*_log.md（本メタ開発工程。既存と同じ場所にそのまま追加）
    └── runs/{company}/{case_id}/{run_id}/{manifest.json, {member_id}.stdout.log, {member_id}.stderr.log, {member_id}.meta.json, artifacts/}
```
- `run_id` = `run_{YYYYMMDD}-{HHMMSS}_{6桁hex}`。`case_id`省略時は`default`。
- パイプライン成果物は対象ワークスペースの中には書き込まない。常に`agentic_orgs/logs/runs/...`側に置く（対象ワークスペースを汚さないため）。

### B. `team/*.md` frontmatterスキーマ（4節）
- 必須: `id`(regex `^[a-z][a-z0-9_-]*$`, unique), `name`, `role`, `model`, `order`(int)
- 任意（デフォルト）: `enabled`(true), `reasoning_effort`(`"medium"`, 列挙型`none/minimal/low/medium/high/xhigh/max`のみ許可), `specialty`([]), `depends_on`([], 存在idのみ許可・循環禁止), `input_artifacts`([]), `output_artifacts`([]), `timeout_sec`(1800), `max_ai_credits`(null, 指定時は≥30), `permissions.{allow_all_tools=false, allow_tools=[], deny_tools=["shell(git push)"]固定マージ, allow_urls=[], add_dirs=[]}`
- `model`はteam_loader側で静的検証**しない**（実行時にCLIのエラー応答で検出）。
- エラー方針: 必須欠落/型不整合/id重複/reasoning_effort列挙外/depends_on不正・循環 = 致命的エラー（ロード全体中断、1回のCLI呼び出しも行わない）。未知フィールド = 警告のみでロード継続。

### C. `copilot_cli.py`契約（5節）
- `invoke_copilot_member(member, prompt, *, workspace_dir, run_log_dir, run_name_prefix) -> MemberInvocationResult`
- 毎回`subprocess.run()`で新規プロセス起動。**`--continue`/`--resume`/`--session-id`を組み立てるコードは書かない。**
- 固定引数: `-p <prompt> --output-format json --no-color --no-custom-instructions --disable-builtin-mcps --no-remote --no-remote-export -C <workspace_dir> --add-dir <run_log_dir> --model <model> --effort <reasoning_effort> -n <run_name_prefix> --log-dir <run_log_dir>\_copilot_internal\<member_id>`
- `permissions`から`--allow-all-tools`/`--allow-tool`/`--deny-tool`/`--allow-url`/`--add-dir`を追加。`max_ai_credits`指定時は`--max-ai-credits`追加。
- プロンプトには前工程成果物の**中身を埋め込まず、ファイルパスのみ**を渡す（Windowsコマンドライン長制限回避＋AC-C2遵守）。
- 成否判定 = `exit_code==0` AND `not timed_out` AND JSON最終`result`イベントの`exitCode==0` AND `output_artifacts`が全て実在。
- stdout/stderrは加工前に生ログとして保存してからパースする。JSONL各行のパース失敗は警告のみで継続。
- タイムアウト時は子プロセスを強制終了し、放置がないか確認する。

### D. `team_loader.py`設計（6節）
- `load_team(team_dir) -> TeamLoadResult(members, warnings)` / 失敗時`TeamLoadError`
- 処理順: glob → frontmatter区切り抽出 → `yaml.safe_load` → スキーマ検証（全ファイル分まとめてエラー収集）→ id重複チェック → Kahnアルゴリズムで循環検出 → `enabled=false`除外 → レイヤー順（レイヤー内は`order`昇順→`id`昇順）にフラット化して返す。
- v6では同一レイヤーでも**逐次実行**（並列実行は将来課題として`parallel_group`拡張に委ねる）。

### E. ペルソナ変換 一次パラメータ（8節）
- 採用6パラメータ: `gamma`, `difficulty_0`, `budget_c0`, `budget_c1`, `partial_pay`, `r_min`, `max_consecutive_failures`
- **`funds_0`は除外**（B社側資源であり、A社ペルソナの一次根拠にしない。参考情報として言及する程度に留める）
- `alpha/beta/k1/cost_curve_exponent/lam/sigma_noise/strategy`も除外（ゲーム構造パラメータ、またはB社戦略変数のため）
- 変換ルール: 各パラメータをデフォルト値比で低(<0.7x)/中(0.7〜1.3x)/高(>1.3x)の3段階に分類し、「野心度軸」（`gamma`/`difficulty_0`/`budget_c0`/`budget_c1`）と「厳格度軸」（`r_min`/`max_consecutive_failures`の逆/`partial_pay`の逆）の2軸に多数決で集約。数値そのものは要求書本文（テンプレート側）に、性格描写は`team/*.md`本文にのみ反映し、両者を混在させない。

### F. 実機確認で判明した安全上の必須事項（再掲・重要）
1. 非対話実行では**`--allow-all-tools`（またはそれに相当する明示的な`--allow-tool`群）が実質必須**。省略した場合の挙動（ハングするか等）は未検証のため、Implementerは実装着手前に一度だけ、タイムアウト付きの安全な形で確認すること。
2. モデル名の妥当性はCLIが実行時に判定する（`Error: Model "..." is not available.` / 終了コード1）。team_loader側では検証しない。
3. `--output-format json`時は`--silent`を付けてもイベントストリーム全体が出力される（silentが効くのはtextモードのみ）。ログ設計はJSON全体を保存する前提で行う。
4. CLIは自動更新される（今回の検証中に1.0.77→1.0.80へ変化した）。Implementer着手時に`copilot --version`と`copilot --help`を再実行し、本ログとの差分がないか一度確認すること。
5. 動作確認は`gpt-5-mini`・`effort=low/minimal`・`--max-ai-credits 30`・ツール不使用の最小プロンプトに限定し、フル品質のロール実行を検証目的で何度も回さないこと。
