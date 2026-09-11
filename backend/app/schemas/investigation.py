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
