from decimal import Decimal

from pydantic import BaseModel
from pydantic import ConfigDict


class TransactionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    tx_id: int
    sender_account_id: int
    receiver_account_id: int
    tx_type: str
    tx_amount: Decimal
    simulation_step: int
