from pathlib import Path

import pandas as pd


parent_path = Path(__file__).resolve().parent.parent
DATA_DIR = Path.joinpath(parent_path,r'data_gen\data\raw')


def validate_alert_transactions() -> None:
    transactions = pd.read_csv(
        DATA_DIR / "transactions.csv"
    )

    alerts = pd.read_csv(
        DATA_DIR / "alerts.csv"
    )

    transaction_columns = [
        "TX_ID",
        "SENDER_ACCOUNT_ID",
        "RECEIVER_ACCOUNT_ID",
        "TX_TYPE",
        "TX_AMOUNT",
        "TIMESTAMP",
    ]

    transaction_subset = transactions[
        transaction_columns
    ].copy()

    merged = alerts.merge(
        transaction_subset,
        on="TX_ID",
        how="left",
        suffixes=(
            "_ALERT",
            "_TRANSACTION",
        ),
        validate="many_to_one",
    )

    missing_transactions = merged[
        "SENDER_ACCOUNT_ID_TRANSACTION"
    ].isna()

    if missing_transactions.any():
        missing_ids = merged.loc[
            missing_transactions,
            "TX_ID",
        ].tolist()

        raise ValueError(
            "alerts.csv contains TX_ID values "
            "that do not exist in transactions.csv: "
            f"{missing_ids[:20]}"
        )

    compare_columns = [
        "SENDER_ACCOUNT_ID",
        "RECEIVER_ACCOUNT_ID",
        "TX_TYPE",
        "TX_AMOUNT",
        "TIMESTAMP",
    ]

    for column in compare_columns:
        alert_column = (
            f"{column}_ALERT"
        )

        transaction_column = (
            f"{column}_TRANSACTION"
        )

        mismatches = (
            merged[alert_column].astype(str)
            !=
            merged[transaction_column].astype(str)
        )

        if mismatches.any():
            count = int(
                mismatches.sum()
            )

            raise ValueError(
                f"{column} has {count} "
                "mismatches between alerts.csv "
                "and transactions.csv."
            )

    print(
        "Alert transaction fields match "
        "transactions.csv."
    )


def validate_alert_metadata() -> None:
    alerts = pd.read_csv(
        DATA_DIR / "alerts.csv"
    )

    columns_that_should_be_constant = [
        "ALERT_TYPE",
        "IS_FRAUD",
    ]

    for column in columns_that_should_be_constant:
        value_counts = (
            alerts.groupby("ALERT_ID")[column]
            .nunique(
                dropna=False
            )
        )

        invalid = value_counts[
            value_counts > 1
        ]

        if not invalid.empty:
            raise ValueError(
                f"{column} changes inside "
                f"the same ALERT_ID:\n"
                f"{invalid.head(20)}"
            )

    print(
        "Alert-level metadata is consistent."
    )


def main() -> None:
    validate_alert_metadata()
    validate_alert_transactions()

    print(
        "AMLSim validation completed successfully."
    )


if __name__ == "__main__":
    main()