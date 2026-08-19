"""Hidden 'true client intent' acceptance test for the order-aggregation
case study (Phase 4 LLM multi-agent experiment). This test suite represents
requirements that were in the Visionary's head but NEVER shown to the
Planner/Bid Manager/Implementer agents — only the (high- or low-tier)
Planner's own spec was given to them. It is run here, after the fact, to
measure whether spec ambiguity caused the delivered implementation to
diverge from true intent (see docs/experiments/004_llm_multiagent_case_study.md).

True intent (author's own specification, not disclosed to any agent):
- aggregate_orders(orders) -> {"per_customer": {cust: {currency: total}},
                                "grand_total": {currency: total}}
- Dedupe by order_id: if the same order_id appears more than once with
  different content, keep the record with the latest `updated_at`.
- Only orders with status in {confirmed, shipped, completed} count toward
  totals. `new`, `cancelled`, `returned` must be excluded entirely (NOT
  netted as negative amounts).
- Round to 2 decimal places using standard rounding.
"""
import importlib.util
import pathlib

import pytest

HERE = pathlib.Path(__file__).parent


def _load(module_name: str, file_name: str):
    spec = importlib.util.spec_from_file_location(module_name, HERE / file_name)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.aggregate_orders


ORDERS = [
    {"order_id": "A1", "customer_id": "cust1", "amount": 100.0, "currency": "JPY", "status": "completed"},
    {"order_id": "A1", "customer_id": "cust1", "amount": 100.0, "currency": "JPY", "status": "completed"},  # exact dup
    {"order_id": "A2", "customer_id": "cust1", "amount": 50.5, "currency": "JPY", "status": "confirmed"},
    {
        "order_id": "A2",
        "customer_id": "cust1",
        "amount": 75.25,
        "currency": "JPY",
        "status": "shipped",
        "updated_at": "2024-01-02T00:00:00",
    },  # updated version of A2, should win (no updated_at on the first -> latest wins)
    {"order_id": "A3", "customer_id": "cust2", "amount": 30.0, "currency": "USD", "status": "new"},  # excluded
    {"order_id": "A4", "customer_id": "cust2", "amount": 40.0, "currency": "USD", "status": "cancelled"},  # excluded
    {"order_id": "A5", "customer_id": "cust2", "amount": 60.0, "currency": "USD", "status": "returned"},  # excluded
    {"order_id": "A6", "customer_id": "cust2", "amount": 20.005, "currency": "USD", "status": "completed"},  # rounding
]

EXPECTED_PER_CUSTOMER = {
    "cust1": {"JPY": 175.25},
    "cust2": {"USD": 20.01},  # Decimal("20.005") half-up rounds to 20.01 (float round() would mis-round to 20.0)
}
EXPECTED_GRAND_TOTAL = {
    "JPY": 175.25,
    "USD": 20.01,
}


@pytest.fixture(params=["impl_high_tier", "impl_low_tier"])
def aggregate_orders(request):
    return _load(request.param, f"{request.param}.py")


def test_output_has_expected_top_level_keys(aggregate_orders):
    result = aggregate_orders(ORDERS)
    assert "per_customer" in result
    assert "grand_total" in result


def test_excludes_new_cancelled_returned_entirely(aggregate_orders):
    result = aggregate_orders(ORDERS)
    grand_total = result["grand_total"]
    # True intent: cancelled/returned must not appear as negative adjustments
    # or otherwise affect totals -- they should simply not be counted.
    assert grand_total == EXPECTED_GRAND_TOTAL, (
        f"grand_total mismatch: got {grand_total}, expected {EXPECTED_GRAND_TOTAL} "
        "(hidden requirement: exclude new/cancelled/returned entirely, no netting)"
    )


def test_per_customer_matches_true_intent(aggregate_orders):
    result = aggregate_orders(ORDERS)
    assert result["per_customer"] == EXPECTED_PER_CUSTOMER


def test_dedup_by_order_id_keeps_latest_update(aggregate_orders):
    result = aggregate_orders(ORDERS)
    # A2 should be counted once at 75.25 (the updated version), not twice
    # and not at the stale 50.5 value.
    cust1_jpy = result["per_customer"].get("cust1", {}).get("JPY")
    assert cust1_jpy == 175.25
