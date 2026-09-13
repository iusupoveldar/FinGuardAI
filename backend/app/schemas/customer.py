from decimal import Decimal

from pydantic import BaseModel
from pydantic import ConfigDict


class AccountSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    account_id: int
    init_balance: Decimal
    country: str
    account_type: str


class RiskSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    score: Decimal
    risk_band: str
    data_cutoff_step: int
    model_version: str
    feature_version: str
    evidence: dict


class PolicySourceResponse(BaseModel):
    source_id: str
    document_id: str
    title: str
    version: str
    heading: str
    text: str
    score: float


class RiskDetailResponse(BaseModel):
    risk: RiskSummary
    retrieval_status: str
    corpus_version: str | None
    policy_sources: list[PolicySourceResponse]


class CustomerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    customer_id: str
    synthetic_display_name: str | None
    accounts: list[AccountSummary]
    risk: RiskSummary | None = None
