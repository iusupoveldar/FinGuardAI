"""Time-safe transaction feature construction.

All historical features are computed from transactions at strictly smaller
simulation steps. Rows sharing a step are therefore unable to observe one
another, irrespective of their input order.
"""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from math import log1p
from typing import Iterable

import numpy as np
import pandas as pd


FEATURE_VERSION = "transaction_features_v1"
WINDOWS = (1, 7, 30)
MIN_HISTORY = 5
RATIO_CAP = 100.0

RESTRICTED_COLUMNS = {
    "is_fraud",
    "ground_truth_is_fraud",
    "alert_id",
    "alert_type",
    "investigation_outcome",
    "analyst_disposition",
}

NUMERIC_FEATURES = [
    "log_amount",
    "amount_to_initial_balance",
    "zero_initial_balance",
    "same_account",
    "same_customer",
    "cross_border_account",
    "insufficient_history",
    "steps_since_sender_activity",
    "is_new_counterparty",
    "sender_unique_counterparties_30",
    "receiver_unique_senders_30",
    "pair_reverse_count_30",
    "amount_vs_sender_median_30",
    "amount_robust_z_30",
    "sender_count_1_vs_30_baseline",
    "sender_value_1_vs_30_baseline",
]
for _window in WINDOWS:
    NUMERIC_FEATURES.extend(
        [
            f"sender_out_count_{_window}",
            f"sender_out_value_{_window}",
            f"sender_in_count_{_window}",
            f"sender_in_value_{_window}",
            f"sender_avg_amount_{_window}",
            f"sender_max_amount_{_window}",
            f"sender_out_in_ratio_{_window}",
            f"sender_cross_border_count_{_window}",
            f"sender_cross_border_pct_{_window}",
            f"sender_type_frequency_{_window}",
        ]
    )

CATEGORICAL_FEATURES = ["tx_type", "sender_account_type"]
FEATURE_COLUMNS = NUMERIC_FEATURES + CATEGORICAL_FEATURES


@dataclass(frozen=True)
class _Event:
    step: int
    amount: float
    direction: str
    counterparty: int
    tx_type: str
    cross_border: bool


