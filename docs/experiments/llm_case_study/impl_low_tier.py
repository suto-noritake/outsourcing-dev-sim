"""Implementation produced by the general-purpose sub-agent playing
Architect+Implementer, given the LOW-TIER (vague, "よしなに") Planner spec.
Verbatim output from the LLM experiment (see docs/experiments/004_llm_multiagent_case_study.md).
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any


# Assumptions used in this implementation:
# - Duplicate orders are removed when either:
#   1) the normalized order_id matches, or
#   2) the normalized business content matches (fallback / secondary check).
# - No currency conversion is performed; totals are aggregated per currency.
# - Cancelled/voided orders are excluded from net totals.
# - Returned/refunded orders are treated as negative adjustments to net totals.
# - Unknown statuses are treated as active/effective orders.
# - Missing customer_id is grouped under "__unknown_customer__".


_KEY_ALIASES = {
    "order_id": {"order_id", "order_no", "order_number", "id"},
    "customer_id": {"customer_id", "customer", "customer_no", "customer_number", "client_id"},
    "amount": {"amount", "total", "total_amount", "order_amount", "subtotal"},
    "currency": {"currency", "currency_code", "ccy"},
    "status": {"status", "order_status", "state"},
}

_ALIAS_TO_CANONICAL: dict[str, str] = {}
for canonical_name, aliases in _KEY_ALIASES.items():
    for alias in aliases:
        _ALIAS_TO_CANONICAL["".join(ch if ch.isalnum() else "_" for ch in alias).strip("_").lower()] = canonical_name

_CANCELLED_STATUSES = {
    "cancelled", "canceled", "void", "voided", "rejected", "deleted",
}
_NEGATIVE_STATUSES = {
    "returned", "return", "refunded", "refund", "chargeback",
}
_IGNORED_STATUSES = {
    "draft", "cart", "quote", "test",
}
_AMOUNT_QUANT = Decimal("0.01")


def _normalize_key(key: Any) -> str:
    return "".join(ch if ch.isalnum() else "_" for ch in str(key)).strip("_").lower()


def _normalize_text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def _normalize_status(value: Any) -> str:
    return _normalize_text(value, default="completed").lower()


def _normalize_amount(value: Any) -> Decimal:
    if value is None or value == "":
        return Decimal("0.00")
    if isinstance(value, bool):
        return Decimal("0.00")
    try:
        return Decimal(str(value)).quantize(_AMOUNT_QUANT, rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError, TypeError):
        return Decimal("0.00")


def _freeze(value: Any) -> Any:
    if isinstance(value, dict):
        return tuple(sorted((_normalize_key(k), _freeze(v)) for k, v in value.items()))
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(v) for v in value)
    if isinstance(value, set):
        return tuple(sorted(_freeze(v) for v in value))
    if isinstance(value, Decimal):
        return str(value.quantize(_AMOUNT_QUANT, rounding=ROUND_HALF_UP))
    return value


def _classify_status(status: str) -> str:
    if status in _CANCELLED_STATUSES:
        return "cancelled"
    if status in _NEGATIVE_STATUSES:
        return "reversal"
    if status in _IGNORED_STATUSES:
        return "ignored"
    return "active"


def _build_normalized_order(record: dict[str, Any]) -> dict[str, Any]:
    normalized_raw = {_normalize_key(k): v for k, v in record.items()}

    def pick(canonical_name: str, default: Any = None) -> Any:
        for alias in _KEY_ALIASES[canonical_name]:
            alias_key = _normalize_key(alias)
            if alias_key in normalized_raw:
                return normalized_raw[alias_key]
        return default

    extras: dict[str, Any] = {}
    for raw_key, raw_value in record.items():
        normalized_key = _normalize_key(raw_key)
        if normalized_key not in _ALIAS_TO_CANONICAL:
            extras[normalized_key] = _freeze(raw_value)

    normalized = {
        "order_id": _normalize_text(pick("order_id")),
        "customer_id": _normalize_text(pick("customer_id"), default="__unknown_customer__"),
        "amount": _normalize_amount(pick("amount")),
        "currency": _normalize_text(pick("currency"), default="JPY").upper(),
        "status": _normalize_status(pick("status")),
        "extras": extras,
    }
    return normalized


def _build_signature(normalized_order: dict[str, Any]) -> tuple[Any, ...]:
    return (
        normalized_order["customer_id"],
        str(normalized_order["amount"]),
        normalized_order["currency"],
        normalized_order["status"],
        tuple(sorted(normalized_order["extras"].items())),
    )


def _new_summary() -> dict[str, Any]:
    return {
        "input_record_count": 0,
        "unique_order_count": 0,
        "effective_order_count": 0,
        "cancelled_order_count": 0,
        "reversal_order_count": 0,
        "ignored_order_count": 0,
        "duplicate_count": 0,
        "invalid_record_count": 0,
        "status_breakdown": {},
        "currency_totals": {},
    }


def _increment_status(summary: dict[str, Any], status: str) -> None:
    summary["status_breakdown"][status] = summary["status_breakdown"].get(status, 0) + 1


def _currency_bucket(summary: dict[str, Any], currency: str) -> dict[str, Decimal]:
    if currency not in summary["currency_totals"]:
        summary["currency_totals"][currency] = {
            "gross_amount": Decimal("0.00"),
            "reversal_amount": Decimal("0.00"),
            "cancelled_amount": Decimal("0.00"),
            "net_amount": Decimal("0.00"),
        }
    return summary["currency_totals"][currency]


def _apply_unique_order(summary: dict[str, Any], normalized_order: dict[str, Any]) -> None:
    amount = normalized_order["amount"]
    currency = normalized_order["currency"]
    status = normalized_order["status"]
    status_type = _classify_status(status)

    summary["unique_order_count"] += 1
    _increment_status(summary, status)
    bucket = _currency_bucket(summary, currency)

    if status_type == "active":
        summary["effective_order_count"] += 1
        bucket["gross_amount"] += amount
        bucket["net_amount"] += amount
    elif status_type == "reversal":
        summary["effective_order_count"] += 1
        summary["reversal_order_count"] += 1
        signed_amount = -abs(amount)
        bucket["reversal_amount"] += signed_amount
        bucket["net_amount"] += signed_amount
    elif status_type == "cancelled":
        summary["cancelled_order_count"] += 1
        bucket["cancelled_amount"] += amount
    else:
        summary["ignored_order_count"] += 1


def _to_float(value: Decimal) -> float:
    return float(value.quantize(_AMOUNT_QUANT, rounding=ROUND_HALF_UP))


def _finalize_summary(summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "input_record_count": summary["input_record_count"],
        "unique_order_count": summary["unique_order_count"],
        "effective_order_count": summary["effective_order_count"],
        "cancelled_order_count": summary["cancelled_order_count"],
        "reversal_order_count": summary["reversal_order_count"],
        "ignored_order_count": summary["ignored_order_count"],
        "duplicate_count": summary["duplicate_count"],
        "invalid_record_count": summary["invalid_record_count"],
        "status_breakdown": dict(sorted(summary["status_breakdown"].items())),
        "currency_totals": {
            currency: {
                "gross_amount": _to_float(amounts["gross_amount"]),
                "reversal_amount": _to_float(amounts["reversal_amount"]),
                "cancelled_amount": _to_float(amounts["cancelled_amount"]),
                "net_amount": _to_float(amounts["net_amount"]),
            }
            for currency, amounts in sorted(summary["currency_totals"].items())
        },
    }


def aggregate_orders(orders: list[dict]) -> dict:
    grand_total = _new_summary()
    per_customer_raw: dict[str, dict[str, Any]] = {}

    seen_order_ids: set[str] = set()
    seen_signatures: set[tuple[Any, ...]] = set()

    for raw_order in orders:
        grand_total["input_record_count"] += 1

        if not isinstance(raw_order, dict):
            grand_total["invalid_record_count"] += 1
            continue

        normalized_order = _build_normalized_order(raw_order)
        customer_id = normalized_order["customer_id"]

        if customer_id not in per_customer_raw:
            per_customer_raw[customer_id] = _new_summary()
        customer_summary = per_customer_raw[customer_id]
        customer_summary["input_record_count"] += 1

        order_id = normalized_order["order_id"]
        signature = _build_signature(normalized_order)

        is_duplicate = False
        if order_id and order_id in seen_order_ids:
            is_duplicate = True
        elif signature in seen_signatures:
            is_duplicate = True

        if is_duplicate:
            grand_total["duplicate_count"] += 1
            customer_summary["duplicate_count"] += 1
            continue

        if order_id:
            seen_order_ids.add(order_id)
        seen_signatures.add(signature)

        _apply_unique_order(grand_total, normalized_order)
        _apply_unique_order(customer_summary, normalized_order)

    return {
        "per_customer": {
            customer_id: _finalize_summary(summary)
            for customer_id, summary in sorted(per_customer_raw.items())
        },
        "grand_total": _finalize_summary(grand_total),
    }
