from __future__ import annotations

from decimal import Decimal

from sqlalchemy import BigInteger
from sqlalchemy import Boolean
from sqlalchemy import CheckConstraint
from sqlalchemy import ForeignKey
from sqlalchemy import Index
from sqlalchemy import Numeric
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship

from app.database.base import Base


class Transaction(Base):
    __tablename__ = "transactions"

    __table_args__ = (
        Index(
            "ix_transactions_sender_step",
            "sender_account_id",
            "simulation_step",
        ),
        Index(
            "ix_transactions_receiver_step",
            "receiver_account_id",
            "simulation_step",
        ),
        Index(
            "ix_transactions_simulation_step",
            "simulation_step",
        ),
        CheckConstraint(
            "tx_amount >= 0",
            name="tx_amount_nonnegative",
        ),
        CheckConstraint(
            "simulation_step >= 0",
            name="simulation_step_nonnegative",
        ),
    )

    tx_id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=False,
    )

    sender_account_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(
            "accounts.account_id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )

    receiver_account_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(
            "accounts.account_id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )

    tx_type: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )

    tx_amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 2),
        nullable=False,
    )

    simulation_step: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    sender_account: Mapped["Account"] = relationship(
        "Account",
        foreign_keys=[sender_account_id],
    )

    receiver_account: Mapped["Account"] = relationship(
        "Account",
        foreign_keys=[receiver_account_id],
    )

    alert_links: Mapped[list["AlertTransaction"]] = relationship(
        "AlertTransaction",
        back_populates="transaction",
        cascade="all, delete-orphan",
    )

    ground_truth: Mapped["TransactionGroundTruth | None"] = relationship(
        "TransactionGroundTruth",
        back_populates="transaction",
        uselist=False,
        cascade="all, delete-orphan",
    )


class TransactionGroundTruth(Base):
    """Restricted synthetic labels; never use these as inference features."""

    __tablename__ = "transaction_ground_truth"

    tx_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(
            "transactions.tx_id",
            ondelete="CASCADE",
        ),
        primary_key=True,
    )

    is_fraud: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
    )

    transaction: Mapped["Transaction"] = relationship(
        "Transaction",
        back_populates="ground_truth",
    )
