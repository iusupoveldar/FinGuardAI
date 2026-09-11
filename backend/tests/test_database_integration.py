import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from main import app


pytestmark = pytest.mark.skipif(
    not os.getenv("RUN_DATABASE_INTEGRATION"),
    reason="set RUN_DATABASE_INTEGRATION=1 for PostgreSQL integration tests",
)


EXPECTED_COUNTS = {
    "account_ground_truth": 10_000,
    "accounts": 10_000,
    "alert_transactions": 1_719,
    "alerts": 391,
    "customer_profiles": 10_000,
    "customers": 10_000,
    "transaction_ground_truth": 1_323_234,
    "transactions": 1_323_234,
}


def test_imported_counts_and_integrity() -> None:
    engine = create_engine(os.environ["DATABASE_URL"])
    with engine.connect() as connection:
        actual = {
            table: int(connection.scalar(text(f"SELECT count(*) FROM {table}")))
            for table in EXPECTED_COUNTS
        }
        assert actual == EXPECTED_COUNTS

        assert connection.scalar(
            text(
                """
                SELECT count(*) FROM transactions t
                LEFT JOIN accounts a ON a.account_id = t.sender_account_id
                WHERE a.account_id IS NULL
                """
            )
        ) == 0
        assert connection.scalar(
            text(
                """
                SELECT count(*) FROM alert_transactions atx
                LEFT JOIN transactions t USING (tx_id)
                LEFT JOIN alerts a USING (alert_id)
                WHERE t.tx_id IS NULL OR a.alert_id IS NULL
                """
            )
        ) == 0
        assert connection.scalar(
            text("SELECT count(*) FROM transaction_ground_truth WHERE is_fraud")
        ) == 1_719
        assert connection.scalar(
            text("SELECT count(*) FROM pg_extension WHERE extname = 'vector'")
        ) == 1
        assert connection.scalar(
            text(
                """
                SELECT count(*) FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'transactions'
                  AND column_name = 'alert_id'
                """
            )
        ) == 0


def test_completed_import_is_recorded() -> None:
    engine = create_engine(os.environ["DATABASE_URL"])
    with engine.connect() as connection:
        status = connection.scalar(
            text("SELECT status FROM import_runs ORDER BY started_at DESC LIMIT 1")
        )
        assert status == "completed"


def test_customer_and_transaction_endpoints_use_real_schema() -> None:
    with TestClient(app) as client:
        customers = client.get("/customers/?limit=2")
        assert customers.status_code == 200
        assert len(customers.json()) == 2
        assert customers.json()[0]["customer_id"].startswith("C_")

        transactions = client.get("/customers/C_0/transactions?limit=2")
        assert transactions.status_code == 200
        assert len(transactions.json()) <= 2
        if transactions.json():
            assert "simulation_step" in transactions.json()[0]
            assert "customer_id" not in transactions.json()[0]


def test_investigation_endpoint_is_honest_and_persistent() -> None:
    with TestClient(app) as client:
        missing = client.post("/investigate/does-not-exist")
        assert missing.status_code == 404

        response = client.post("/investigate/C_0")
        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "pending"
        assert "have not been run" in payload["summary"]
        assert "risk_score" not in payload
        assert payload["evidence"]["transaction_count"] >= 0


def test_database_rejects_negative_transaction_amounts() -> None:
    engine = create_engine(os.environ["DATABASE_URL"])
    connection = engine.connect()
    transaction = connection.begin()
    try:
        with pytest.raises(IntegrityError):
            connection.execute(
                text(
                    """
                    INSERT INTO transactions (
                        tx_id, sender_account_id, receiver_account_id,
                        tx_type, tx_amount, simulation_step
                    ) VALUES (999999999, 0, 1, 'TRANSFER', -0.01, 0)
                    """
                )
            )
    finally:
        transaction.rollback()
        connection.close()
