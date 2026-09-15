from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from ai.retrieval import current_corpus_version
import app.models  # noqa: F401
from app import config
from app.database.base import Base
from app.models.customer import Customer
from app.models.investigation import Investigation
from app.services.investigation_service import (
    _fallback_reason,
    _snapshot_key,
    create_or_reuse_investigation,
    latest_customer_investigation,
    list_investigations,
)


def test_snapshot_key_changes_with_frozen_corpus_identity() -> None:
    first = _snapshot_key("C1", 30, "corpus-v1")

    assert first == _snapshot_key("C1", 30, "corpus-v1")
    assert first != _snapshot_key("C1", 30, "corpus-v2")
    assert len(first) == 64


def test_disabled_deepseek_short_circuits_before_budget_query(monkeypatch) -> None:
    monkeypatch.setattr(config, "DEEPSEEK_ENABLED", False)
    risk = SimpleNamespace(risk_band="high")

    reason = _fallback_reason(object(), risk, [{"source_id": "policy:1"}])

    assert "disabled" in reason


def test_investigation_history_is_newest_first_and_latest_is_customer_scoped() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    now = datetime.now(timezone.utc)
    with Session(engine) as db:
        db.add_all([Customer(customer_id="C1"), Customer(customer_id="C2")])
        db.add_all(
            [
                Investigation(
                    investigation_id=1,
                    customer_id="C1",
                    snapshot_key="a" * 64,
                    status="completed",
                    summary="older",
                    evidence={},
                    created_at=now - timedelta(days=1),
                    updated_at=now - timedelta(days=1),
                ),
                Investigation(
                    investigation_id=2,
                    customer_id="C2",
                    snapshot_key="b" * 64,
                    status="completed",
                    summary="newest overall",
                    evidence={},
                    created_at=now,
                    updated_at=now,
                ),
                Investigation(
                    investigation_id=3,
                    customer_id="C1",
                    snapshot_key="c" * 64,
                    status="completed",
                    summary="latest for C1",
                    evidence={},
                    created_at=now - timedelta(hours=1),
                    updated_at=now - timedelta(hours=1),
                ),
            ]
        )
        db.commit()

        history = list_investigations(db, limit=10, offset=0)
        latest = latest_customer_investigation(db, "C1")

    assert [item.investigation_id for item in history] == [2, 3, 1]
    assert latest is not None
    assert latest.investigation_id == 3


@pytest.mark.parametrize("status", ["pending", "in_progress"])
def test_stale_investigation_is_requeued(monkeypatch, status: str) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    monkeypatch.setattr(config, "INVESTIGATION_STALE_AFTER_SECONDS", 60)

    with Session(engine) as db:
        db.add(Customer(customer_id="C1"))
        db.commit()
        existing = Investigation(
            investigation_id=1,
            customer_id="C1",
            snapshot_key=_snapshot_key("C1", 0, current_corpus_version()),
            status=status,
            summary="Interrupted work",
            evidence={},
            created_at=datetime.now(timezone.utc) - timedelta(minutes=10),
            updated_at=datetime.now(timezone.utc) - timedelta(minutes=10),
        )
        db.add(existing)
        db.commit()
        investigation_id = existing.investigation_id

        recovered, should_process = create_or_reuse_investigation(db, "C1")

    assert recovered is not None
    assert recovered.investigation_id == investigation_id
    assert recovered.status == "pending"
    assert recovered.evidence["stale_recovery_count"] == 1
    assert should_process is True


def test_recent_pending_investigation_is_not_duplicated(monkeypatch) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    monkeypatch.setattr(config, "INVESTIGATION_STALE_AFTER_SECONDS", 300)

    with Session(engine) as db:
        db.add(Customer(customer_id="C1"))
        db.commit()
        existing = Investigation(
            investigation_id=1,
            customer_id="C1",
            snapshot_key=_snapshot_key("C1", 0, current_corpus_version()),
            status="pending",
            summary="Queued",
            evidence={},
        )
        db.add(existing)
        db.commit()
        investigation_id = existing.investigation_id

        reused, should_process = create_or_reuse_investigation(db, "C1")

    assert reused is not None
    assert reused.investigation_id == investigation_id
    assert reused.status == "pending"
    assert should_process is False
