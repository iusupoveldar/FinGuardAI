# insert order
"""
1. customers

2. customer_profiles

3. accounts

4. transactions

5. alerts

6. alert_transactions
"""
from pathlib import Path

import pandas as pd

from sqlalchemy.orm import Session

from app.database.connection import SessionLocal

from app.models.customer import Customer, CustomerProfile
from app.models.account import Account
from app.models.transaction import Transaction
from app.models.alert import Alert
from app.models.alert import AlertTransaction



parent_path = Path(__file__).resolve().parent.parent

ACCOUNT_FILE = (
    Path.joinpath(parent_path,"data/raw/accounts.csv")
)

CUSTOMER_PROFILE_FILE = (
    Path.joinpath(parent_path,"data/processed/customer_profiles.csv")
)

TRANSACTION_FILE = (
    Path.joinpath(parent_path,"data/raw/transactions.csv")
)

ALERT_FILE = (
    Path.joinpath(parent_path,"data/raw/alerts.csv")
)

def load_customers(
    db: Session
):
    accounts = pd.read_csv(
        ACCOUNT_FILE
    )

    customer_ids = (
        accounts["CUSTOMER_ID"]
        .drop_duplicates()
    )

    for customer_id in customer_ids:
        customer = Customer(
            customer_id=str(
                customer_id
            )
        )

        db.add(
            customer
        )

    db.commit()

def load_customer_profiles(
        db: Session
):
    df = pd.read_csv(
        CUSTOMER_PROFILE_FILE
    )


    for _, row in df.iterrows():

        profile = CustomerProfile(

            customer_id=str(
                row["CUSTOMER_ID"]
            ),

            synthetic_display_name=row[
                "SYNTHETIC_DISPLAY_NAME"
            ]

        )


        db.add(profile)


    db.commit()

def load_accounts(
    db: Session
    ):
    df = pd.read_csv(
        ACCOUNT_FILE
    )

    for _, row in df.iterrows():
        account = Account(
            account_id=str(
                row["ACCOUNT_ID"]
            ),

            customer_id=str(
                row["CUSTOMER_ID"]
            ),

            init_balance=row[
                "INIT_BALANCE"
            ],

            country=row[
                "COUNTRY"
            ],

            account_type=row[
                "ACCOUNT_TYPE"
            ],

            ground_truth_is_fraud=row[
                "IS_FRAUD"
            ],

            tx_behavior_id=row[
                "TX_BEHAVIOR_ID"
            ]
        )

        db.add(
            account
        )

    db.commit()



def load_transactions(
    db: Session
):
    df = pd.read_csv(
        TRANSACTION_FILE
    )

    for _, row in df.iterrows():
        transaction = Transaction(
            tx_id=str(
                row["TX_ID"]
            ),

            sender_account_id=str(
                row["SENDER_ACCOUNT_ID"]
            ),

            receiver_account_id=str(
                row["RECEIVER_ACCOUNT_ID"]
            ),

            tx_type=row[
                "TX_TYPE"
            ],

            tx_amount=row[
                "TX_AMOUNT"
            ],

            timestamp=row[
                "TIMESTAMP"
            ],

            ground_truth_is_fraud=row[
                "IS_FRAUD"
            ],

            alert_id=(
                str(row["ALERT_ID"])
                if pd.notna(
                    row["ALERT_ID"]
                )
                else None
            )
        )

        db.add(
            transaction
        )

    db.commit()



def load_alerts(
    db: Session
):
    df = pd.read_csv(
        ALERT_FILE
    )

    alerts = (
        df.drop_duplicates(
            subset=[
                "ALERT_ID"
            ]
        )
    )

    for _, row in alerts.iterrows():
        alert = Alert(
            alert_id=str(
                row["ALERT_ID"]
            ),

            alert_type=row[
                "ALERT_TYPE"
            ],

            ground_truth_is_fraud=row[
                "IS_FRAUD"
            ]
        )

        db.add(
            alert
        )

    db.commit()



def load_alert_transactions(
    db: Session
):
    df = pd.read_csv(
        ALERT_FILE
    )

    df = df[
        [
            "ALERT_ID",
            "TX_ID"
        ]
    ]

    for _, row in df.iterrows():
        link = AlertTransaction(
            alert_id=str(
                row["ALERT_ID"]
            ),

            tx_id=str(
                row["TX_ID"]
            )
        )

        db.add(
            link
        )

    db.commit()

def main():
    db = SessionLocal()

    try:
        print(
            "Loading customers"
        )
        load_customers(db)

        print(
            "Loading customer profiles"
        )

        load_customer_profiles(db)

        print(
            "Loading accounts"
        )

        load_accounts(db)

        print(
            "Loading transactions"
        )

        load_transactions(db)

        print(
            "Loading alerts"
        )

        load_alerts(db)

        print(
            "Linking alerts"
        )

        load_alert_transactions(db)

        print(
            "Finished"
        )

    finally:
        db.close()

if __name__ == "__main__":
    main()