from app.database.connection import get_db
from app.schemas.investigation import InvestigationResponse
from app.services.investigation_service import create_pending_investigation

from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from sqlalchemy.orm import Session


router = APIRouter(
    prefix="/investigate",
    tags=["Investigation"]
)

@router.post("/{customer_id}", response_model=InvestigationResponse)
def investigate(
    customer_id: str,
    db: Session = Depends(get_db),
):
    investigation = create_pending_investigation(db, customer_id)
    if investigation is None:
        raise HTTPException(status_code=404, detail="Customer not found")
    return investigation
