"""Versioned investigation creation and bounded background processing."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timedelta, timezone
import hashlib
import json
import logging
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ai.deepseek import (
    DeepSeekBudgetUnavailable,
    DeepSeekClient,
    DeepSeekError,
)
from ai.prompts import (
    PROMPT_VERSION,
    build_investigation_packet,
    deterministic_narrative,
    prompt_messages,
    validate_narrative,
)
from ai.retrieval import current_corpus_version
from app import config
from app.models.customer import Customer
from app.models.investigation import Investigation
from app.models.transaction import Transaction
from app.services.risk_service import latest_risk_score


logger = logging.getLogger("uvicorn.error")


def _snapshot_key(
    customer_id: str, cutoff_step: int, corpus_version: str
) -> str:
    identity = {
        "customer_id": customer_id,
        "cutoff_step": cutoff_step,
        "model_version": config.RISK_MODEL_VERSION,
        "feature_version": config.RISK_FEATURE_VERSION,
        "corpus_version": corpus_version,
        "prompt_version": PROMPT_VERSION,
        "deepseek_model": config.DEEPSEEK_MODEL,
    }
    return hashlib.sha256(
        json.dumps(identity, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _is_stale(investigation: Investigation) -> bool:
    """Return whether a queued or running job has stopped making progress."""

    updated_at = investigation.updated_at
    if updated_at.tzinfo is None:
        # SQLite returns naive values in tests; production stores timestamptz.
        updated_at = updated_at.replace(tzinfo=timezone.utc)
    cutoff = datetime.now(timezone.utc) - timedelta(
        seconds=config.INVESTIGATION_STALE_AFTER_SECONDS
    )
    return updated_at <= cutoff


def create_or_reuse_investigation(
    db: Session, customer_id: str
) -> tuple[Investigation | None, bool]:
    """Create one pending job per immutable versioned snapshot identity."""

    customer_exists = db.scalar(
        select(Customer.customer_id).where(Customer.customer_id == customer_id)
    )
    if customer_exists is None:
        return None, False

    cutoff_step = int(db.scalar(select(func.max(Transaction.simulation_step))) or 0)
    corpus_version = current_corpus_version()
    key = _snapshot_key(customer_id, cutoff_step, corpus_version)
    risk = latest_risk_score(db, customer_id, cutoff_step=cutoff_step)
    existing = db.scalar(
        select(Investigation)
        .where(Investigation.snapshot_key == key)
        .with_for_update()
    )
    if existing is not None:
        # A score may have been generated after an earlier no-score fallback.
        if existing.risk_score_id is None and risk is not None:
            existing.status = "pending"
            existing.risk_score_id = risk.risk_score_id
            existing.summary = "Investigation queued for the newly available risk snapshot."
            db.commit()
            db.refresh(existing)
            return existing, True
        if existing.status == "failed":
            existing.status = "pending"
            existing.summary = "Investigation queued for retry."
            existing.evidence = {
                key: value
                for key, value in (existing.evidence or {}).items()
                if key != "error_category"
            }
            db.commit()
            db.refresh(existing)
            return existing, True
        if existing.status in {"pending", "in_progress"} and _is_stale(existing):
            recovery_count = int(
                (existing.evidence or {}).get("stale_recovery_count", 0)
            )
            existing.status = "pending"
            existing.summary = "Stale investigation recovered and queued for retry."
            existing.evidence = {
                **(existing.evidence or {}),
                "stale_recovery_count": recovery_count + 1,
            }
            db.commit()
            db.refresh(existing)
            return existing, True
        return existing, False

    investigation = Investigation(
        customer_id=customer_id,
        snapshot_key=key,
        risk_score_id=risk.risk_score_id if risk else None,
        status="pending",
        summary="Investigation queued for background analysis.",
        evidence={
            "data_cutoff_step": cutoff_step,
            "model_version": config.RISK_MODEL_VERSION,
            "feature_version": config.RISK_FEATURE_VERSION,
            "corpus_version": corpus_version,
            "prompt_version": PROMPT_VERSION,
            "configured_deepseek_model": config.DEEPSEEK_MODEL,
        },
    )
    db.add(investigation)
    try:
        db.commit()
    except IntegrityError:
        # The unique key makes concurrent duplicate requests converge.
        db.rollback()
        concurrent = db.scalar(
            select(Investigation).where(Investigation.snapshot_key == key)
        )
        if concurrent is None:
            raise
        return concurrent, False
    db.refresh(investigation)
    return investigation, True


def get_investigation(db: Session, investigation_id: int) -> Investigation | None:
    return db.get(Investigation, investigation_id)


def list_investigations(
    db: Session,
    *,
    limit: int,
    offset: int,
) -> list[Investigation]:
    return list(
        db.scalars(
            select(Investigation)
            .order_by(
                Investigation.updated_at.desc(),
                Investigation.investigation_id.desc(),
            )
            .offset(offset)
            .limit(limit)
        ).all()
    )


def latest_customer_investigation(
    db: Session, customer_id: str
) -> Investigation | None:
    """Return cached work only; this read never starts a new investigation."""

    return db.scalar(
        select(Investigation)
        .where(Investigation.customer_id == customer_id)
        .order_by(
            Investigation.updated_at.desc(),
            Investigation.investigation_id.desc(),
        )
        .limit(1)
    )


def _estimated_cost(usage: dict[str, int]) -> float:
    return (
        usage.get("prompt_cache_hit_tokens", 0)
        / 1_000_000
        * config.DEEPSEEK_CACHE_HIT_RATE
        + usage.get("prompt_cache_miss_tokens", 0)
        / 1_000_000
        * config.DEEPSEEK_CACHE_MISS_RATE
        + usage.get("completion_tokens", 0)
        / 1_000_000
        * config.DEEPSEEK_OUTPUT_RATE
    )


def _spent_today(db: Session) -> float:
    start = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    investigations = db.scalars(
        select(Investigation).where(Investigation.created_at >= start)
    ).all()
    return sum(
        float((item.evidence or {}).get("token_usage", {}).get("estimated_cost", 0))
        for item in investigations
    )


def _fallback_reason(db: Session, risk: Any, sources: list[dict[str, Any]]) -> str | None:
    if risk is None:
        return "A compatible score snapshot was unavailable; DeepSeek was not called."
    if risk.risk_band == "unscored":
        return "The customer is unscored; DeepSeek was not called."
    if not sources:
        return "Policy retrieval was unavailable or returned no relevant passages."
    if not config.DEEPSEEK_ENABLED:
        return "DeepSeek generation is disabled; a deterministic summary was used."
    if not config.DEEPSEEK_API_KEY:
        return "The DeepSeek API key is unavailable; a deterministic summary was used."
    if config.DEEPSEEK_DAILY_BUDGET_USD <= 0:
        return "The configured daily LLM budget is unavailable."
    if max(
        config.DEEPSEEK_CACHE_HIT_RATE,
        config.DEEPSEEK_CACHE_MISS_RATE,
        config.DEEPSEEK_OUTPUT_RATE,
    ) <= 0:
        return "LLM pricing is not configured, so the spending limit cannot be enforced."
    if _spent_today(db) >= config.DEEPSEEK_DAILY_BUDGET_USD:
        return "The configured daily LLM budget is exhausted."
    return None


def _process(db: Session, investigation: Investigation) -> None:
    evidence = dict(investigation.evidence or {})
    cutoff_step = int(evidence["data_cutoff_step"])
    # Pull latest risk score from the database
    risk = latest_risk_score(
        db, investigation.customer_id, cutoff_step=cutoff_step
    )
    sources: list[dict[str, Any]] = []
    corpus_version = str(evidence.get("corpus_version", "unavailable"))

    if risk is not None:
        try:
            # Compare if the current policy is newer than when the risk was calculated
            from ai.retrieval import get_policy_retriever

            retriever = get_policy_retriever()
            if str(retriever.pointer["corpus_version"]) != corpus_version:
                raise ValueError("policy corpus changed after cutoff was frozen")
            sources = [asdict(item) for item in retriever.retrieve(risk.evidence)]
        except (FileNotFoundError, RuntimeError, ValueError) as exc:
            logger.warning(
                "Investigation %s policy retrieval failed: %s",
                investigation.investigation_id,
                exc,
            )
            sources = []

    packet = (
        build_investigation_packet(
            investigation_id=investigation.investigation_id,
            customer_id=investigation.customer_id,
            risk=risk,
            policy_sources=sources,
            corpus_version=corpus_version,
        )
        if risk is not None
        else None
    )
    # Selecting reasons for fallback
    fallback_reason = _fallback_reason(db, risk, sources)
    generation_mode = "deterministic_fallback"
    token_usage: dict[str, Any] = {
        "provider": "deepseek",
        "model": config.DEEPSEEK_MODEL,
        "prompt_tokens": 0,
        "prompt_cache_hit_tokens": 0,
        "prompt_cache_miss_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        "estimated_cost": 0,
        "currency": "USD",
        "pricing_version": config.DEEPSEEK_PRICING_VERSION,
        "retry_count": 0,
    }

    if fallback_reason is not None:
        logger.warning(
            "Investigation %s using deterministic fallback: %s",
            investigation.investigation_id,
            fallback_reason,
        )
        narrative = deterministic_narrative(packet, reason=fallback_reason)
    else:
        logger.warning(
            "Ivestigation %s using Deepseek.",
            investigation.investigation_id
        )
        try:
            client = DeepSeekClient(
                api_key=config.DEEPSEEK_API_KEY,
                base_url=config.DEEPSEEK_BASE_URL,
                model=config.DEEPSEEK_MODEL,
                timeout_seconds=config.DEEPSEEK_TIMEOUT_SECONDS,
                max_output_tokens=config.DEEPSEEK_MAX_OUTPUT_TOKENS,
            )
            result = client.generate(prompt_messages(packet))  # type: ignore[arg-type]
            narrative = validate_narrative(result.content, packet)  # type: ignore[arg-type]
            generation_mode = "deepseek"
            token_usage.update(result.usage)
            token_usage.update(
                {
                    "model": result.provider_model,
                    "latency_ms": result.latency_ms,
                    "retry_count": result.retry_count,
                    "estimated_cost": round(_estimated_cost(result.usage), 8),
                }
            )
            fallback_reason = None
            logger.info(
                "Investigation %s used DeepSeek model=%s latency_ms=%s retries=%s",
                investigation.investigation_id,
                result.provider_model,
                result.latency_ms,
                result.retry_count,
            )
        except DeepSeekBudgetUnavailable:
            fallback_reason = (
                "DeepSeek reported unavailable account balance; a deterministic "
                "summary was used."
            )
            logger.warning(
                "Investigation %s using deterministic fallback: %s",
                investigation.investigation_id,
                fallback_reason,
            )
            narrative = deterministic_narrative(packet, reason=fallback_reason)  # type: ignore[arg-type]
        except (DeepSeekError, ValueError) as exc:
            fallback_reason = (
                "DeepSeek was unavailable or returned an invalid response; a "
                "deterministic summary was used."
            )
            logger.warning(
                "Investigation %s using deterministic fallback: %s (%s: %s)",
                investigation.investigation_id,
                fallback_reason,
                type(exc).__name__,
                exc,
            )
            narrative = deterministic_narrative(packet, reason=fallback_reason)  # type: ignore[arg-type]

    result_payload = narrative.model_dump(mode="json")
    logger.warning(
        "Payload Result: %s",
        str(result_payload)
    )
    evidence.update(
        {
            "corpus_version": corpus_version,
            "risk_snapshot": (
                {
                    "risk_score_id": risk.risk_score_id,
                    "score": float(risk.score),
                    "risk_band": risk.risk_band,
                    "data_cutoff_step": risk.data_cutoff_step,
                    "model_version": risk.model_version,
                    "feature_version": risk.feature_version,
                    "evidence": risk.evidence,
                }
                if risk is not None
                else None
            ),
            "policy_sources": sources,
            "validated_source_ids": [
                item["source_id"] for item in result_payload["sources"]
            ],
            "generation_mode": generation_mode,
            "fallback_reason": fallback_reason,
            "token_usage": token_usage,
            "result": result_payload,
        }
    )
    investigation.risk_score_id = risk.risk_score_id if risk is not None else None
    investigation.summary = narrative.summary
    investigation.evidence = evidence
    investigation.status = "completed"
    db.commit()


def process_investigation(investigation_id: int) -> None:
    """Background-task entry point; always owns its database session."""

    from app.database.connection import SessionLocal

    with SessionLocal() as db:
        investigation = db.scalar(
            select(Investigation)
            .where(Investigation.investigation_id == investigation_id)
            .with_for_update()
        )
        if investigation is None or investigation.status != "pending":
            return
        investigation.status = "in_progress"
        db.commit()
        logger.info("Investigation %s started", investigation_id)
        try:
            _process(db, investigation)
        except Exception:  # noqa: BLE001 - persist only a sanitized failure category
            logger.exception("Investigation %s failed unexpectedly", investigation_id)
            db.rollback()
            failed = db.get(Investigation, investigation_id)
            if failed is not None:
                failed.status = "failed"
                failed.summary = "Investigation processing failed unexpectedly."
                failed.evidence = {
                    **(failed.evidence or {}),
                    "error_category": "internal_processing_error",
                }
                db.commit()
