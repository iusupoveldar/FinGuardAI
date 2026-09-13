import pandas as pd
import pytest

from ml.features import FEATURE_COLUMNS
from ml.score import build_customer_snapshots
from ml.train import train


def test_training_uses_time_splits_and_versioned_schema() -> None:
    accounts = pd.DataFrame(
        [
            {"ACCOUNT_ID": 1, "CUSTOMER_ID": "C1", "INIT_BALANCE": 1000, "COUNTRY": "CA", "ACCOUNT_TYPE": "personal", "IS_FRAUD": False},
            {"ACCOUNT_ID": 2, "CUSTOMER_ID": "C2", "INIT_BALANCE": 1000, "COUNTRY": "US", "ACCOUNT_TYPE": "business", "IS_FRAUD": False},
            {"ACCOUNT_ID": 3, "CUSTOMER_ID": "C3", "INIT_BALANCE": 1000, "COUNTRY": "CA", "ACCOUNT_TYPE": "personal", "IS_FRAUD": False},
        ]
    )
    rows = []
    tx_id = 0
    for step in range(10):
        for fraud in (False, True):
            tx_id += 1
            rows.append(
                {
                    "TX_ID": tx_id,
                    "SENDER_ACCOUNT_ID": 1 if tx_id % 2 else 2,
                    "RECEIVER_ACCOUNT_ID": 2 if tx_id % 2 else 1,
                    "TX_TYPE": "WIRE" if fraud else "TRANSFER",
                    "TX_AMOUNT": 1000 if fraud else 10,
                    "TIMESTAMP": step,
                    "IS_FRAUD": fraud,
                    "ALERT_ID": tx_id if fraud else -1,
                }
            )
    artifact, metrics = train(pd.DataFrame(rows), accounts, review_rate=0.10)

    assert artifact.feature_columns == tuple(FEATURE_COLUMNS)
    assert metrics["split_steps"]["train"]["maximum"] < metrics["split_steps"]["validation"]["minimum"]
    assert metrics["split_steps"]["validation"]["maximum"] < metrics["split_steps"]["test"]["minimum"]
    assert 0 <= metrics["logistic_regression"]["test"]["pr_auc"] <= 1

    snapshots = build_customer_snapshots(pd.DataFrame(rows), accounts, artifact)
    unscored = next(item for item in snapshots if item["customer_id"] == "C3")
    assert unscored["risk_band"] == "unscored"
    assert unscored["score"] == 0
    assert any(item["customer_id"] == "C1" for item in snapshots)


def test_artifact_rejects_dependency_version_mismatch(tmp_path) -> None:
    from ml.risk_model import RiskModelArtifact, build_pipeline

    artifact = RiskModelArtifact(
        pipeline=build_pipeline(),
        medium_threshold=0.2,
        high_threshold=0.8,
        sklearn_version="incompatible-version",
    )
    path = tmp_path / "model.joblib"
    artifact.save(str(path))

    with pytest.raises(ValueError, match="retrain it with the active environment"):
        RiskModelArtifact.load(str(path))
