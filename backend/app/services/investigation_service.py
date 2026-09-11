from sqlalchemy import func
from sqlalchemy import or_
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.account import Account
from app.models.customer import Customer
from app.models.investigation import Investigation
from app.models.transaction import Transaction


def create_pending_investigation(
    db: Session,
    customer_id: str,
) -> Investigation | None:
    customer_exists = db.scalar(
        select(Customer.customer_id).where(Customer.customer_id == customer_id)
    )
    if customer_exists is None:
        return None

    account_ids = select(Account.account_id).where(
        Account.customer_id == customer_id
    )
    transaction_count = db.scalar(
        select(func.count(Transaction.tx_id)).where(
            or_(
                Transaction.sender_account_id.in_(account_ids),
                Transaction.receiver_account_id.in_(account_ids),
            )
        )
    )

    investigation = Investigation(
        customer_id=customer_id,
        status="pending",
        summary=(
            "Investigation queued. Automated risk scoring and LLM analysis "
            "have not been run."
        ),
        evidence={"transaction_count": int(transaction_count or 0)},
    )
    db.add(investigation)
    db.commit()
    db.refresh(investigation)
    return investigation
