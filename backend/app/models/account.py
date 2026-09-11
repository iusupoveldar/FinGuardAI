from __future__ import annotations

from decimal import Decimal

from sqlalchemy import Boolean
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import Numeric
from sqlalchemy import String
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship

from app.database.base import Base


class Account(Base):
    __tablename__ = "accounts"

    account_id: Mapped[str] = mapped_column(
        String(128),
        primary_key=True,
    )

    customer_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey(
            "customers.customer_id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        index=True,
    )

    init_balance: Mapped[Decimal] = mapped_column(
        Numeric(18, 2),
        nullable=False,
    )

    country: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )

    account_type: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )

    ground_truth_is_fraud: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
    )

    tx_behavior_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    customer: Mapped["Customer"] = relationship(
        "Customer",
        back_populates="accounts",
    )