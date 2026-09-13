from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger
from sqlalchemy import CheckConstraint
from sqlalchemy import DateTime
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import JSON
from sqlalchemy import Numeric
from sqlalchemy import String
from sqlalchemy import UniqueConstraint
from sqlalchemy import func
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship

from app.database.base import Base


class RiskScore(Base):
    __tablename__ = "risk_scores"

    __table_args__ = (
        CheckConstraint(
            "score >= 0 AND score <= 100",
            name="risk_score_range",
        ),
        CheckConstraint(
            "risk_band IN ('low', 'medium', 'high', 'unscored')",
            name="risk_band_value",
        ),
        UniqueConstraint(
            "customer_id",
            "data_cutoff_step",
            "model_version",
            "feature_version",
            name="uq_risk_scores_risk_snapshot_identity",
        ),
    )

    risk_score_id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )
    customer_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("customers.customer_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    score: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    risk_band: Mapped[str] = mapped_column(String(32), nullable=False)
    data_cutoff_step: Mapped[int] = mapped_column(Integer, nullable=False)
    evidence: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    model_version: Mapped[str] = mapped_column(String(128), nullable=False)
    feature_version: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    customer: Mapped["Customer"] = relationship(
        "Customer",
        back_populates="risk_scores",
    )
