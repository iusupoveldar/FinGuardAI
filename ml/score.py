"""Batch-score transactions and persist versioned customer risk snapshots.

Run from the repository root after training:
    python -m ml.score
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from pathlib import Path
import sys

import pandas as pd
from sqlalchemy import select

from ml.features import build_transaction_features
from ml.risk_model import (
    RiskModelArtifact,
    aggregate_customer_priority,
    rule_benchmark,
)


ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

DEFAULT_ARTIFACT = ROOT / "ml/artifacts/risk_model.joblib"


def _reasons(row: pd.Series) -> tuple[list[str], list[str]]:
    facts: list[str] = []
    patterns: list[str] = []
    if row["sender_count_1_vs_30_baseline"] >= 3:
        facts.append(
            f"Short-window outgoing count was {row['sender_out_count_1']:.0f}, "
            f"{row['sender_count_1_vs_30_baseline']:.1f} times its 30-step daily baseline."
        )
        patterns.append("rapid outgoing transfer velocity")
    if row["amount_vs_sender_median_30"] >= 3:
        facts.append(
            f"Amount was {row['amount_vs_sender_median_30']:.1f} times the sender's "
            "30-step historical median."
        )
        patterns.append("sudden increase in transaction value")
    if row["cross_border_account"]:
        facts.append("Sender and receiver accounts have different recorded countries.")
        patterns.append("cross-border account activity")
    if row["is_new_counterparty"]:
        facts.append("Receiver was a new external counterparty for the sender customer.")
        patterns.append("new counterparty")
    if row["pair_reverse_count_30"]:
        facts.append(
            f"The account pair had {row['pair_reverse_count_30']:.0f} reverse-direction "
            "transactions in the prior 30 steps."
        )
        patterns.append("back-and-forth transfers")
    if row["insufficient_history"]:
        facts.append("Sender had fewer than five prior transactions; baseline confidence is low.")
    return facts, patterns


def build_customer_snapshots(
    transactions: pd.DataFrame,
    accounts: pd.DataFrame,
    artifact: RiskModelArtifact,
) -> list[dict[str, object]]:
    """Score each transaction, then aggregate recent results without volume inflation."""

    tx = transactions.copy()
    tx.columns = [column.lower() for column in tx.columns]
    tx = tx.rename(columns={"timestamp": "simulation_step"})
    account_frame = accounts.copy()
    account_frame.columns = [column.lower() for column in account_frame.columns]
    for restricted in ("is_fraud", "alert_id"):
        if restricted in tx:
            tx = tx.drop(columns=[restricted])
        if restricted in account_frame:
            account_frame = account_frame.drop(columns=[restricted])

    features = build_transaction_features(tx, account_frame)
    probabilities = artifact.predict_probability(features)
    features = features.assign(
        probability=probabilities,
        rule_score=rule_benchmark(features),
    )
    cutoff = int(features["simulation_step"].max())
    recent_ids = features.index[features["simulation_step"] >= cutoff - 30]
    recent = features.loc[recent_ids]

    tx_by_id = tx.set_index("tx_id")
    account_customer = account_frame.set_index("account_id")["customer_id"].to_dict()
    customer_rows: dict[str, list[int]] = defaultdict(list)
    for tx_id in recent.index:
        transaction = tx_by_id.loc[tx_id]
        customers = {
            str(account_customer[int(transaction["sender_account_id"])]),
            str(account_customer[int(transaction["receiver_account_id"])]),
        }
        for customer_id in customers:
            customer_rows[customer_id].append(int(tx_id))

    snapshots: list[dict[str, object]] = []
    for customer_id, tx_ids in customer_rows.items():
        customer_results = recent.loc[tx_ids].sort_values(
            "probability", ascending=False
        )
        top = customer_results.head(3)
        priority = aggregate_customer_priority(
            customer_results["probability"], customer_results["rule_score"]
        )
        notable_transactions: list[dict[str, object]] = []
        all_facts: list[str] = []
        all_patterns: list[str] = []
        for tx_id, row in top.iterrows():
            facts, patterns = _reasons(row)
            all_facts.extend(facts)
            all_patterns.extend(patterns)
            notable_transactions.append(
                {
                    "tx_id": int(tx_id),
                    "probability": round(float(row["probability"]), 6),
                    "simulation_step": int(row["simulation_step"]),
                    "facts": facts,
                }
            )
        snapshots.append(
            {
                "customer_id": customer_id,
                "score": round(max(0.0, min(100.0, priority * 100)), 2),
                "risk_band": artifact.band(priority),
                "data_cutoff_step": cutoff,
                "model_version": artifact.model_version,
                "feature_version": artifact.feature_version,
                "evidence": {
                    "score_type": "operational priority, not probability of guilt",
                    "window": "last 30 simulation steps",
                    "top_transactions": notable_transactions,
                    "top_factors": list(dict.fromkeys(all_facts))[:8],
                    "patterns": list(dict.fromkeys(all_patterns))[:8],
                },
            }
        )
    for customer_id in sorted(
        {str(value) for value in account_frame["customer_id"]}.difference(customer_rows)
    ):
        snapshots.append(
            {
                "customer_id": customer_id,
                "score": 0.0,
                "risk_band": "unscored",
                "data_cutoff_step": cutoff,
                "model_version": artifact.model_version,
                "feature_version": artifact.feature_version,
                "evidence": {
                    "score_type": "operational priority, not probability of guilt",
                    "window": "last 30 simulation steps",
                    "top_transactions": [],
                    "top_factors": [
                        "No transaction activity was available in the scoring window."
                    ],
                    "patterns": [],
                },
            }
        )
    return snapshots


def load_database_frames(engine) -> tuple[pd.DataFrame, pd.DataFrame]:
    transactions_query = """
        SELECT tx_id, sender_account_id, receiver_account_id, tx_type,
               tx_amount, simulation_step
        FROM transactions
        ORDER BY simulation_step, tx_id
    """
    accounts_query = """
        SELECT account_id, customer_id, init_balance, country, account_type
        FROM accounts
        ORDER BY account_id
    """
    with engine.connect() as connection:
        return (
            pd.read_sql_query(transactions_query, connection),
            pd.read_sql_query(accounts_query, connection),
        )


def persist_snapshots(session, snapshots: list[dict[str, object]]) -> int:
    from app.models.risk import RiskScore

    created = 0
    for snapshot in snapshots:
        existing = session.scalar(
            select(RiskScore).where(
                RiskScore.customer_id == snapshot["customer_id"],
                RiskScore.data_cutoff_step == snapshot["data_cutoff_step"],
                RiskScore.model_version == snapshot["model_version"],
                RiskScore.feature_version == snapshot["feature_version"],
            )
        )
        if existing is None:
            session.add(RiskScore(**snapshot))
            created += 1
        else:
            # Refreshing the same identity handles late rows at/before the
            # cutoff without creating duplicate snapshots.
            existing.score = snapshot["score"]
            existing.risk_band = snapshot["risk_band"]
            existing.evidence = snapshot["evidence"]
    session.commit()
    return created


def main() -> None:
    parser = argparse.ArgumentParser(description="Persist current customer risk scores")
    parser.add_argument("--artifact", type=Path, default=DEFAULT_ARTIFACT)
    args = parser.parse_args()

    try:
        from app.database.connection import SessionLocal, engine
    except ModuleNotFoundError as exc:
        if exc.name == "psycopg":
            parser.error(
                "PostgreSQL driver 'psycopg' is not installed for this Python "
                "interpreter. Activate the backend virtual environment and run "
                "'python -m pip install -r backend/requirements.txt'."
            )
        raise

    try:
        artifact = RiskModelArtifact.load(str(args.artifact))
    except (FileNotFoundError, ValueError) as exc:
        parser.error(f"Cannot load risk model artifact: {exc}")
    transactions, accounts = load_database_frames(engine)
    snapshots = build_customer_snapshots(transactions, accounts, artifact)
    with SessionLocal() as session:
        created = persist_snapshots(session, snapshots)
    print(
        f"Created {created} new customer risk snapshots; "
        "existing snapshot identities were refreshed."
    )


if __name__ == "__main__":
    main()
