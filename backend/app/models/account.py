from __future__ import annotations

from decimal import Decimal

from sqlalchemy import BigInteger
from sqlalchemy import Boolean
from sqlalchemy import CheckConstraint
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

    __table_args__ = (
        CheckConstraint(
            "init_balance >= 0",
            name="init_balance_nonnegative",
        ),
        CheckConstraint(
            "tx_behavior_id > 0",
            name="tx_behavior_id_positive",
        ),
    )

    account_id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=False,
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

    tx_behavior_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    customer: Mapped["Customer"] = relationship(
        "Customer",
        back_populates="accounts",
    )

    ground_truth: Mapped["AccountGroundTruth | None"] = relationship(
        "AccountGroundTruth",
        back_populates="account",
        uselist=False,
        cascade="all, delete-orphan",
    )


class AccountGroundTruth(Base):
    """Restricted synthetic labels; never use these as inference features."""

    __tablename__ = "account_ground_truth"

    account_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(
            "accounts.account_id",
            ondelete="CASCADE",
        ),
        primary_key=True,
    )

    is_fraud: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
    )

    account: Mapped["Account"] = relationship(
        "Account",
        back_populates="ground_truth",
    )
