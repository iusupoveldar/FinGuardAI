
from faker import Faker
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