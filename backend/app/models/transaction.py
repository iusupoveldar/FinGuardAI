from sqlalchemy import Column, Integer, String, Float, ForeignKey

from app.database.base import base

class Transaction(base):
    __tablename__ = 'transactions'

    id = Column(
        Integer,
        primary_key=True
    )

    customer_id = Column(
        Integer,
        ForeignKey("customers.id")
    )

    amount = Column(
        Float
    )

    currency = Column(
        String
    )

    country = Column(
        String
    )