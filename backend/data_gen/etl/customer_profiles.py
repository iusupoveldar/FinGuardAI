from pathlib import Path

import pandas as pd

from data_gen.etl.generate_synthetic_names import (
    generate_customer_name,
)


parent_path = Path(__file__).resolve().parent.parent
RAW_DATA_DIR = Path.joinpath(parent_path,r'data\raw')
PROCESSED_DATA_DIR = Path.joinpath(parent_path,r'data\processed')


def build_customer_profiles() -> pd.DataFrame:
    accounts_path = (
        RAW_DATA_DIR / "accounts.csv"
    )

    accounts = pd.read_csv(
        accounts_path
    )

    customer_ids = (
        accounts["CUSTOMER_ID"]
        .dropna()
        .astype(str)
        .drop_duplicates()
        .sort_values()
    )

    rows = []

    for customer_id in customer_ids:
        synthetic_display_name = (
            generate_customer_name(
                customer_id
            )
        )

        rows.append(
            {
                "CUSTOMER_ID":
                    customer_id,

                "SYNTHETIC_DISPLAY_NAME":
                    synthetic_display_name,
            }
        )

    profiles = pd.DataFrame(
        rows
    )

    return profiles


def save_customer_profiles() -> None:
    PROCESSED_DATA_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    profiles = (
        build_customer_profiles()
    )

    output_path = (
        PROCESSED_DATA_DIR
        / "customer_profiles.csv"
    )

    profiles.to_csv(
        output_path,
        index=False,
    )

    print(
        f"Created {len(profiles)} "
        f"synthetic customer profiles."
    )

    print(
        f"Saved to: {output_path}"
    )


if __name__ == "__main__":
    save_customer_profiles()