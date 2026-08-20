# v3 Bid Manager Log — Bid Manager

作成者: Bid Manager (私)
日時: 2026-08-20T09:12:48+09:00

## 要約
クライアントのv3要求を受け、UI/分析/可視化の修正案を正式に受け入れ可否判断。バックエンドAPI契約(`/api/simulate`)は後方互換を維持する前提。

## 受け入れ基準 (Acceptance Criteria)

AC1 Legend / Scatter visualization
- AC1.1: Chart points MUST be colored only by quadrant (dominant_leader, cash_starved_specialist, deep_pockets_shallow_skills, exit_candidate) using the existing quadrantColors mapping.
- AC1.2: Strategy MUST be encoded by marker shape (circle/square/triangle) when compare_strategies=true; marker shapes must be consistent and documented in the UI.
- AC1.3: Remove Chart.js built-in legend that lists per-strategy color. Only keep the existing quadrant-meaning panel (`#quadrant-legend`) as the single legend source of truth.
- AC1.4: Tooltips must show both strategy (日本語＋(enum)) and quadrant (日本語＋(enum)), seed, x/y to two decimals.

AC2 Spread & readability
- AC2.1: Add slight opacity (e.g., alpha=0.85) and jitter (small random offset within ±0.12 on x/y) to plotted points to reduce overplotting.
- AC2.2: When compare_strategies=true, use distinct marker shapes per strategy AND apply a thin stroke (border) in neutral color to improve contrast between quadrant fill color and marker shape.

AC3 Deeper analysis (analytics)
- AC3.1: Response UI must include per-strategy quadrant distribution percentages (e.g., % of trials in each quadrant) derived from existing per_trial data; display these in summary cards.
- AC3.2: Provide a concise per-strategy tendency commentary sentence generated client-side from the quadrant distribution and existing aggregates (success_rate, bankruptcy_rate). Example rules documented in log.
- AC3.3: Add a lightweight parameter sensitivity/correlation view: run up to 3 short extra sweeps using existing API by reusing `run_many` semantics (client-side will call `/api/simulate` multiple times with `n_trials` reduced) — default: sweep `sigma_noise` ±25% and `k1` ±25% at 3 points each (low/base/high) and compute simple monotonicity/correlation (Pearson r) vs mean_net_profit. Show results as a small table + max observed delta in mean_net_profit.
- AC3.4: All new analytics must be computed without changing the `/api/simulate` response schema; reuse existing endpoint (client orchestrates additional calls). Any backend change must be avoided unless performance proves insufficient.

AC4 Visual design refresh
- AC4.1: Replace Arial default with system UI font stack for modern feel; update panel colors to higher-contrast palette while preserving accessibility.
- AC4.2: Improve card typography (metric labels bold, values larger) and add subtle shadows and rounded layout as in v2 architect guidance.
- AC4.3: Chart container sizing remains responsive with maintainAspectRatio:false (already present). Mobile height reduced to 280px.

AC5 Backward compatibility & tests
- AC5.1: Do NOT change `/api/simulate` request/response JSON fields or enum values.
- AC5.2: Existing tests (`tests/test_api.py`) MUST continue passing unchanged after UI/frontend changes.
- AC5.3: Any additional client-side network calls for sensitivity sweeps must respect n_trials<=500 guardrail and provide UI warnings if user-requested sweeps would exceed recommended limits.


## 実現性評価 / 技術アセスメント

