from datetime import date
import hashlib
from pathlib import Path
import re
import shutil

import ai.retrieval as retrieval
from ai.ingestion import build_index, chunk_document, parse_front_matter
from ai.retrieval import PolicyRetriever


class HashingEmbedder:
    model_name = "test-hashing-v1"

    def embed(self, texts):
        vectors = []
        for text in texts:
            vector = [0.0] * 128
            for token in re.findall(r"[a-z0-9-]+", text.lower()):
                index = int(hashlib.sha256(token.encode()).hexdigest()[:8], 16) % len(vector)
                vector[index] += 1.0
            magnitude = sum(value * value for value in vector) ** 0.5 or 1.0
            vectors.append([value / magnitude for value in vector])
        return vectors


def test_front_matter_and_heading_chunks_preserve_source_metadata() -> None:
    path = Path("ai/documents/transaction_monitoring_standard.md")
    document = parse_front_matter(path)
    chunks = chunk_document(document)

    assert document.metadata["document_id"] == "NSB-STD-TM-004"
    assert all(chunk.metadata["checksum"] == document.checksum for chunk in chunks)
    assert any("Patterns requiring review" in chunk.metadata["heading"] for chunk in chunks)


def test_retrieval_finds_pattern_and_excludes_future_policy(tmp_path: Path) -> None:
    documents = tmp_path / "documents"
    documents.mkdir()
    for source in Path("ai/documents").glob("*.md"):
        shutil.copy2(source, documents / source.name)
    index = tmp_path / "index"
    embedder = HashingEmbedder()
    pointer = build_index(documents_dir=documents, index_dir=index, embedder=embedder)

    retriever = PolicyRetriever(index_dir=index, embedder=embedder)
    results = retriever.retrieve(
        {"patterns": ["rapid movement funds new counterparties sudden increase transaction count"]},
        as_of_date=date(2025, 3, 15),
        minimum_score=0.0,
    )

    assert pointer["chunk_count"] > 0
    assert results
    assert results[0].document_id == "NSB-STD-TM-004"
    assert all(result.document_id != "NSB-PLAY-INV-002" for result in results)
    assert all(result.source_id.startswith(result.document_id) for result in results)


def test_default_retriever_is_cached_for_the_process(monkeypatch) -> None:
    created = []

    class FakeRetriever:
        def __init__(self) -> None:
            created.append(self)

    retrieval.get_policy_retriever.cache_clear()
    monkeypatch.setattr(retrieval, "PolicyRetriever", FakeRetriever)
    try:
        first = retrieval.get_policy_retriever()
        second = retrieval.get_policy_retriever()
    finally:
        retrieval.get_policy_retriever.cache_clear()

    assert first is second
    assert len(created) == 1
