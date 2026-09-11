from app.database.connection import get_db
from app.models.customer import Customer

from app.schemas.customer import CustomerResponse

from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.orm import selectinload
from fastapi import APIRouter
from fastapi import Depends
from fastapi import Query


router = APIRouter(
    prefix="/customers",
    tags=["Customers"]
)

@router.get("/", response_model=list[CustomerResponse])
def get_customers(
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    statement = (
        select(Customer)
        .options(
            selectinload(Customer.profile),
            selectinload(Customer.accounts),
        )
        .order_by(Customer.customer_id)
        .offset(offset)
        .limit(limit)
    )
    customers = db.scalars(statement).all()

    return [
        CustomerResponse(
            customer_id=customer.customer_id,
            synthetic_display_name=(
                customer.profile.synthetic_display_name
                if customer.profile
                else None
            ),
            accounts=customer.accounts,
        )
        for customer in customers
    ]
