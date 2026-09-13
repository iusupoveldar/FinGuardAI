from app.database.connection import get_db
from app.models.customer import Customer

from app.schemas.customer import CustomerResponse
from app.schemas.customer import RiskDetailResponse
from app.services.risk_service import latest_risk_score
from app.config import RISK_FEATURE_VERSION
from app.config import RISK_MODEL_VERSION

from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.orm import selectinload
from fastapi import APIRouter
from fastapi import Depends
from fastapi import Query
from fastapi import HTTPException


router = APIRouter(
    prefix="/customers",
    tags=["Customers"]
)


@router.get("/{customer_id}/risk", response_model=RiskDetailResponse)
def get_customer_risk(
    customer_id: str,
    db: Session = Depends(get_db),
):
    """Return persisted score evidence with locally retrieved policy sources."""

    risk = latest_risk_score(db, customer_id)
    if risk is None:
        customer_exists = db.scalar(
            select(Customer.customer_id).where(Customer.customer_id == customer_id)
        )
        if customer_exists is None:
            raise HTTPException(status_code=404, detail="Customer not found")
        raise HTTPException(status_code=404, detail="Customer has no risk snapshot")

    try:
        from ai.retrieval import PolicyRetriever

        retrieval = PolicyRetriever().retrieve_with_evidence(risk.evidence)
        return RiskDetailResponse(
            risk=risk,
            retrieval_status="available",
            corpus_version=retrieval["corpus_version"],
            policy_sources=retrieval["policy_sources"],
        )
    except (FileNotFoundError, RuntimeError, ValueError):
        # Scoring stays useful when the optional local index is unavailable.
        return RiskDetailResponse(
            risk=risk,
            retrieval_status="unavailable",
            corpus_version=None,
            policy_sources=[],
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
            selectinload(Customer.risk_scores),
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
            risk=(
                max(
                    [
                        item
                        for item in customer.risk_scores
                        if item.model_version == RISK_MODEL_VERSION
                        and item.feature_version == RISK_FEATURE_VERSION
                    ],
                    key=lambda item: (item.data_cutoff_step, item.created_at),
                    default=None,
                )
            ),
        )
        for customer in customers
    ]
