# Experiment 001: Stage 0 — Pilot trial at baseline parameters

**Script**: `scripts/run_pilot.py --n 100`
**Params**: `SimParams()` defaults (strategy=adaptive), see `outsourcing_sim/params.py`
**Seed range**: 0–99

## Result

```json
{
  "n_pilot": 100,
  "mean_success_rate": 0.7905818797215857,
  "std_success_rate": 0.11948855192250599,
  "mean_survival_rounds": 17.69,
  "std_survival_rounds": 3.4777648691147136,
  "bankruptcy_rate": 0.9,
  "required_n_success_rate_ci": 1591
}
```

## Interpretation

- At baseline, the adaptive contractor strategy survives ~17-18 rounds on average before the
  game ends (bankruptcy or contract termination), with a ~79% mean per-round success rate.
- **Bankruptcy rate is very high (90%)** at these default economic parameters
  (`budget_c0`, `budget_c1`, `k1`, `cost_curve_exponent`). This is a useful early finding:
  under the current baseline calibration, financial exhaustion — not technical failure — is
  the dominant end-of-game reason, which is consistent with hypothesis **H1**
  (see `docs/experiment_design.md`).
- Achieving a tight ±2pt 95% CI on success_rate would require ~1591 replications per design
  point. Given the size of the Stage 1/2 designs, we accept a looser CI (`n=50–100` per point)
  for screening/focused runs and note this as a precision/compute trade-off — a production-scale
  study would re-run Stage 2 with the full `n≈1591` replication count on the top design points.
