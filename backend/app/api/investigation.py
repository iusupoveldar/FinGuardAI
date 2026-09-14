from app.database.connection import get_db
from app.schemas.investigation import InvestigationResponse
from app.schemas.investigation import InvestigationListItem
from app.services.investigation_service import create_or_reuse_investigation
from app.services.investigation_service import get_investigation
from app.services.investigation_service import latest_customer_investigation
from app.services.investigation_service import list_investigations
from app.services.investigation_service import process_investigation

from fastapi import APIRouter
from fastapi import BackgroundTasks
from fastapi import Depends
from fastapi import HTTPException
from fastapi import Query
from sqlalchemy.orm import Session


router = APIRouter(tags=["Investigation"])


@router.post("/investigate/{customer_id}", response_model=InvestigationResponse)
def investigate(
    customer_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    investigation, should_process = create_or_reuse_investigation(db, customer_id)
    if investigation is None:
        raise HTTPException(status_code=404, detail="Customer not found")
    if should_process:
        background_tasks.add_task(process_investigation, investigation.investigation_id)
    return investigation


def _list_item(investigation) -> InvestigationListItem:
    evidence = investigation.evidence or {}
    risk = evidence.get("risk_snapshot") or {}
    return InvestigationListItem(
        investigation_id=investigation.investigation_id,
        customer_id=investigation.customer_id,
        status=investigation.status,
        summary=investigation.summary,
        score=risk.get("score"),
        risk_band=risk.get("risk_band"),
        generation_mode=evidence.get("generation_mode"),
        created_at=investigation.created_at,
        updated_at=investigation.updated_at,
    )


@router.get("/investigations/", response_model=list[InvestigationListItem])
def read_investigation_history(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    return [
        _list_item(item)
        for item in list_investigations(db, limit=limit, offset=offset)
    ]


@router.get(
    "/customers/{customer_id}/investigations/latest",
    response_model=InvestigationResponse,
)
def read_latest_customer_investigation(
    customer_id: str,
    db: Session = Depends(get_db),
):
    investigation = latest_customer_investigation(db, customer_id)
    if investigation is None:
        raise HTTPException(status_code=404, detail="Customer has no cached investigation")
    return investigation


@router.get(
    "/investigations/{investigation_id}", response_model=InvestigationResponse
)
def read_investigation(
    investigation_id: int,
    db: Session = Depends(get_db),
):
    investigation = get_investigation(db, investigation_id)
    if investigation is None:
        raise HTTPException(status_code=404, detail="Investigation not found")
    return investigation
