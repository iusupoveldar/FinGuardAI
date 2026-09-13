import pandas as pd
import pytest

from ml.features import FEATURE_COLUMNS, build_transaction_features


@pytest.fixture
def accounts() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"account_id": 1, "customer_id": "C1", "init_balance": 100, "country": "CA", "account_type": "personal"},
            {"account_id": 2, "customer_id": "C2", "init_balance": 100, "country": "US", "account_type": "personal"},
        ]
    )


def test_same_step_transactions_cannot_see_each_other(accounts: pd.DataFrame) -> None:
    transactions = pd.DataFrame(
        [
            {"tx_id": 10, "sender_account_id": 1, "receiver_account_id": 2, "tx_type": "TRANSFER", "tx_amount": 10, "simulation_step": 1},
            {"tx_id": 11, "sender_account_id": 1, "receiver_account_id": 2, "tx_type": "TRANSFER", "tx_amount": 20, "simulation_step": 1},
            {"tx_id": 12, "sender_account_id": 1, "receiver_account_id": 2, "tx_type": "TRANSFER", "tx_amount": 30, "simulation_step": 2},
        ]
    )

    features = build_transaction_features(transactions, accounts)

    assert list(features.columns) == ["simulation_step", *FEATURE_COLUMNS]
    assert features.loc[10, "sender_out_count_1"] == 0
    assert features.loc[11, "sender_out_count_1"] == 0
    assert features.loc[12, "sender_out_count_1"] == 2
    assert features.loc[10, "is_new_counterparty"] == 1
    assert features.loc[11, "is_new_counterparty"] == 1
    assert features.loc[12, "is_new_counterparty"] == 0


def test_feature_builder_rejects_restricted_columns(accounts: pd.DataFrame) -> None:
    transaction = pd.DataFrame(
        [{"tx_id": 1, "sender_account_id": 1, "receiver_account_id": 2, "tx_type": "TRANSFER", "tx_amount": 10, "simulation_step": 1, "is_fraud": True}]
    )
    with pytest.raises(ValueError, match="restricted feature columns"):
        build_transaction_features(transaction, accounts)


def test_zero_balance_is_safe(accounts: pd.DataFrame) -> None:
    accounts.loc[accounts["account_id"] == 1, "init_balance"] = 0
    transaction = pd.DataFrame(
        [{"tx_id": 1, "sender_account_id": 1, "receiver_account_id": 2, "tx_type": "TRANSFER", "tx_amount": 10, "simulation_step": 1}]
    )
    features = build_transaction_features(transaction, accounts)
    assert features.loc[1, "zero_initial_balance"] == 1
    assert features.loc[1, "amount_to_initial_balance"] == 0
