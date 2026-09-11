from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger
from sqlalchemy import CheckConstraint
from sqlalchemy import DateTime
from sqlalchemy import ForeignKey
from sqlalchemy import Numeric
from sqlalchemy import String
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
