"""Implementation produced by the general-purpose sub-agent playing
Architect+Implementer, given the HIGH-TIER (clear, detailed) Planner spec.
Verbatim output from the LLM experiment (see docs/experiments/004_llm_multiagent_case_study.md).
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

_INCLUDED_STATUSES = {"confirmed", "shipped", "completed"}
_ALLOWED_STATUSES = {
    "new",
    "confirmed",
    "shipped",
    "completed",
    "cancelled",
    "returned",
}
_CENTS = Decimal("0.01")


def _quantize_amount(value: Any) -> Decimal:
    try:
        amount = Decimal(str(value))
    except Exception as exc:  # pragma: no cover
        raise ValueError(f"Invalid amount: {value!r}") from exc
    return amount.quantize(_CENTS, rounding=ROUND_HALF_UP)


def _parse_iso8601(value: Any) -> datetime | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Invalid updated_at: {value!r}")

    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"

    try:
        return datetime.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"Invalid updated_at: {value!r}") from exc


def _validate_record(order: dict[str, Any]) -> None:
    required_keys = {"order_id", "customer_id", "amount", "currency", "status"}
    missing = required_keys - order.keys()
    if missing:
        raise ValueError(f"Missing required keys: {sorted(missing)}")

    if not isinstance(order["order_id"], str) or not order["order_id"]:
        raise ValueError("order_id must be a non-empty string")
    if not isinstance(order["customer_id"], str) or not order["customer_id"]:
        raise ValueError("customer_id must be a non-empty string")
    if not isinstance(order["currency"], str) or not order["currency"]:
        raise ValueError("currency must be a non-empty string")
    if order["status"] not in _ALLOWED_STATUSES:
        raise ValueError(f"Invalid status: {order['status']!r}")


def _canonical_content(order: dict[str, Any], normalized_amount: Decimal) -> tuple[Any, ...]:
    return (
        order["customer_id"],
        normalized_amount,
        order["currency"],
        order["status"],
        order.get("updated_at"),
    )


def aggregate_orders(orders: list[dict]) -> dict:
    deduped: dict[str, dict[str, Any]] = {}

    for index, raw_order in enumerate(orders):
        if not isinstance(raw_order, dict):
            raise ValueError(f"Each order must be a dict: {raw_order!r}")

        _validate_record(raw_order)
        amount = _quantize_amount(raw_order["amount"])
        updated_at = _parse_iso8601(raw_order.get("updated_at"))

        candidate = {
            "order_id": raw_order["order_id"],
            "customer_id": raw_order["customer_id"],
            "amount": amount,
            "currency": raw_order["currency"],
            "status": raw_order["status"],
            "updated_at": raw_order.get("updated_at"),
            "_updated_at_dt": updated_at,
            "_received_index": index,
            "_content_key": _canonical_content(raw_order, amount),
        }

        order_id = candidate["order_id"]
        current = deduped.get(order_id)

        if current is None:
            deduped[order_id] = candidate
            continue

        if current["_content_key"] == candidate["_content_key"]:
            # 完全一致の再送は無視する
            continue

        # 内容不一致は更新として扱い、updated_at が新しい方を優先する。
        # updated_at が欠落している場合は受信順（入力順）をフォールバックに使う。
        current_dt = current["_updated_at_dt"]
        candidate_dt = candidate["_updated_at_dt"]

        if current_dt is not None and candidate_dt is not None:
            if candidate_dt > current_dt or (
                candidate_dt == current_dt and candidate["_received_index"] > current["_received_index"]
            ):
                deduped[order_id] = candidate
        elif current_dt is None and candidate_dt is None:
            if candidate["_received_index"] > current["_received_index"]:
                deduped[order_id] = candidate
        elif current_dt is None and candidate_dt is not None:
            deduped[order_id] = candidate
        else:
            # current_dt is not None and candidate_dt is None:
            # 明示的な更新日時があるレコードを優先しつつ、両方欠落時のみ受信順で解決する。
            pass

    per_customer_decimals: dict[str, dict[str, Decimal]] = {}

    for order in deduped.values():
        if order["status"] not in _INCLUDED_STATUSES:
            continue

        customer_id = order["customer_id"]
        currency = order["currency"]
        amount = order["amount"]

        customer_totals = per_customer_decimals.setdefault(customer_id, {})
        customer_totals[currency] = customer_totals.get(currency, Decimal("0")) + amount

    # 顧客別集計を先に確定し、その結果から全体集計を作ることで整合性を保証する。
    per_customer: dict[str, dict[str, float]] = {}
    grand_total_decimals: dict[str, Decimal] = {}

    for customer_id, totals in per_customer_decimals.items():
        per_customer[customer_id] = {}
        for currency, total in totals.items():
            rounded_total = total.quantize(_CENTS, rounding=ROUND_HALF_UP)
            per_customer[customer_id][currency] = float(rounded_total)
            grand_total_decimals[currency] = grand_total_decimals.get(currency, Decimal("0")) + rounded_total

    grand_total = {
        currency: float(total.quantize(_CENTS, rounding=ROUND_HALF_UP))
        for currency, total in grand_total_decimals.items()
    }

    return {
        "per_customer": per_customer,
        "grand_total": grand_total,
    }
