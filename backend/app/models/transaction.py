from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean
from sqlalchemy import DateTime
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
            "ix_transactions_sender_timestamp",
            "sender_account_id",
            "timestamp",
        ),
        Index(
            "ix_transactions_receiver_timestamp",
            "receiver_account_id",
            "timestamp",
        ),
        Index(
            "ix_transactions_alert_id",
            "alert_id",
        ),
    )

    tx_id: Mapped[str] = mapped_column(
        String(128),
        primary_key=True,
    )

    sender_account_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey(
            "accounts.account_id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )

    receiver_account_id: Mapped[str] = mapped_column(
        String(128),
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

    timestamp: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    ground_truth_is_fraud: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
    )

    alert_id: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
    )

    sender_account: Mapped["Account"] = relationship(
        "Account",
        foreign_keys=[sender_account_id],
    )

    receiver_account: Mapped["Account"] = relationship(
        "Account",
        foreign_keys=[receiver_account_id],
    )