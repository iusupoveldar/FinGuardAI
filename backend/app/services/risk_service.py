"""Read helpers for persisted operational risk snapshots."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.risk import RiskScore
from app.config import RISK_FEATURE_VERSION, RISK_MODEL_VERSION


def latest_risk_score(db: Session, customer_id: str) -> RiskScore | None:
    return db.scalar(
        select(RiskScore)
        .where(
            RiskScore.customer_id == customer_id,
            RiskScore.model_version == RISK_MODEL_VERSION,
            RiskScore.feature_version == RISK_FEATURE_VERSION,
        )
        .order_by(
            RiskScore.data_cutoff_step.desc(),
            RiskScore.created_at.desc(),
            RiskScore.risk_score_id.desc(),
        )
        .limit(1)
    )
