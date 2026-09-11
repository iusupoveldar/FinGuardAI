from app.database.connection import get_db
from app.models.account import Account
from app.models.transaction import Transaction

from app.schemas.transaction import TransactionResponse

from sqlalchemy import or_
from sqlalchemy import select
from sqlalchemy.orm import Session

from fastapi import APIRouter
from fastapi import Depends
from fastapi import Query


router = APIRouter(
    prefix="/customers",
    tags=["Transactions"]
)

@router.get(
        "/{customer_id}/transactions",
        response_model=list[TransactionResponse])
def get_customer_transactions(
    customer_id: str,
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    account_ids = select(Account.account_id).where(
        Account.customer_id == customer_id
    )
    statement = (
        select(Transaction)
        .where(
            or_(
                Transaction.sender_account_id.in_(account_ids),
                Transaction.receiver_account_id.in_(account_ids),
            )
        )
        .order_by(
            Transaction.simulation_step.desc(),
            Transaction.tx_id.desc(),
        )
        .offset(offset)
        .limit(limit)
    )
    return db.scalars(statement).all()
