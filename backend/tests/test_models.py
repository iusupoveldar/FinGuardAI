from sqlalchemy import CheckConstraint
from sqlalchemy import UniqueConstraint
from sqlalchemy.orm import configure_mappers

from app.database.base import Base
from app.models.account import Account
from app.models.account import AccountGroundTruth
from app.models.alert import Alert
from app.models.alert import AlertTransaction
from app.models.customer import Customer
from app.models.customer import CustomerProfile
from app.models.import_run import ImportRun
from app.models.investigation import Investigation
from app.models.risk import RiskScore
from app.models.transaction import Transaction
from app.models.transaction import TransactionGroundTruth


def test_all_mappers_configure() -> None:
    configure_mappers()


def test_expected_tables_are_registered() -> None:
    assert set(Base.metadata.tables) == {
        "account_ground_truth",
        "accounts",
        "alert_transactions",
        "alerts",
        "customer_profiles",
        "customers",
        "import_runs",
        "investigations",
        "risk_scores",
        "transaction_ground_truth",
        "transactions",
    }


def test_transaction_alert_relationship_is_not_duplicated() -> None:
    columns = set(Transaction.__table__.columns.keys())
    assert "alert_id" not in columns
    assert "simulation_step" in columns
    assert "timestamp" not in columns
    assert set(AlertTransaction.__table__.primary_key.columns.keys()) == {
        "alert_id",
        "tx_id",
    }


def test_ground_truth_is_separate_from_operational_entities() -> None:
    assert "ground_truth_is_fraud" not in Account.__table__.columns
    assert "ground_truth_is_fraud" not in Transaction.__table__.columns
    assert "is_fraud" in AccountGroundTruth.__table__.columns
    assert "is_fraud" in TransactionGroundTruth.__table__.columns


def test_money_and_step_checks_exist() -> None:
    account_checks = {
        item.name
        for item in Account.__table__.constraints
        if isinstance(item, CheckConstraint)
    }
    transaction_checks = {
        item.name
        for item in Transaction.__table__.constraints
        if isinstance(item, CheckConstraint)
    }
    assert "ck_accounts_init_balance_nonnegative" in account_checks
    assert "ck_transactions_tx_amount_nonnegative" in transaction_checks
    assert "ck_transactions_simulation_step_nonnegative" in transaction_checks


def test_risk_snapshots_have_explicit_identity_and_evidence() -> None:
    assert {"risk_band", "data_cutoff_step", "evidence"}.issubset(
        RiskScore.__table__.columns.keys()
    )
    unique_columns = {
        tuple(column.name for column in item.columns)
        for item in RiskScore.__table__.constraints
        if isinstance(item, UniqueConstraint)
    }
    assert (
        "customer_id",
        "data_cutoff_step",
        "model_version",
        "feature_version",
    ) in unique_columns


def test_investigations_have_idempotent_snapshot_identity() -> None:
    assert Investigation.__table__.columns["snapshot_key"].unique