- Legend & scatter fix: Purely frontend changes in `static/index.html`/Chart.js options. Implementable without backend edits.
- Spread visibility: Frontend only: set pointBackgroundColor based solely on quadrant and use `pointStyle` per dataset or per-point when compare mode; jitter can be applied client-side by perturbing x/y values when rendering (do not alter server data). This preserves raw data while improving visual spread.
- Strategy shapes: Chart.js supports `pointStyle` per-dataset; in compare mode create one dataset per strategy but set `backgroundColor` to quadrant color via `pointBackgroundColor` array and set `pointStyle` to shape per-dataset. To avoid built-in legend showing strategy color, disable legend or provide custom legend for shapes; ensure quadrant legend remains.
- Deeper analysis (sensitivity/correlation): Current backend (`app.py` + `outsourcing_sim.run_many`) already supports repeated simulation runs and returns aggregates; no new endpoint required. Approach: client issues multiple `/api/simulate` requests with modified params and smaller n_trials (e.g., 50–100) to keep response time reasonable. Compute Pearson r and percent deltas client-side. Performance: running multiple runs increases total compute linearly; with n_trials<=500 and typical run times (see `meta.elapsed_seconds`), recommend default sweeps of 3×3 runs at n_trials=50 (9 runs) — likely acceptable but must surface estimated time to user using `meta.elapsed_seconds` from preliminary single-run probe. If running server-side heavy sweeps is required, consider adding server-side asynchronous job in future.

## 推奨作業方式 (how to implement without backend change)

- Frontend only: edit `product/abm-dashboard/static/index.html`
  - Change drawScatter: build datasets per strategy only when compare=true; keep dataset.label omitted or set to null and disable Chart.js legend (plugins.legend.display=false). Use `pointStyle` mapping: conservative->'circle', cost_optimal->'rectRounded', adaptive->'triangle'. Use `borderColor` and `borderWidth` to draw neutral stroke.
  - For each point, set `pointBackgroundColor` to quadrantColors[quadrant], and set `pointStyle` per dataset. Apply jitter by adding small random offset to x/y in the drawn data (do not mutate original response object).
  - Compute quadrant distributions from response.per_trial and add UI elements to strategy cards showing percentage per quadrant.
  - Implement sensitivity sweep orchestration: a compact UI control "分析スイープ（オプション）" that when enabled triggers multiple smaller `/api/simulate` calls; aggregate results client-side and display correlation and max delta.
  - Improve CSS (font stack, typography, subtle shadows) per AC4.

## Go / No-Go decision

Decision: GO (implementable as frontend-only changes with acceptable risk)

Rationale:
- All functional requirements can be satisfied by client-side changes; backend contract remains intact, preserving tests and reproducibility.
- Sensitivity/correlation can be implemented by orchestrating multiple existing `/api/simulate` calls at reduced n_trials; avoids backend changes and keeps v3 lightweight.

Risks:
- Performance: multiple sequential `/api/simulate` calls may increase user wait times and server load. Mitigation: default small n_trials for sweeps, show progress and allow cancel; limit concurrent sweeps.
- Statistical validity: client-side correlation from small n_trials may be noisy and misleading. Mitigation: clearly label results as "探索的（低試行数）」, show confidence caveats (sample size, Pearson r p-value not computed), and recommend Architect verify.
- UX complexity: adding sweeps and shape legend may confuse non-technical users; mitigate by keeping UI minimal and providing concise explanatory hover text.


## 実装注意事項 / QA checklist

- Keep API enums (strategy, final_quadrant) unchanged. Run full `pytest product/abm-dashboard/tests/test_api.py`.
- Ensure Chart.js legend disabled for strategy color; keep quadrant panel as single legend.
- Do not persist jittered coordinates back to server; jitter only for visualization layer.
- Respect n_trials<=500 guardrail for all user-initiated calls; if combined sweeps would exceed a practical limit, require user confirmation.


## 次工程への申し送り

アーキテクトへ: 下記を必ず実施してから分析文言や図表の最終版を確定してください。

- 私が設計した感想文（per-strategy tendency commentary）と感覚的な相関説明は「草案」です。必ず `outsourcing_sim/model.py`, `outsourcing_sim/simulate.py`, `outsourcing_sim/params.py` のロジックを読んで、私の推論（どの指標がどのパラメータに敏感か・四象限の閾値など）がソースコードと一致することを検証してください。
- 特に感度分析（sigma_noise, k1の変化が mean_net_profit に与える影響）の統計的正当性をコードベースの出力分布で検証し、必要であれば試行回数（n_trials）を増やすか検定（例：t検定）を追加してください。
- UIによる"探索的分析"の結果には必ず注釈を付けてください（例: 小サンプルのため示唆に留める等）。

以上。

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>
