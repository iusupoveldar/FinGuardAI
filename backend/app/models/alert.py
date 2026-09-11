from __future__ import annotations

from sqlalchemy import BigInteger
from sqlalchemy import Boolean
from sqlalchemy import ForeignKey
from sqlalchemy import Index
from sqlalchemy import String
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship

from app.database.base import Base


class Alert(Base):
    __tablename__ = "alerts"

    alert_id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=False,
    )

    alert_type: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )

    ground_truth_is_fraud: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
    )

    transactions: Mapped[
        list["AlertTransaction"]
    ] = relationship(
        "AlertTransaction",
        back_populates="alert",
        cascade="all, delete-orphan",
    )


class AlertTransaction(Base):
    __tablename__ = "alert_transactions"

    __table_args__ = (
        Index(
            "ix_alert_transactions_tx_id",
            "tx_id",
        ),
    )

    alert_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(
            "alerts.alert_id",
            ondelete="CASCADE",
        ),
        primary_key=True,
    )

    tx_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(
            "transactions.tx_id",
            ondelete="CASCADE",
        ),
        primary_key=True,
    )

    alert: Mapped["Alert"] = relationship(
        "Alert",
        back_populates="transactions",
    )

    transaction: Mapped["Transaction"] = relationship(
        "Transaction",
        back_populates="alert_links",
    )
