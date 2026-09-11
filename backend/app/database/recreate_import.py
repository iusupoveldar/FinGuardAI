"""
    Recreate the configured database schema and import the AMLSim dataset.

    Run from the backend directory:
        python -m app.database.recreate_import

    For non-interactive local automation:
        python -m app.database.recreate_import --yes
"""

from __future__ import annotations

import argparse

from sqlalchemy import text
from sqlalchemy.engine import make_url

from app.config import DATABASE_URL
from app.database.connection import engine
from data_gen.etl.import_amlsim import import_amlsim
from scripts.create_tables import create_tables


CONFIRMATION_TEXT = "RECREATE"
PROTECTED_DATABASES = {"postgres", "template0", "template1"}


def database_label() -> str:
    """Return a display-safe target label without exposing credentials."""
    url = make_url(DATABASE_URL)
    host = url.host or "localhost"
    database = url.database or ""
    return f"{host}/{database}"


def ensure_safe_target() -> None:
    database = make_url(DATABASE_URL).database
    if not database:
        raise RuntimeError("DATABASE_URL must include a database name.")
    if database.lower() in PROTECTED_DATABASES:
        raise RuntimeError(
            f"Refusing to recreate protected database {database!r}. "
            "Configure DATABASE_URL for the FinGuardAI application database."
        )


def confirm_recreation() -> None:
    target = database_label()
    response = input(
        f"This permanently replaces the public schema in {target}. "
        f"Type {CONFIRMATION_TEXT} to continue: "
    )
    if response.strip() != CONFIRMATION_TEXT:
        raise SystemExit("Database recreation cancelled; no changes were made.")


def recreate_schema() -> None:
    """Drop and recreate only the configured database's public schema."""
    with engine.begin() as connection:
        connection.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
        connection.execute(text("CREATE SCHEMA public"))

    # Discard connections that may retain state from the previous schema.
    engine.dispose()


def recreate_and_import() -> dict[str, int]:
    ensure_safe_target()

    print(f"Recreating public schema in {database_label()}...")
    recreate_schema()

    print("Applying migrations...")
    create_tables()

    print("Importing validated AMLSim data...")
    counts = import_amlsim()

    print("Database recreation and import completed successfully.")
    print(f"Verified imported counts: {counts}")
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Drop the configured database's public schema, apply migrations, "
            "and import the AMLSim dataset."
        )
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="skip the interactive RECREATE confirmation",
    )
    args = parser.parse_args()

    if not args.yes:
        confirm_recreation()

    recreate_and_import()


if __name__ == "__main__":
    main()
