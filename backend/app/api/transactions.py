from app.database.connection import SessionLocal
from app.models.transaction import Transaction

from app.schemas.transaction import TransactionResponse

from sqlalchemy import select

from fastapi import APIRouter


router = APIRouter(
    prefix="/customers",
    tags=["Transactions"]
)

@router.get(
        "/{customer_id}/transactions",
        response_model=list[TransactionResponse])
async def get_customer_transactions(customer_id: int):
    db = SessionLocal()
    try:
        transations = db.execute(select(Transaction).where(Transaction.customer_id == customer_id))
        return transations.scalars().all()
    except:
        # TODO: Add Actual Code, so it won't silent fail
        "Add code that will throw an actual error"
    finally:
        db.close()