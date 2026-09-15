"""Retrieve current policy passages from structured risk evidence."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
from functools import lru_cache
import json
from pathlib import Path
import re
from threading import Lock
from typing import Any, Iterable

import chromadb

from ai.embedding import Embedder, SentenceTransformerEmbedder
from ai.ingestion import DEFAULT_INDEX_DIR, POINTER_FILE


@dataclass(frozen=True)
class RetrievedPolicySource:
    source_id: str
    document_id: str
    title: str
    version: str
    heading: str
    text: str
    score: float


def current_corpus_version(index_dir: Path = DEFAULT_INDEX_DIR) -> str:
    pointer_path = index_dir / POINTER_FILE
    if not pointer_path.exists():
        return "unavailable"
    try:
        pointer = json.loads(pointer_path.read_text(encoding="utf-8"))
        return str(pointer["corpus_version"])
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        return "unavailable"


def build_pattern_query(risk_facts: dict[str, Any] | Iterable[str]) -> str:
    if isinstance(risk_facts, dict):
        patterns = risk_facts.get("patterns", [])
        factors = risk_facts.get("top_factors", [])
        values = [*patterns, *factors]
    else:
        values = list(risk_facts)
    clean = [str(value).strip() for value in values if str(value).strip()]
    return "; ".join(clean + ["evidence requirements", "investigation procedure"])


def _keywords(text: str) -> set[str]:
    stopwords = {"the", "and", "for", "was", "with", "from", "this", "that"}
    return {
        token
        for token in re.findall(r"[a-z0-9-]+", text.lower())
        if len(token) > 2 and token not in stopwords
    }


class PolicyRetriever:
    def __init__(
        self,
        *,
        index_dir: Path = DEFAULT_INDEX_DIR,
        embedder: Embedder | None = None,
    ) -> None:
        pointer_path = index_dir / POINTER_FILE
        if not pointer_path.exists():
            raise FileNotFoundError("policy index is not built; run python -m ai.ingestion")
        self.pointer = json.loads(pointer_path.read_text(encoding="utf-8"))
        self.embedder = embedder or SentenceTransformerEmbedder(
            self.pointer["embedding_model"]
        )
        if self.embedder.model_name != self.pointer["embedding_model"]:
            raise ValueError("query embedder does not match the indexed embedding model")
        client = chromadb.PersistentClient(path=str(index_dir / "chroma"))
        self.collection = client.get_collection(self.pointer["collection"])
        self._embedding_lock = Lock()

    def retrieve(
        self,
        risk_facts: dict[str, Any] | Iterable[str],
        *,
        as_of_date: date | None = None,
        jurisdiction: str = "Canada",
        limit: int = 5,
        candidate_count: int = 20,
        token_budget: int = 1_800,
        minimum_score: float = 0.15,
    ) -> list[RetrievedPolicySource]:
        if limit < 1 or token_budget < 1:
            return []
        query = build_pattern_query(risk_facts)
        count = self.collection.count()
        if not count:
            return []
        # The default retriever is shared for the life of the API process.
        # Serialize model inference to avoid multiplying peak PyTorch memory.
        with self._embedding_lock:
            query_embedding = self.embedder.embed([query])
        results = self.collection.query(
            query_embeddings=query_embedding,
            n_results=min(candidate_count, count),
            include=["documents", "metadatas", "distances"],
        )
        as_of = as_of_date or date.today()
        query_keywords = _keywords(query)
        ranked: list[tuple[float, str, dict[str, Any]]] = []
        for text, metadata, distance in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        ):
            if not metadata.get("active", False):
                continue
            if date.fromisoformat(str(metadata["effective_date"])) > as_of:
                continue
            chunk_jurisdiction = str(metadata.get("jurisdiction", "general"))
            if chunk_jurisdiction.lower() not in {jurisdiction.lower(), "general"}:
                continue
            semantic_score = 1.0 - float(distance)
            overlap = len(query_keywords.intersection(_keywords(
                f"{metadata.get('title', '')} {metadata.get('heading', '')} {text}"
            )))
            combined_score = semantic_score + min(0.20, overlap * 0.02)
            if combined_score >= minimum_score:
                ranked.append((combined_score, text, metadata))

        ranked.sort(key=lambda item: item[0], reverse=True)
        selected: list[RetrievedPolicySource] = []
        used_tokens = 0
        seen_ids: set[str] = set()
        for score, text, metadata in ranked:
            source_id = (
                f"{metadata['document_id']}:{metadata['checksum'][:12]}:"
                f"{int(metadata['chunk_number']):04d}"
            )
            if source_id in seen_ids:
                continue
            estimated_tokens = max(1, int(len(text.split()) * 1.3))
            if used_tokens + estimated_tokens > token_budget:
                continue
            selected.append(
                RetrievedPolicySource(
                    source_id=source_id,
                    document_id=str(metadata["document_id"]),
                    title=str(metadata["title"]),
                    version=str(metadata["version"]),
                    heading=str(metadata["heading"]),
                    text=text,
                    score=round(score, 6),
                )
            )
            seen_ids.add(source_id)
            used_tokens += estimated_tokens
            if len(selected) == limit:
                break
        return selected

    def retrieve_with_evidence(
        self, evidence: dict[str, Any], **kwargs: Any
    ) -> dict[str, Any]:
        sources = self.retrieve(evidence, **kwargs)
        return {
            "score_evidence": evidence,
            "corpus_version": self.pointer["corpus_version"],
            "policy_sources": [asdict(source) for source in sources],
        }


@lru_cache(maxsize=1)
def get_policy_retriever() -> PolicyRetriever:
    """Return one lazy, process-wide retriever and embedding model."""

    return PolicyRetriever()
