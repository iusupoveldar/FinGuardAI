"""Train and evaluate the Phase 1 transaction model.

Run from the repository root:
    python -m ml.train
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, precision_score, recall_score

from ml.features import FEATURE_COLUMNS, build_transaction_features
from ml.risk_model import (
    RiskModelArtifact,
    aggregate_customer_priority,
    build_pipeline,
    rule_benchmark,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TRANSACTIONS = ROOT / "backend/data_gen/data/raw/transactions.csv"
DEFAULT_ACCOUNTS = ROOT / "backend/data_gen/data/raw/accounts.csv"
DEFAULT_ARTIFACT = ROOT / "ml/artifacts/risk_model.joblib"
DEFAULT_METRICS = ROOT / "ml/artifacts/metrics.json"


def time_split_masks(steps: pd.Series) -> tuple[pd.Series, pd.Series, pd.Series]:
    unique_steps = np.sort(steps.unique())
    if len(unique_steps) < 5:
        raise ValueError("at least five unique simulation steps are required")
    train_end = max(1, int(len(unique_steps) * 0.60))
    validation_end = max(train_end + 1, int(len(unique_steps) * 0.80))
    validation_end = min(validation_end, len(unique_steps) - 1)
    train_steps = set(unique_steps[:train_end])
    validation_steps = set(unique_steps[train_end:validation_end])
    test_steps = set(unique_steps[validation_end:])
    return (
        steps.isin(train_steps),
        steps.isin(validation_steps),
        steps.isin(test_steps),
    )


def _check_labels(labels: pd.Series, split_name: str) -> None:
    if labels.nunique() < 2:
        raise ValueError(f"{split_name} must contain both positive and negative labels")


def _metrics(labels: pd.Series, scores: np.ndarray, threshold: float) -> dict[str, float]:
    predictions = scores >= threshold
    return {
        "pr_auc": float(average_precision_score(labels, scores)),
        "precision": float(precision_score(labels, predictions, zero_division=0)),
        "recall": float(recall_score(labels, predictions, zero_division=0)),
        "false_positives_per_1000": float(
            1_000 * np.sum(predictions & ~labels.to_numpy(dtype=bool)) / len(labels)
        ),
    }


def _validation_customer_priorities(
    validation_features: pd.DataFrame,
    probabilities: np.ndarray,
    transactions: pd.DataFrame,
    accounts: pd.DataFrame,
) -> np.ndarray:
    """Mirror inference aggregation to configure customer queue thresholds."""

    tx = transactions.copy()
    tx.columns = [column.lower() for column in tx.columns]
    tx = tx.rename(columns={"timestamp": "simulation_step"}).set_index("tx_id")
    account_frame = accounts.copy()
    account_frame.columns = [column.lower() for column in account_frame.columns]
    account_customer = account_frame.set_index("account_id")["customer_id"].to_dict()

    scored = validation_features.assign(
        probability=probabilities,
        rule_score=rule_benchmark(validation_features),
    )
    cutoff = int(scored["simulation_step"].max())
    scored = scored.loc[scored["simulation_step"] >= cutoff - 30]
    customer_rows: dict[str, list[int]] = {}
    for tx_id in scored.index:
        transaction = tx.loc[tx_id]
        for customer_id in {
            str(account_customer[int(transaction["sender_account_id"])]),
            str(account_customer[int(transaction["receiver_account_id"])]),
        }:
            customer_rows.setdefault(customer_id, []).append(int(tx_id))

    return np.asarray(
        [
            aggregate_customer_priority(
                scored.loc[tx_ids, "probability"], scored.loc[tx_ids, "rule_score"]
            )
            for tx_ids in customer_rows.values()
        ],
        dtype=float,
    )


def train(
    transactions: pd.DataFrame,
    accounts: pd.DataFrame,
    *,
    random_state: int = 42,
    review_rate: float = 0.01,
) -> tuple[RiskModelArtifact, dict[str, object]]:
    """Train with natural validation/test ratios and class-weighted fitting."""

    normalized_columns = {column.lower(): column for column in transactions.columns}
    label_column = normalized_columns.get("is_fraud")
    if label_column is None:
        raise ValueError("training transactions require a separate is_fraud target")
    labels = transactions.set_index(normalized_columns["tx_id"])[label_column].astype(bool)
    inference_transactions = transactions.drop(columns=[label_column])
    # The raw simulator alert identifier is label-derived and is never passed on.
    alert_column = normalized_columns.get("alert_id")
    if alert_column and alert_column in inference_transactions:
        inference_transactions = inference_transactions.drop(columns=[alert_column])
    account_columns = {
        column.lower(): column for column in accounts.columns
    }
    inference_accounts = accounts.drop(
        columns=[
            original
            for restricted in ("is_fraud",)
            if (original := account_columns.get(restricted)) is not None
        ]
    )

    features = build_transaction_features(inference_transactions, inference_accounts)
    labels = labels.reindex(features.index)
    train_mask, validation_mask, test_mask = time_split_masks(
        features["simulation_step"]
    )
    splits = {
        "train": (features.loc[train_mask], labels.loc[train_mask]),
        "validation": (features.loc[validation_mask], labels.loc[validation_mask]),
        "test": (features.loc[test_mask], labels.loc[test_mask]),
    }
    for name, (_, split_labels) in splits.items():
        _check_labels(split_labels, name)

    pipeline = build_pipeline(random_state=random_state)
    pipeline.fit(splits["train"][0][FEATURE_COLUMNS], splits["train"][1])
    validation_probabilities = pipeline.predict_proba(
        splits["validation"][0][FEATURE_COLUMNS]
    )[:, 1]

    if not 0 < review_rate < 0.5:
        raise ValueError("review_rate must be between 0 and 0.5")
    transaction_high_threshold = float(
        np.quantile(validation_probabilities, 1 - review_rate)
    )
    customer_priorities = _validation_customer_priorities(
        splits["validation"][0],
        validation_probabilities,
        inference_transactions,
        inference_accounts,
    )
    if not customer_priorities.size:
        raise ValueError("validation split produced no customer priority scores")
    customer_high_threshold = float(
        np.quantile(customer_priorities, 1 - review_rate)
    )
    customer_medium_threshold = float(
        np.quantile(customer_priorities, 1 - min(review_rate * 5, 0.25))
    )
    transaction_medium_threshold = float(
        np.quantile(validation_probabilities, 1 - min(review_rate * 5, 0.25))
    )
    artifact = RiskModelArtifact(
        pipeline=pipeline,
        medium_threshold=customer_medium_threshold,
        high_threshold=customer_high_threshold,
    )

    metrics: dict[str, object] = {
        "split_steps": {
            name: {
                "minimum": int(frame["simulation_step"].min()),
                "maximum": int(frame["simulation_step"].max()),
                "rows": len(frame),
                "positive_labels": int(split_labels.sum()),
            }
            for name, (frame, split_labels) in splits.items()
        },
        "thresholds": {
            "transaction_medium": transaction_medium_threshold,
            "transaction_high": transaction_high_threshold,
            "customer_medium": customer_medium_threshold,
            "customer_high": customer_high_threshold,
        },
        "logistic_regression": {},
        "rule_benchmark": {},
    }
    for name in ("validation", "test"):
        frame, split_labels = splits[name]
        probabilities = artifact.predict_probability(frame)
        metrics["logistic_regression"][name] = _metrics(  # type: ignore[index]
            split_labels, probabilities, transaction_high_threshold
        )
        metrics["rule_benchmark"][name] = _metrics(  # type: ignore[index]
            split_labels, rule_benchmark(frame), 0.65
        )
    return artifact, metrics


def main() -> None:
    parser = argparse.ArgumentParser(description="Train FinGuardAI risk scoring")
    parser.add_argument("--transactions", type=Path, default=DEFAULT_TRANSACTIONS)
    parser.add_argument("--accounts", type=Path, default=DEFAULT_ACCOUNTS)
    parser.add_argument("--artifact", type=Path, default=DEFAULT_ARTIFACT)
    parser.add_argument("--metrics", type=Path, default=DEFAULT_METRICS)
    parser.add_argument("--review-rate", type=float, default=0.01)
    parser.add_argument(
        "--max-rows",
        type=int,
        help="development-only row limit; preserve chronological CSV order",
    )
    args = parser.parse_args()

    transactions = pd.read_csv(args.transactions, nrows=args.max_rows)
    accounts = pd.read_csv(args.accounts)
    artifact, metrics = train(
        transactions, accounts, review_rate=args.review_rate
    )
    args.artifact.parent.mkdir(parents=True, exist_ok=True)
    args.metrics.parent.mkdir(parents=True, exist_ok=True)
    artifact.save(str(args.artifact))
    args.metrics.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
