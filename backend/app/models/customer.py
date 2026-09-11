from __future__ import annotations

from sqlalchemy import ForeignKey
from sqlalchemy import String
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship

from app.database.base import Base


class Customer(Base):
    __tablename__ = "customers"

    customer_id: Mapped[str] = mapped_column(
        String(128),
        primary_key=True
    )

    profile: Mapped["CustomerProfile | None"] = relationship(
        "CustomerProfile",
        back_populates="customer",
        uselist=False
    )
    
    accounts: Mapped[
        list["Account"]
    ] = relationship(
        "Account",
        back_populates="customer",
    )

    risk_scores: Mapped[list["RiskScore"]] = relationship(
        "RiskScore",
        back_populates="customer",
        cascade="all, delete-orphan",
    )

    investigations: Mapped[list["Investigation"]] = relationship(
        "Investigation",
        back_populates="customer",
        cascade="all, delete-orphan",
    )


class CustomerProfile(Base):
    __tablename__ = "customer_profiles"

    customer_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey(
            "customers.customer_id",
            ondelete="CASCADE",
        ),
        primary_key=True,
    )

    synthetic_display_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    customer: Mapped["Customer"] = relationship(
        "Customer",
        back_populates="profile",
    )
