from pathlib import Path

import pandas as pd


parent_path = Path(__file__).resolve().parent.parent
DATA_DIR = Path.joinpath(parent_path,r'data_gen\data\raw')


def inspect_accounts() -> None:
    path = DATA_DIR / "accounts.csv"

    df = pd.read_csv(path)

    print("\n=== ACCOUNTS ===")

    print("Rows:", len(df))

    print(
        "Unique ACCOUNT_ID:",
        df["ACCOUNT_ID"].nunique(),
    )

    print(
        "Unique CUSTOMER_ID:",
        df["CUSTOMER_ID"].nunique(),
    )

    print(
        "Duplicate ACCOUNT_ID:",
        df["ACCOUNT_ID"].duplicated().sum(),
    )


def inspect_transactions() -> None:
    path = DATA_DIR / "transactions.csv"

    df = pd.read_csv(path)

    print("\n=== TRANSACTIONS ===")

    print("Rows:", len(df))

    print(
        "Unique TX_ID:",
        df["TX_ID"].nunique(),
    )

    print(
        "Duplicate TX_ID:",
        df["TX_ID"].duplicated().sum(),
    )

    print(
        "Null ALERT_ID:",
        df["ALERT_ID"].isna().sum(),
    )


def inspect_alerts() -> None:
    path = DATA_DIR / "alerts.csv"

    df = pd.read_csv(path)

    print("\n=== ALERTS ===")

    print("Rows:", len(df))

    print(
        "Unique ALERT_ID:",
        df["ALERT_ID"].nunique(),
    )

    print(
        "Unique TX_ID:",
        df["TX_ID"].nunique(),
    )

    print(
        "Duplicate ALERT_ID:",
        df["ALERT_ID"].duplicated().sum(),
    )

    print(
        "Duplicate ALERT_ID + TX_ID:",
        df.duplicated(
            subset=[
                "ALERT_ID",
                "TX_ID",
            ]
        ).sum(),
    )

    transactions_per_alert = (
        df.groupby("ALERT_ID")["TX_ID"]
        .nunique()
        .sort_values(
            ascending=False
        )
    )

    print(
        "\nLargest alerts:"
    )

    print(
        transactions_per_alert.head(10)
    )


def main() -> None:
    inspect_accounts()
    inspect_transactions()
    inspect_alerts()


if __name__ == "__main__":
    main()