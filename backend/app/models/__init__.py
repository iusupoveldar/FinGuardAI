"""Import every ORM model so SQLAlchemy can resolve named relationships."""

from app.models.account import Account, AccountGroundTruth
from app.models.alert import Alert, AlertTransaction
from app.models.customer import Customer, CustomerProfile
from app.models.import_run import ImportRun
from app.models.investigation import Investigation
from app.models.risk import RiskScore
from app.models.transaction import Transaction, TransactionGroundTruth

__all__ = [
    "Account",
    "AccountGroundTruth",
    "Alert",
    "AlertTransaction",
    "Customer",
    "CustomerProfile",
    "ImportRun",
    "Investigation",
    "RiskScore",
    "Transaction",
    "TransactionGroundTruth",
]
