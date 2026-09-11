from decimal import Decimal

from pydantic import BaseModel
from pydantic import ConfigDict


class AccountSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    account_id: int
    init_balance: Decimal
    country: str
    account_type: str


class CustomerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    customer_id: str
    synthetic_display_name: str | None
    accounts: list[AccountSummary]
