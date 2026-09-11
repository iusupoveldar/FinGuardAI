from sqlalchemy import Column, Integer, String

from app.database.base import base

class Customer(base):
    __tablename__ = 'customers'

    id = Column(
        Integer,
        primary_key=True
    )

    name = Column(
        String
    )

    
    country = Column(
        String
    )

    
    risk_score = Column(
        Integer
    )