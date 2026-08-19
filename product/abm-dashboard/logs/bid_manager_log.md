# 受託可否判断ログ — Bid/Go-No-Go Manager

私はまず既存コードを確認した。
outsourcing_sim パッケージは以下の点でダッシュボード要求を直接満たせると判断する。

要点（コード確認）
- simulate.run_many は Monte Carlo バッチを実行し、summary dict のリスト（各試行の要約）を返す。keep_traces=True でフル trace も取得可能。
- summarize_trace が返す summary は seed, strategy, survival_rounds, success_rate, final_funds, final_quadrant, end_reason, total_cost, total_payment, net_profit を含む（さらに run_params をマージしている）。
- run_game が各ラウンドの trace（round, tier, n_agents, capability, difficulty, cost, payment, success, funds, reputation, capability_margin, funding_runway, quadrant, bankrupt）を記録している。
- モデル関数（model.py）は capability, credit_cost, success_probability, funding_runway, quadrant を提供する。quadrant は文字列ラベル（"dominant_leader" 等）を返す。
- パラメータ構造は SimParams dataclass で一元管理され、to_dict で JSON 直下に出せる。
- strategies.py に STRATEGIES があり、要求された3戦略は揃っている（conservative, cost_optimal, adaptive）。

ギャップ／追加で実装が必要な点
- run_many の出力は直接 JSON シリアライズ可能（数値と文字列の辞書）が、frontend が必要とする「各試行の最終 (capability_margin, funding_runway) の散布図用ポイント」や「survival_rounds のヒストグラム」は、run_many の summary＋/または trace の最終行から容易に作れるが、API 層でどの形で返すかの定義が必要。
- パフォーマンス：Python 実行はシングルスレッドループで n_trials <= 500 なら通常数秒で終了すると期待されるが、実測ベンチマークがないため API レイテンシ保証には検証が必要（numpy RNG +軽量ループのため期待値は良好）。
- パラメータ検証：SimParams は型付き dataclass だが API 受け口での検証（範囲チェック、戦略文字列の整合）は実装が必要。
- JSON に含めるための型変換：summary と traces は数値/文字列なので問題ない。np.float64 が混入する可能性はあるが FastAPI の JSONResponse は Pydantic を使えば自動変換可能。trace をそのまま返す場合は float 型を標準 float に変換しておくと安心。
- 同時実行・負荷：同時に複数ユーザーが 500 トライアル実行すると CPU負荷が高くなるため、バックエンド側でタイムアウト・同時実行制限を検討すべき。

受け入れ基準（Acceptance Criteria）
以下は QA と開発チームがテスト可能なチェックリスト（番号で追跡可能）。

1) 動作開始
  1.1 FastAPI アプリが `uvicorn product.abm_dashboard.app:app --reload` 等でローカル起動できること（README に起動手順を記載）。

2) API 契約（/api/simulate）
  2.1 エンドポイント: POST /api/simulate
  2.2 リクエスト JSON（サンプル、全てオプションでデフォルトは SimParams の baseline）:
    {
      "params": { <SimParams 相当のキー:alpha,beta,gamma,k1,cost_curve_exponent,D_0（difficulty_0）,Funds_0（funds_0）,r_min,K（max_consecutive_failures）,sigma_noise, strategy, max_rounds, partial_pay, ...> },
      "n_trials": 100,
      "base_seed": 0,
      "presets": "baseline" | "all_strategies" | null
    }
  2.3 レスポンス JSON（正常系、schema の概略）:
    {
      "meta": { "n_trials": int, "elapsed_seconds": float, "presets": str|null },
      "aggregates": {
         "success_rate": float,            // 試行あたりの平均(success_rate ＝ successes / survival_rounds) の平均ではなく、各試行の success_rate を平均したもの
         "bankruptcy_rate": float,         // 試行中に bankrupted と判定された割合
         "mean_survival_rounds": float,
         "mean_net_profit": float,
      },
      "per_trial": [                         // 長さ n_trials の配列
         { "seed": int, "strategy": str, "survival_rounds": int, "success_rate": float, "net_profit": float, "final_quadrant": str, "final_capability_margin": float, "final_funding_runway": float }
      ],
      "plot_data": {
         "quadrant_points": [               // 散布図用: 各試行の最終点
            { "x": float, "y": float, "quadrant": str, "seed": int, "strategy": str }
         ],
         "survival_histogram": {           // ヒストグラム作成に必要な生の survival_rounds 配列
            "values": [int,...]
         }
      }
    }
  2.4 `presets: "all_strategies"` を指定した場合、バックエンドは同一の params（seeding は各戦略内で base_seed+offset）で3戦略を走らせ、per_trial に strategy ごとの結果を含める。

