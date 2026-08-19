# Experiment 002: Stage 1 — Morris screening design

**Script**: `scripts/run_screening.py --n-trajectories 10 --n-seeds 50`
**Design**: Morris elementary-effects sampling (`SALib`), 12 factors, 4 levels,
10 trajectories per strategy (conservative / cost_optimal / adaptive) →
130 design points per strategy × 50 Monte Carlo seeds each = 6,500 games per
strategy (19,500 games total).

Full results: `results/screening_morris.csv` (not committed — regenerate via the command above;
see `.gitignore`).

## Ranking (mean |μ*| across the 3 strategies)

| parameter | μ* on success_rate | μ* on survival_rounds |
|---|---|---|
| max_consecutive_failures | 0.148 | 10.72 |
| beta | 0.144 | 4.43 |
| cost_curve_exponent | 0.125 | 4.43 |
| difficulty_0 | 0.111 | 5.74 |
| alpha | 0.095 | 5.86 |
| gamma | 0.090 | 14.63 |
| k1 | 0.079 | 18.27 |
| lam | 0.067 | 7.67 |
| sigma_noise | 0.062 | 8.08 |
| r_min | 0.052 | 1.96 |
| funds_0 | 0.044 | 1.23 |
| partial_pay | 0.034 | 1.09 |

## Interpretation & Stage 2 factor selection

- On **success_rate**, the top factors are `max_consecutive_failures`, `beta`
  (success-probability sensitivity), `cost_curve_exponent`, `difficulty_0`, `alpha`.
- On **survival_rounds**, the top factors are `k1` (base credit cost), `gamma`
  (escalation rate), `max_consecutive_failures`, `sigma_noise`, `alpha`.
- `funds_0` and `partial_pay` rank low on both metrics in this screening range — candidates to
  fix at baseline in Stage 2 rather than sweep further.
- For Stage 2 we selected the union of the consistently high-ranking factors across both metrics:
  **`max_consecutive_failures`, `beta`, `k1`, `gamma`** (4 factors), keeping `alpha` as a secondary
  factor of theoretical interest (H3) for a future extended run, and holding all other structural/
  environment parameters at baseline.
