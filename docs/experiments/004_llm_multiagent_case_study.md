# Experiment 004: LLM multi-agent case study — spec ambiguity propagation

Case study implementing the org-structure design in `docs/llm_experiments.md`, using real
sub-agents (this session's `task` tool, `general-purpose` agent) for each role. Coding task:
"注文集計モジュール" (order aggregation: dedupe, filter by status, sum per customer/currency).

## Roles run as real agents

| Role | Company | Condition |
|---|---|---|
| Visionary | A | scripted one-line "夢" (not a live agent call, to keep scope small — see Limitations) |
| Planner | A | **2 live agent runs**: high-tier (thorough, edge-case-aware) vs low-tier (vague, "よしなに") |
| Bid/Go-No-Go Manager | B | live agent run per condition, reads only the Planner's spec |
| Architect + Implementer (combined) | B | live agent run per condition, reads spec + Bid Manager notes, writes `aggregate_orders()` |

Full transcripts are the prompts/outputs used to produce the specs and implementations in this
directory (`impl_high_tier.py`, `impl_low_tier.py`). A hidden acceptance test
(`test_hidden_acceptance.py`) encodes the "true client intent" that was **never shown to any
agent** — only the Planner's own (high/low tier) spec was passed downstream, exactly as the
Phase 4 design intends to test information asymmetry.

## Hidden true intent (author-only, not shown to agents)

- Dedupe by `order_id`; if content differs across duplicates, keep the one with the latest
  `updated_at`.
- Only `confirmed / shipped / completed` count toward totals — `new`, `cancelled`, `returned`
  must be **excluded entirely** (not netted as negative amounts).
- Round to 2 decimals (half-up); output shape: `{"per_customer": {cust: {currency: total}},
  "grand_total": {currency: total}}`.

## Result: `pytest docs/experiments/llm_case_study/test_hidden_acceptance.py`

| Implementation | Tests passed | Tests failed |
|---|---|---|
| `impl_high_tier.py` (from the detailed spec) | 4 / 4 | 0 |
| `impl_low_tier.py` (from the vague "よしなに" spec) | 1 / 4 | 3 |

### What went wrong under the low-tier (ambiguous) spec

1. **Output schema mismatch**: the vague spec never fixed the exact return shape, so the
   Implementer invented its own (richer but incompatible) nested schema
   (`{"grand_total": {"currency_totals": {...}}}` instead of the expected flat
   `{"grand_total": {currency: total}}`). Any downstream consumer built against the original
   intent would break immediately on integration — a pure **interface/contract failure**, not a
   business-logic bug.
2. **Wrong business decision on returns**: the low-tier Implementer *guessed* that "returned"
   orders should be netted as a negative adjustment to the total, whereas the true intent (and
   the high-tier spec, which explicitly enumerated `cancelled/returned` as "excluded from the
   normal total") was to exclude them entirely. This is exactly the "曖昧さ→見積り誤差→失敗" chain
   hypothesized in `docs/llm_experiments.md`.
3. **Dedup strategy diverged**: the low-tier Implementer deduped on **first-seen** record per
   `order_id` rather than **latest-updated**, because the vague spec never specified an update/
   supersede rule. The high-tier spec's explicit "更新日時が最新のレコードを採用" instruction was
   followed correctly by its Implementer.

### What the Bid Manager step revealed

Interestingly, **both** Bid Managers (high-tier-spec and low-tier-spec conditions) correctly
flagged duplicate-detection semantics, return/cancel handling, and rounding as open risks in
their written estimates — i.e. the *risk was visible at the estimation stage* even under the
vague spec. In this run, the downstream Implementer nonetheless proceeded to guess rather than
escalate back to the client, and the guesses did not match true intent. This suggests a concrete,
testable extension of the abstract ABM (per `docs/DESIGN.md` "将来拡張"): a **"assumption written
down but not confirmed" failure mode**, distinct from pure technical capability shortfall — i.e.
even a competent Bid Manager estimate does not protect against downstream fixed-price
implementation choosing the wrong assumption when the client never confirms it.

## Interpretation for the abstract model (Phase 1–3)

This single case study is illustrative, not statistically powered, but it gives a concrete,
measurable signal supporting the extension proposed in `docs/DESIGN.md`:

- Introduce a **spec completeness / ambiguity parameter** (driven by the Planner's model tier)
  that increases the variance (or bias) of the Bid Manager's effective difficulty estimate,
  which could be wired into the abstract model's `credit_cost` / `success_probability` noise
  terms (`sigma_noise`) or as a new multiplicative "hidden difficulty surprise" factor.
- The failure mode observed here (schema/contract mismatch under ambiguity) is not well captured
  by the current binary success/failure outcome — a future refinement could add a partial-credit
  "integration failure" outcome distinct from "did not run at all".

## Limitations of this session's run

- Single case study (n=1 coding task, n=2 conditions) — **not a statistically powered
  experiment**; it demonstrates the mechanism and the harness, not a generalizable effect size.
- The Visionary role was scripted rather than a live agent call, to keep the number of sub-agent
  calls small for this proof-of-concept; a full run should make every role a live agent.
- Only one model/agent configuration was used for all roles (this session's default
  `general-purpose` agent) rather than genuinely different model tiers per role — the "tier"
  manipulation was simulated via prompt instructions ("high-tier: thorough" vs "low-tier: vague
  and rushed") rather than by actually swapping the underlying model. A follow-up should assign
  literally different models (e.g. a smaller/faster model vs a larger one) to each role to more
  faithfully test the "モデルティアが仕様完成度を左右する" claim in `docs/llm_experiments.md`.
- No role-based credit/cost accounting was measured in this run (out of scope for this
  proof-of-concept); a fuller experiment should log real token usage per role and compare to the
  abstract model's `CreditCost` predictions for calibration.
