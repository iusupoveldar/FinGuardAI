from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import app.models  # noqa: F401
from app.api.customers import get_customers
from app.config import RISK_FEATURE_VERSION, RISK_MODEL_VERSION
from app.database.base import Base
from app.models.customer import Customer
from app.models.risk import RiskScore


def _risk(
    risk_id: int,
    customer_id: str,
    score: float,
    cutoff: int,
    risk_band: str | None = None,
) -> RiskScore:
    return RiskScore(
        risk_score_id=risk_id,
        customer_id=customer_id,
        score=score,
        risk_band=risk_band or ("high" if score >= 70 else "low"),
        data_cutoff_step=cutoff,
        evidence={},
        model_version=RISK_MODEL_VERSION,
        feature_version=RISK_FEATURE_VERSION,
    )


def test_customer_sort_uses_latest_score_before_pagination_and_puts_unscored_last() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add_all(
            [
                Customer(customer_id="C0"),
                Customer(customer_id="C1"),
                Customer(customer_id="C2"),
                Customer(customer_id="C3"),
            ]
        )
        db.add_all(
            [
                _risk(1, "C1", 95, 5),
                _risk(2, "C1", 10, 6),  # latest compatible score wins
                _risk(3, "C2", 80, 6),
                _risk(4, "C0", 0, 6, risk_band="unscored"),
            ]
        )
        db.commit()

        descending = get_customers(
            limit=2,
            offset=0,
            sort_by="score",
            sort_order="desc",
            db=db,
        )
        ascending = get_customers(
            limit=4,
            offset=0,
            sort_by="score",
            sort_order="asc",
            db=db,
        )

    assert [item.customer_id for item in descending] == ["C2", "C1"]
    assert [item.customer_id for item in ascending] == ["C1", "C2", "C0", "C3"]
