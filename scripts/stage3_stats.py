"""Stage 3: statistical analysis of Stage 2 focused-factorial results
(docs/experiment_design.md, Stage 3).

- Logistic regression on per-round success (binary outcome) -> odds ratios
- Cox proportional-hazards model on survival_rounds (right-censored at
  max_rounds, i.e. "contract still running") -> hazard ratios
- OLS/ANOVA on net_profit (continuous outcome), including strategy
  interaction terms
"""
from __future__ import annotations

import argparse

import numpy as np
import pandas as pd
import statsmodels.api as sm
import statsmodels.formula.api as smf
from lifelines import CoxPHFitter


def load(path: str) -> pd.DataFrame:
    if path.endswith(".parquet"):
        return pd.read_parquet(path)
    return pd.read_csv(path)


def main():
    ap = argparse.ArgumentParser(description="Stage 3 statistical analysis")
    ap.add_argument("--input", type=str, required=True)
    args = ap.parse_args()

    df = load(args.input)
    df["event"] = (df["end_reason"] != "max_rounds").astype(int)  # 1=bankrupt/terminated, 0=censored

    print("=" * 70)
    print("Logistic regression: success_rate ~ factors (per-run mean success used as proxy)")
    print("=" * 70)
    logit_df = df.copy()
    logit_df["strategy"] = pd.Categorical(
        logit_df["strategy"], categories=["cost_optimal", "conservative", "adaptive"]
    )
    # Use a quasi-binomial GLM on the run-level success_rate (bounded [0,1])
    model = smf.glm(
        formula="success_rate ~ C(strategy) + max_consecutive_failures + beta + k1 + gamma",
        data=logit_df,
        family=sm.families.Binomial(),
    ).fit()
    print(model.summary())
    print("\nOdds ratios (exp(coef)):")
    print(np.exp(model.params).to_string())

    print("\n" + "=" * 70)
    print("Cox proportional hazards: survival_rounds ~ factors (event=bankrupt/terminated)")
    print("=" * 70)
    cox_df = pd.get_dummies(
        df[["survival_rounds", "event", "strategy", "max_consecutive_failures", "beta", "k1", "gamma"]],
        columns=["strategy"],
        drop_first=True,
    )
    cox_df = cox_df.astype({c: float for c in cox_df.columns})
    cph = CoxPHFitter()
    cph.fit(cox_df, duration_col="survival_rounds", event_col="event")
    cph.print_summary()

    print("\n" + "=" * 70)
    print("OLS / ANOVA: net_profit ~ factors * strategy")
    print("=" * 70)
    ols_model = smf.ols(
        formula="net_profit ~ C(strategy) * (max_consecutive_failures + beta + k1 + gamma)",
        data=df,
    ).fit()
    print(ols_model.summary())


if __name__ == "__main__":
    main()
