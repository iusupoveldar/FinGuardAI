"""Validated, atomic AMLSim import using PostgreSQL COPY.

The source files are copied into transaction-local staging tables, validated,
and published with set-based inserts. A completed source checksum makes normal
reruns idempotent. Use --replace only when an intentional replacement is needed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from uuid import uuid4

from sqlalchemy import Connection
from sqlalchemy import text

from app.database.connection import engine


DATA_DIR = Path(__file__).resolve().parent.parent / "data"
FILES = {
    "accounts": DATA_DIR / "raw" / "accounts.csv",
    "profiles": DATA_DIR / "processed" / "customer_profiles.csv",
    "transactions": DATA_DIR / "raw" / "transactions.csv",
    "alerts": DATA_DIR / "raw" / "alerts.csv",
}

STAGING_TABLES = {
    "accounts": """
        CREATE TEMP TABLE staging_accounts (
            account_id bigint NOT NULL,
            customer_id varchar(128) NOT NULL,
            init_balance numeric(18, 2) NOT NULL,
            country varchar(128) NOT NULL,
            account_type varchar(128) NOT NULL,
            is_fraud boolean NOT NULL,
            tx_behavior_id integer NOT NULL
        ) ON COMMIT DROP
    """,
    "profiles": """
        CREATE TEMP TABLE staging_profiles (
            customer_id varchar(128) NOT NULL,
            synthetic_display_name varchar(255) NOT NULL
        ) ON COMMIT DROP
    """,
    "transactions": """
        CREATE TEMP TABLE staging_transactions (
            tx_id bigint NOT NULL,
            sender_account_id bigint NOT NULL,
            receiver_account_id bigint NOT NULL,
            tx_type varchar(128) NOT NULL,
            tx_amount numeric(18, 2) NOT NULL,
            simulation_step integer NOT NULL,
            is_fraud boolean NOT NULL,
            alert_id bigint NOT NULL
        ) ON COMMIT DROP
    """,
    "alerts": """
        CREATE TEMP TABLE staging_alerts (
            alert_id bigint NOT NULL,
            alert_type varchar(128) NOT NULL,
            is_fraud boolean NOT NULL,
            tx_id bigint NOT NULL,
            sender_account_id bigint NOT NULL,
            receiver_account_id bigint NOT NULL,
            tx_type varchar(128) NOT NULL,
            tx_amount numeric(18, 2) NOT NULL,
            simulation_step integer NOT NULL
        ) ON COMMIT DROP
    """,
}

COPY_SQL = {
    "accounts": """
        COPY staging_accounts (
            account_id, customer_id, init_balance, country,
            account_type, is_fraud, tx_behavior_id
        ) FROM STDIN WITH (FORMAT CSV, HEADER TRUE)
    """,
    "profiles": """
        COPY staging_profiles (customer_id, synthetic_display_name)
        FROM STDIN WITH (FORMAT CSV, HEADER TRUE)
    """,
    "transactions": """
        COPY staging_transactions (
            tx_id, sender_account_id, receiver_account_id, tx_type,
            tx_amount, simulation_step, is_fraud, alert_id
        ) FROM STDIN WITH (FORMAT CSV, HEADER TRUE)
    """,
    "alerts": """
        COPY staging_alerts (
            alert_id, alert_type, is_fraud, tx_id, sender_account_id,
            receiver_account_id, tx_type, tx_amount, simulation_step
        ) FROM STDIN WITH (FORMAT CSV, HEADER TRUE)
    """,
}

VALIDATIONS = {
    "duplicate account IDs": """
        SELECT count(*) FROM (
            SELECT account_id FROM staging_accounts
            GROUP BY account_id HAVING count(*) > 1
        ) invalid
    """,
    "duplicate customer profiles": """
        SELECT count(*) FROM (
            SELECT customer_id FROM staging_profiles
            GROUP BY customer_id HAVING count(*) > 1
        ) invalid
    """,
    "accounts without profiles": """
        SELECT count(*) FROM staging_accounts a
        LEFT JOIN staging_profiles p USING (customer_id)
        WHERE p.customer_id IS NULL
    """,
    "profiles without accounts": """
        SELECT count(*) FROM staging_profiles p
        LEFT JOIN staging_accounts a USING (customer_id)
        WHERE a.customer_id IS NULL
    """,
    "invalid account values": """
        SELECT count(*) FROM staging_accounts
        WHERE init_balance < 0 OR tx_behavior_id <= 0
    """,
    "duplicate transaction IDs": """
        SELECT count(*) FROM (
            SELECT tx_id FROM staging_transactions
            GROUP BY tx_id HAVING count(*) > 1
        ) invalid
    """,
    "transactions with missing sender accounts": """
        SELECT count(*) FROM staging_transactions t
        LEFT JOIN staging_accounts a ON a.account_id = t.sender_account_id
        WHERE a.account_id IS NULL
    """,
    "transactions with missing receiver accounts": """
        SELECT count(*) FROM staging_transactions t
        LEFT JOIN staging_accounts a ON a.account_id = t.receiver_account_id
        WHERE a.account_id IS NULL
    """,
    "invalid transaction values": """
        SELECT count(*) FROM staging_transactions
        WHERE tx_amount < 0 OR simulation_step < 0 OR alert_id < -1
    """,
    "fraud labels inconsistent with alert sentinel": """
        SELECT count(*) FROM staging_transactions
        WHERE (is_fraud AND alert_id = -1)
           OR (NOT is_fraud AND alert_id <> -1)
    """,
    "duplicate alert/transaction pairs": """
        SELECT count(*) FROM (
            SELECT alert_id, tx_id FROM staging_alerts
            GROUP BY alert_id, tx_id HAVING count(*) > 1
        ) invalid
    """,
    "inconsistent alert metadata": """
        SELECT count(*) FROM (
            SELECT alert_id FROM staging_alerts
            GROUP BY alert_id
            HAVING count(DISTINCT alert_type) <> 1
                OR count(DISTINCT is_fraud) <> 1
        ) invalid
    """,
    "alerts with missing transactions": """
        SELECT count(*) FROM staging_alerts a
        LEFT JOIN staging_transactions t USING (tx_id)
        WHERE t.tx_id IS NULL
    """,
    "alert details different from canonical transactions": """
        SELECT count(*) FROM staging_alerts a
        JOIN staging_transactions t USING (tx_id)
        WHERE a.alert_id IS DISTINCT FROM t.alert_id
           OR a.sender_account_id IS DISTINCT FROM t.sender_account_id
           OR a.receiver_account_id IS DISTINCT FROM t.receiver_account_id
           OR a.tx_type IS DISTINCT FROM t.tx_type
           OR a.tx_amount IS DISTINCT FROM t.tx_amount
           OR a.simulation_step IS DISTINCT FROM t.simulation_step
           OR a.is_fraud IS DISTINCT FROM t.is_fraud
    """,
    "real transaction alert IDs without alert rows": """
        SELECT count(*) FROM staging_transactions t
        WHERE t.alert_id <> -1
          AND NOT EXISTS (
              SELECT 1 FROM staging_alerts a
              WHERE a.alert_id = t.alert_id AND a.tx_id = t.tx_id
          )
    """,
}

TARGET_TABLES = (
    "customers",
    "customer_profiles",
    "accounts",
    "account_ground_truth",
    "transactions",
    "transaction_ground_truth",
    "alerts",
    "alert_transactions",
)


def source_checksum() -> str:
    digest = hashlib.sha256()
    for name, path in sorted(FILES.items()):
        digest.update(name.encode("utf-8"))
        with path.open("rb") as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(chunk)
    return digest.hexdigest()


def copy_csv(connection: Connection, name: str) -> None:
    connection.exec_driver_sql(STAGING_TABLES[name])
    driver_connection = connection.connection.driver_connection
    with driver_connection.cursor() as cursor:
        with cursor.copy(COPY_SQL[name]) as copy:
            with FILES[name].open("r", encoding="utf-8", newline="") as source:
                for chunk in iter(lambda: source.read(1024 * 1024), ""):
                    copy.write(chunk)


def validate_staging(connection: Connection) -> dict[str, int]:
    errors: list[str] = []
    for description, query in VALIDATIONS.items():
        invalid_count = int(connection.scalar(text(query)) or 0)
        if invalid_count:
            errors.append(f"{description}: {invalid_count}")

    if errors:
        raise ValueError("AMLSim validation failed: " + "; ".join(errors))

    return {
        "customers": int(
            connection.scalar(
                text("SELECT count(DISTINCT customer_id) FROM staging_accounts")
            )
            or 0
        ),
        "customer_profiles": int(
            connection.scalar(text("SELECT count(*) FROM staging_profiles")) or 0
        ),
        "accounts": int(
            connection.scalar(text("SELECT count(*) FROM staging_accounts")) or 0
        ),
        "account_ground_truth": int(
            connection.scalar(text("SELECT count(*) FROM staging_accounts")) or 0
        ),
        "transactions": int(
            connection.scalar(text("SELECT count(*) FROM staging_transactions")) or 0
        ),
        "transaction_ground_truth": int(
            connection.scalar(text("SELECT count(*) FROM staging_transactions")) or 0
        ),
        "alerts": int(
            connection.scalar(
                text("SELECT count(DISTINCT alert_id) FROM staging_alerts")
            )
            or 0
        ),
        "alert_transactions": int(
            connection.scalar(text("SELECT count(*) FROM staging_alerts")) or 0
        ),
    }


def publish(connection: Connection) -> None:
    connection.exec_driver_sql(
        "INSERT INTO customers (customer_id) "
        "SELECT DISTINCT customer_id FROM staging_accounts"
    )
    connection.exec_driver_sql(
        "INSERT INTO customer_profiles (customer_id, synthetic_display_name) "
        "SELECT customer_id, synthetic_display_name FROM staging_profiles"
    )
    connection.exec_driver_sql(
        """
        INSERT INTO accounts (
            account_id, customer_id, init_balance, country,
            account_type, tx_behavior_id
        )
        SELECT account_id, customer_id, init_balance, country,
               account_type, tx_behavior_id
        FROM staging_accounts
        """
    )
    connection.exec_driver_sql(
        "INSERT INTO account_ground_truth (account_id, is_fraud) "
        "SELECT account_id, is_fraud FROM staging_accounts"
    )
    connection.exec_driver_sql(
        """
        INSERT INTO transactions (
            tx_id, sender_account_id, receiver_account_id,
            tx_type, tx_amount, simulation_step
        )
        SELECT tx_id, sender_account_id, receiver_account_id,
               tx_type, tx_amount, simulation_step
        FROM staging_transactions
        """
    )
    connection.exec_driver_sql(
        "INSERT INTO transaction_ground_truth (tx_id, is_fraud) "
        "SELECT tx_id, is_fraud FROM staging_transactions"
    )
    connection.exec_driver_sql(
        """
        INSERT INTO alerts (alert_id, alert_type, ground_truth_is_fraud)
        SELECT alert_id, min(alert_type), bool_and(is_fraud)
        FROM staging_alerts
        GROUP BY alert_id
        """
    )
    connection.exec_driver_sql(
        "INSERT INTO alert_transactions (alert_id, tx_id) "
        "SELECT alert_id, tx_id FROM staging_alerts"
    )


def target_counts(connection: Connection) -> dict[str, int]:
    return {
        table: int(connection.scalar(text(f"SELECT count(*) FROM {table}")) or 0)
        for table in TARGET_TABLES
    }


def import_amlsim(*, replace: bool = False) -> dict[str, int]:
    for path in FILES.values():
        if not path.is_file():
            raise FileNotFoundError(path)

    checksum = source_checksum()
    run_id = str(uuid4())

    with engine.connect() as connection:
        completed = connection.execute(
            text(
                """
                SELECT row_counts
                FROM import_runs
                WHERE source_checksum = :checksum AND status = 'completed'
                ORDER BY finished_at DESC
                LIMIT 1
                """
            ),
            {"checksum": checksum},
        ).scalar_one_or_none()
        if completed is not None and not replace:
            print("This exact dataset is already imported; no changes made.")
            return dict(completed)

    try:
        with engine.begin() as connection:
            current_rows = sum(
                int(connection.scalar(text(f"SELECT count(*) FROM {table}")) or 0)
                for table in TARGET_TABLES
            )
            if current_rows and not replace:
                raise RuntimeError(
                    "Target tables already contain data from another or incomplete "
                    "import. Use --replace only for an intentional replacement."
                )

            if replace:
                connection.exec_driver_sql(
                    """
                    TRUNCATE TABLE
                        investigations, risk_scores, alert_transactions, alerts,
                        transaction_ground_truth, transactions,
                        account_ground_truth, accounts, customer_profiles,
                        customers, import_runs
                    RESTART IDENTITY CASCADE
                    """
                )

            connection.execute(
                text(
                    """
                    INSERT INTO import_runs (
                        import_run_id, source_checksum, status, row_counts
                    ) VALUES (:run_id, :checksum, 'running', CAST(:counts AS jsonb))
                    """
                ),
                {"run_id": run_id, "checksum": checksum, "counts": "{}"},
            )

            for name in ("accounts", "profiles", "transactions", "alerts"):
                print(f"Copying {FILES[name].name}...", flush=True)
                copy_csv(connection, name)

            print("Validating staging data...", flush=True)
            expected = validate_staging(connection)

            print("Publishing validated data...", flush=True)
            publish(connection)
            actual = target_counts(connection)
            if actual != expected:
                raise RuntimeError(
                    f"Published counts differ from staging: expected={expected}, "
                    f"actual={actual}"
                )

            connection.execute(
                text(
                    """
                    UPDATE import_runs
                    SET status = 'completed',
                        row_counts = CAST(:counts AS jsonb),
                        finished_at = now()
                    WHERE import_run_id = :run_id
                    """
                ),
                {"run_id": run_id, "counts": json.dumps(actual)},
            )

        print(f"Import completed: {actual}")
        return actual
    except Exception as exc:
        try:
            with engine.begin() as connection:
                connection.execute(
                    text(
                        """
                        INSERT INTO import_runs (
                            import_run_id, source_checksum, status,
                            row_counts, error_message, finished_at
                        ) VALUES (
                            :run_id, :checksum, 'failed', CAST(:counts AS jsonb),
                            :error_message, now()
                        )
                        ON CONFLICT (import_run_id) DO UPDATE
                        SET status = 'failed', error_message = EXCLUDED.error_message,
                            finished_at = EXCLUDED.finished_at
                        """
                    ),
                    {
                        "run_id": run_id,
                        "checksum": checksum,
                        "counts": "{}",
                        "error_message": str(exc)[:4000],
                    },
                )
        except Exception:
            pass
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description="Import the AMLSim CSV dataset")
    parser.add_argument(
        "--replace",
        action="store_true",
        help="replace existing imported and investigation data atomically",
    )
    args = parser.parse_args()
    import_amlsim(replace=args.replace)


if __name__ == "__main__":
    main()
