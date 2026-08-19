# Experiment 003: Stage 2 — Focused factorial + Stage 3 statistical analysis

**Grid**: `configs/stage2_focused_grid.json` — full factorial over
`strategy` (3) × `max_consecutive_failures` (3) × `beta` (3) × `k1` (3) × `gamma` (3)
= 243 design points × 100 Monte Carlo seeds = 24,300 games.

**Scripts**:
```
python scripts/run_monte_carlo.py --grid configs/stage2_focused_grid.json --n-seeds 100 --out results/stage2_focused.parquet
python scripts/analyze_results.py --input results/stage2_focused.parquet --out-dir results/figures_stage2
python scripts/stage3_stats.py --input results/stage2_focused.parquet
```

> Note: `n=100` per design point is a compute-budget compromise for this
> demonstration run; Experiment 001 estimated ~1,591 replications would be needed for a
> ±2pt 95% CI on success_rate. A production-scale study should re-run the top design points
> (or the whole grid, if resources allow) at the full replication count.

## Summary by strategy

| strategy | mean success_rate | mean survival_rounds | bankruptcy_rate | mean net_profit |
|---|---|---|---|---|
| adaptive | 0.736 | 17.26 | 0.600 | -118.3 |
| conservative | 0.828 | 19.45 | 0.032 | -47.4 |
| cost_optimal | 0.657 | 13.68 | 0.430 | -63.1 |

## Final-state quadrant distribution (proportion)

| strategy | cash_starved_specialist | dominant_leader | exit_candidate |
|---|---|---|---|
| adaptive | 0.598 | 0.351 | 0.051 |
| conservative | 0.165 | 0.000 | 0.835 |
| cost_optimal | 0.456 | 0.544 | 0.000 |

## Stage 3 statistical results (highlights)

### Logistic regression (GLM/Binomial) — `success_rate ~ strategy + max_consecutive_failures + beta + k1 + gamma`

All terms significant (p<0.001). Odds ratios:
- `conservative` vs `adaptive` baseline: **OR≈2.61** (much higher success rate)
- `beta` (success-sensitivity): OR≈1.15 per unit — steeper sigmoid helps once capability trends positive
- `k1` (cost scale): OR≈0.87 per unit — higher cost pressure forces riskier under-investment, lowering success
- `gamma` (escalation rate): OR≈0.16 per unit — faster difficulty escalation sharply reduces success rate

### Cox proportional hazards — `survival_rounds ~ strategy + factors`, event = bankruptcy/contract termination

- **No runs were censored at `max_rounds=200`** in this grid — every game ended before the cap,
  i.e. under all swept configurations the repeated game always resolves (via bankruptcy or contract
  termination) well before 200 rounds. This is itself a modeling finding: the current escalation +
  cost dynamics guarantee termination, so studying "indefinite survivors" would require either a much
  higher `difficulty_cap`/`max_rounds`, or damping `gamma` further.
- `gamma` has by far the largest hazard ratio (exp(coef)≈8.6e4) — escalation rate is the dominant
  driver of *how fast* the game ends, consistent with the Morris screening ranking.
- `max_consecutive_failures` (HR≈0.72) and `beta` (HR≈0.95) reduce hazard (i.e., more tolerance for
  failure and higher success sensitivity both extend survival).
- `k1` increases hazard (HR≈1.88): higher baseline cost accelerates the endgame, as expected.

### OLS — `net_profit ~ strategy * (max_consecutive_failures + beta + k1 + gamma)`

R²≈0.245. Notable interactions: the `conservative` strategy's profit sensitivity to `k1` and
`gamma` differs sharply from `adaptive`/`cost_optimal` (large interaction coefficients),
confirming that **the best strategy is contingent on the cost/escalation regime** rather than
uniformly dominant — refining hypothesis H4 (adaptive is not universally best; it is a compromise
that avoids the `conservative` strategy's extreme quadrant-4 (exit_candidate) outcome under
aggressive escalation, at the cost of a much higher bankruptcy rate than `conservative`).

## Revisiting the hypotheses (H1–H4)

- **H1** (funding exhaustion dominates over technical failure): **Supported** — bankruptcy_rate
  is substantial for `adaptive` (60%) and `cost_optimal` (43%), and even `conservative`'s low
  bankruptcy rate is offset by a 83.5% "exit_candidate" (technical+funding trap) outcome, i.e.
  contract termination due to falling behind on capability while also running low on funds.
- **H2** (frontier-tier overuse becomes inefficient): partially addressed via `cost_curve_exponent`
  in the Stage 1 screening (ranked #3 on success_rate); a dedicated Stage 2 sweep on this factor
  is recommended as follow-up (see "Future work" below).
- **H3** (agent-count scaling depends on α): `alpha` ranked mid-table in Stage 1
  (5th on success_rate, 5th on survival_rounds) — worth a dedicated focused run.
- **H4** (adaptive strategy dominates): **Not supported as stated** — `conservative` has the
  highest success rate and survival rounds and the *least* bankruptcy, but pays for it with a
  large "exit_candidate" share (falls behind technically while spending cautiously); `adaptive`
  balances technical currency against funding risk, and `cost_optimal` reaches "dominant_leader"
  most often but with the lowest success rate and highest volatility. **There is no single
  best strategy — the outcome distribution across the 4 quadrants differs qualitatively by
  strategy**, which is itself the main finding of this stage.

## Future work (not run in this session)

- Dedicated focused factorial on `alpha` and `cost_curve_exponent` (H2/H3)
- Re-run Stage 2 at full replication count (~1,591/point) on the top design points only
- Extend `max_rounds`/`difficulty_cap` to see whether a "survivor" regime exists at all
