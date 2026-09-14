from datetime import datetime

from pydantic import BaseModel
from pydantic import ConfigDict


class InvestigationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    investigation_id: int
    customer_id: str
    status: str
    summary: str | None
    evidence: dict
    created_at: datetime
    updated_at: datetime


class InvestigationListItem(BaseModel):
    investigation_id: int
    customer_id: str
    status: str
    summary: str | None
    score: float | None
    risk_band: str | None
    generation_mode: str | None
    created_at: datetime
    updated_at: datetime
