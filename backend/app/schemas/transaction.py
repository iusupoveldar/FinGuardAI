from pydantic import BaseModel

class TransactionResponse(BaseModel):
    id: int
    customer_id: int
    amount: float
    currency: str
    country: str

    class Config:
        from_attributes = True