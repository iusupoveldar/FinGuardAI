
from faker import Faker
import pandas as pd
from pathlib import Path
import hashlib

def _customer_seed(customer_id: str) -> int:
    """
    Convert a CUSTOMER_ID into a deterministic integer seed.

    The same CUSTOMER_ID always produces the same seed.
    """

    customer_id_string = str(customer_id)

    digest = hashlib.sha256(
        customer_id_string.encode("utf-8")
    ).digest()

    seed = int.from_bytes(
        digest[:8],
        byteorder="big",
        signed=False,
    )

    return seed

def generate_customer_name(
    customer_id: str,
) -> str:
    """
    Generate a deterministic fictional display name
    for an AMLSim customer.

    The generated name is UI-only synthetic metadata.
    It must never be used by the risk engine.
    """

    fake = Faker("en_CA")

    seed = _customer_seed(customer_id)

    fake.seed_instance(seed)

    return fake.name()

# fake = Faker.seed(42)


# parent_path = Path(__file__).resolve().parent.parent
# account_path = Path.joinpath(parent_path,r'data\raw\accounts.csv')
# processed_account_path = Path.joinpath(parent_path,r'data\processed\accounts.csv')


# df = pd.read_csv(account_path)
# names = []
# for row in df.itertuples():
#     names.append(generate_customer_name(row[2]))

# df['NAME'] = names
# df[['FIRST_NAME', 'LAST_NAME']] = df['NAME'].str.split(n=1, expand=True)
# print(df.head(5))
# df.to_csv(processed_account_path, index=False)