def _canonicalize(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    result.columns = [str(column).strip().lower() for column in result.columns]
    return result.rename(columns={"timestamp": "simulation_step"})


def _assert_no_restricted_columns(frame: pd.DataFrame, name: str) -> None:
    found = RESTRICTED_COLUMNS.intersection(frame.columns)
    if found:
        raise ValueError(
            f"{name} contains restricted feature columns: {sorted(found)}"
        )


def _safe_ratio(numerator: float, denominator: float, cap: float = RATIO_CAP) -> float:
    if denominator <= 0 or not np.isfinite(denominator):
        return 0.0
    return float(np.clip(numerator / denominator, 0.0, cap))


def _window_events(events: Iterable[_Event], cutoff: int, window: int) -> list[_Event]:
    lower_bound = cutoff - window
    return [event for event in events if event.step >= lower_bound]


def _history_features(
    events: deque[_Event], cutoff: int, current_type: str
) -> dict[str, float]:
    result: dict[str, float] = {}
    for window in WINDOWS:
        recent = _window_events(events, cutoff, window)
        outgoing = [event for event in recent if event.direction == "out"]
        incoming = [event for event in recent if event.direction == "in"]
        amounts = [event.amount for event in recent]
        out_value = sum(event.amount for event in outgoing)
        in_value = sum(event.amount for event in incoming)
        cross_border_count = sum(event.cross_border for event in recent)

        result.update(
            {
                f"sender_out_count_{window}": float(len(outgoing)),
                f"sender_out_value_{window}": float(out_value),
                f"sender_in_count_{window}": float(len(incoming)),
                f"sender_in_value_{window}": float(in_value),
                f"sender_avg_amount_{window}": float(np.mean(amounts)) if amounts else 0.0,
                f"sender_max_amount_{window}": max(amounts, default=0.0),
                f"sender_out_in_ratio_{window}": _safe_ratio(out_value, in_value),
                f"sender_cross_border_count_{window}": float(cross_border_count),
                f"sender_cross_border_pct_{window}": _safe_ratio(
                    float(cross_border_count), float(len(recent)), cap=1.0
                ),
                f"sender_type_frequency_{window}": _safe_ratio(
                    float(sum(event.tx_type == current_type for event in recent)),
                    float(len(recent)),
                    cap=1.0,
                ),
            }
        )
    return result


def build_transaction_features(
    transactions: pd.DataFrame,
    accounts: pd.DataFrame,
) -> pd.DataFrame:
    """Build features in input-row order using only strictly earlier steps.

    Labels and alert-derived data must be separated before calling this
    function. The returned index is the transaction ID.
    """

    tx = _canonicalize(transactions)
    account_frame = _canonicalize(accounts)
    _assert_no_restricted_columns(tx, "transactions")
    _assert_no_restricted_columns(account_frame, "accounts")

    required_tx = {
        "tx_id",
        "sender_account_id",
        "receiver_account_id",
        "tx_type",
        "tx_amount",
        "simulation_step",
    }
    required_accounts = {
        "account_id",
        "customer_id",
        "init_balance",
        "country",
        "account_type",
    }
    missing_tx = required_tx.difference(tx.columns)
    missing_accounts = required_accounts.difference(account_frame.columns)
    if missing_tx or missing_accounts:
        raise ValueError(
            f"missing transaction columns={sorted(missing_tx)}; "
            f"missing account columns={sorted(missing_accounts)}"
        )
    if tx["tx_id"].duplicated().any():
        raise ValueError("transaction IDs must be unique")
    if (tx["tx_amount"] < 0).any() or (tx["simulation_step"] < 0).any():
        raise ValueError("transaction amounts and simulation steps must be nonnegative")

    account_lookup = account_frame.set_index("account_id").to_dict("index")
    unknown_accounts = (
        set(tx["sender_account_id"]) | set(tx["receiver_account_id"])
    ).difference(account_lookup)
    if unknown_accounts:
        sample = sorted(unknown_accounts)[:5]
        raise ValueError(f"transactions reference unknown accounts: {sample}")

    tx = tx.assign(input_order=np.arange(len(tx))).sort_values(
        ["simulation_step", "tx_id"], kind="stable"
    )
    histories: dict[int, deque[_Event]] = defaultdict(deque)
    last_activity: dict[int, int] = {}
    seen_customer_counterparties: dict[str, set[str]] = defaultdict(set)
    rows: list[dict[str, float | str | int]] = []

    for step, same_step in tx.groupby("simulation_step", sort=True):
        step = int(step)
        # Calculate every row before mutating history: same-step isolation.
        for item in same_step.itertuples(index=False):
            sender_id = int(item.sender_account_id)
            receiver_id = int(item.receiver_account_id)
            sender = account_lookup[sender_id]
            receiver = account_lookup[receiver_id]
            sender_customer = str(sender["customer_id"])
            receiver_customer = str(receiver["customer_id"])
            amount = float(item.tx_amount)
            sender_events = histories[sender_id]
            recent_30 = _window_events(sender_events, step, 30)
            outgoing_30 = [event for event in recent_30 if event.direction == "out"]
            historic_amounts = np.asarray(
                [event.amount for event in recent_30], dtype=float
            )
            median = float(np.median(historic_amounts)) if historic_amounts.size else 0.0
            mad = (
                float(np.median(np.abs(historic_amounts - median)))
                if historic_amounts.size
                else 0.0
            )
            cross_border = str(sender["country"]) != str(receiver["country"])
            same_customer = sender_customer == receiver_customer
            initial_balance = float(sender["init_balance"])
            history = _history_features(sender_events, step, str(item.tx_type))

            unique_counterparties = {
                event.counterparty
                for event in outgoing_30
                if event.counterparty != sender_id
            }
            receiver_recent = _window_events(histories[receiver_id], step, 30)
            receiver_unique_senders = {
                event.counterparty
                for event in receiver_recent
                if event.direction == "in" and event.counterparty != receiver_id
            }
            reverse_pair_count = sum(
                event.direction == "in" and event.counterparty == receiver_id
                for event in recent_30
            )
            prior_external_pair = (
                receiver_customer in seen_customer_counterparties[sender_customer]
            )

            row: dict[str, float | str | int] = {
                "tx_id": int(item.tx_id),
                "simulation_step": step,
                "input_order": int(item.input_order),
                "log_amount": log1p(amount),
                "amount_to_initial_balance": _safe_ratio(amount, initial_balance),
                "zero_initial_balance": float(initial_balance == 0),
                "same_account": float(sender_id == receiver_id),
                "same_customer": float(same_customer),
                "cross_border_account": float(cross_border),
                "insufficient_history": float(len(sender_events) < MIN_HISTORY),
                "steps_since_sender_activity": (
                    float(step - last_activity[sender_id])
                    if sender_id in last_activity
                    else 31.0
                ),
                "is_new_counterparty": float(
                    not same_customer and sender_id != receiver_id and not prior_external_pair
                ),
                "sender_unique_counterparties_30": float(len(unique_counterparties)),
                "receiver_unique_senders_30": float(len(receiver_unique_senders)),
                "pair_reverse_count_30": float(reverse_pair_count),
                "amount_vs_sender_median_30": _safe_ratio(amount, median),
                "amount_robust_z_30": (
                    float(np.clip((amount - median) / (1.4826 * mad), -100.0, 100.0))
                    if mad > 0
                    else 0.0
                ),
                "sender_count_1_vs_30_baseline": _safe_ratio(
                    history["sender_out_count_1"],
                    history["sender_out_count_30"] / 30.0,
                ),
                "sender_value_1_vs_30_baseline": _safe_ratio(
                    history["sender_out_value_1"],
                    history["sender_out_value_30"] / 30.0,
                ),
                "tx_type": str(item.tx_type),
                "sender_account_type": str(sender["account_type"]),
                **history,
            }
            rows.append(row)

        for item in same_step.itertuples(index=False):
            sender_id = int(item.sender_account_id)
            receiver_id = int(item.receiver_account_id)
            amount = float(item.tx_amount)
            sender = account_lookup[sender_id]
            receiver = account_lookup[receiver_id]
            cross_border = str(sender["country"]) != str(receiver["country"])
            histories[sender_id].append(
                _Event(step, amount, "out", receiver_id, str(item.tx_type), cross_border)
            )
            if receiver_id != sender_id:
                histories[receiver_id].append(
                    _Event(step, amount, "in", sender_id, str(item.tx_type), cross_border)
                )
            last_activity[sender_id] = step
            last_activity[receiver_id] = step
            sender_customer = str(sender["customer_id"])
            receiver_customer = str(receiver["customer_id"])
            if sender_customer != receiver_customer:
                seen_customer_counterparties[sender_customer].add(receiver_customer)
                seen_customer_counterparties[receiver_customer].add(sender_customer)

        # Only 30-step history is used. Pruning keeps full-dataset memory bounded.
        lower_bound = step - 30
        touched = set(same_step["sender_account_id"]) | set(
            same_step["receiver_account_id"]
        )
        for account_id in touched:
            events = histories[int(account_id)]
            while events and events[0].step < lower_bound:
                events.popleft()

    result = pd.DataFrame(rows).sort_values("input_order", kind="stable")
    result = result.set_index("tx_id")
    return result[["simulation_step", *FEATURE_COLUMNS]]


def validate_feature_schema(frame: pd.DataFrame) -> None:
    """Fail closed if an artifact and feature frame disagree."""

    actual = [column for column in frame.columns if column != "simulation_step"]
    if actual != FEATURE_COLUMNS:
        raise ValueError(
            "feature schema mismatch; refusing to reorder or silently drop columns"
        )