3) フロントエンド要件（UI）
  3.1 単一ページにパラメータフォーム（主要パラメータ: alpha, beta, gamma, k1, cost_curve_exponent, D_0, Funds_0, R_min, K, sigma_noise, strategy, n_trials）と「Run Simulation」ボタンを配置。
  3.2 プリセットボタン: "Baseline"（デフォルト SimParams）と "All strategies comparison"。
  3.3 出力表示: 成功率(success_rate)、倒産率(bankruptcy_rate)、平均生存ラウンド(mean_survival_rounds)、平均純利益(mean_net_profit) を数値表示。
  3.4 ビジュアライゼーション: Chart.js を用いた
     - 散布図 (quadrant plot): 各試行の (final_capability_margin, final_funding_runway)、点色は quadrant ラベルで分ける。
     - ヒストグラム: survival_rounds の分布。
  3.5 n_trials <= 500 の入力で「Run Simulation」を押してから応答までおおむね数秒以内（目標: < 5s）であること（バックエンド性能に依存）。

4) 実装品質
  4.1 API が入力パラメータの基本的なバリデーションを行う（数値範囲、strategy 値チェック）。
  4.2 出力 JSON は完全に JSON 直列化可能（numpy 型や Python set を含まない）。
  4.3 単体テスト: run_many を使った統合テストを1つ追加し、n_trials=10 でレスポンス形状が上記 schema に一致することを確認する（CI の一部として推奨）。

5) ドキュメント
  5.1 README（product/abm-dashboard/README.md）に起動手順、API 例、そしてプリセットの説明を記載すること。

リスクと未解決事項
- 性能リスク
  - run_many は Python ループで RNG+軽い計算を行うため、n_trials=500 は多くの場合数秒で終わる想定だが、実際のマシンで計測・チューニングが必要。もし応答が遅ければバックグラウンドジョブ（非同期処理）やワーカーキュー（Celery 等）を導入する余地があるが、これは本番の拡張であり初版では不要。
- 同時実行制御
  - 単一プロセスで多数ユーザーが同時に500試行を実行するとリソース枯渇するため、API 側で最大 n_trials 制限や同時実行数制限を設けるべき。
- 型・直列化
  - traces のまま返すと numpy.float64 が含まれる可能性があるため、API 層で float() にキャストしてから返す実装が必要。
- パラメータの意味の不一致
  - フロントエンドのフィールド名（例: D_0 → difficulty_0, Funds_0 → funds_0, K → max_consecutive_failures）を API と一致させる必要。受け渡しレイヤーでマッピングを明示する。
- 再現性
  - `presets: all_strategies` の挙動で seed の取り扱い方を設計する必要（各戦略で同一シード列を使うか否か）。推奨: base_seed を受け取り strategy 毎に base_seed + offset を使う。

Go / No-Go 判定
- 結論: Go（着手可）

理由: 既存の outsourcing_sim は再利用に非常に適している。run_many と summarize_trace が必要なメトリクス／最終状態（quadrant, capability_margin, funding_runway, survival_rounds, net_profit）を既に出力しているため、ダッシュボードのバックエンドは比較的少ないラッパー実装で実現可能である。追加の実装は API 層（リクエスト/レスポンスの整形、パラメータ検証、JSON 直列化）、軽量なフロントエンド、及び運用上の同時実行制限である。

範囲（Scope Boundary）
- 含む
  - FastAPI ベースのシンプル API (POST /api/simulate)
  - 同一アプリで配信される静的シングルページフロントエンド（HTML+JS、Chart.js）
  - presets（baseline、all_strategies）
  - 入力バリデーション、基本的なエラーハンドリング
  - ローカル起動手順の文書化

- 明確に除外（今回のバージョンでは実装しない）
  - 認証・認可
  - 永続化（DB）やユーザープロファイル保存
  - マルチユーザー高可用運用（スケーリング、ワーカーキュー、ジョブ管理）は初版外
  - LLM の実行や外部 API 呼び出し（要件にも明記された通り禁止）
  - 複雑な可視化（軌跡アニメーション、詳細な対話型解析）は初版では省略

## 次工程への申し送り

- Acceptance Criteria を満たすため、実装チームへ最低限伝える事項:
  1) API 仕様に沿った POST /api/simulate を実装すること。リクエストボディは SimParams を受け取りうる形にし、フロントエンド名と内部名のマッピング（例: D_0 → difficulty_0）を明示して実装する。
  2) run_many(..., keep_traces=True) を使い、各試行の最終 trace[-1] から capability_margin と funding_runway を抽出して per_trial と plot_data.quadrant_points を構築すること。
  3) 戻り値は純粋な Python 組み込み型のみを含むように float(), int(), str() にキャストすること（numpy 型が混在しないよう注意）。
  4) n_trials の上限（推奨500）と同時実行制限をバックエンドで enforce すること。タイムアウトや 400/429 の返し方を設計すること。
  5) `presets: "all_strategies"` は内部で3戦略をループし、それぞれの strategy 名を per_trial の各要素に含めて返す（seed は base_seed + offset）。
  6) フロントエンドは Chart.js を使い、散布図とヒストグラムを実装する。UI は単一ページで完結させる。

以上。