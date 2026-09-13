"""Parse, chunk, and atomically publish the local policy corpus."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import date
import hashlib
import json
import os
from pathlib import Path
import re
from typing import Any

import chromadb

from ai.embedding import Embedder, SentenceTransformerEmbedder


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DOCUMENTS_DIR = ROOT / "ai/documents"
DEFAULT_INDEX_DIR = ROOT / "ai/index"
POINTER_FILE = "current.json"
REQUIRED_METADATA = {
    "document_id",
    "title",
    "category",
    "effective_date",
    "version",
    "jurisdiction",
}


@dataclass(frozen=True)
class PolicyDocument:
    path: Path
    metadata: dict[str, str | bool]
    body: str
    checksum: str


@dataclass(frozen=True)
class PolicyChunk:
    chunk_id: str
    text: str
    metadata: dict[str, str | int | bool]


def parse_front_matter(path: Path) -> PolicyDocument:
    raw = path.read_text(encoding="utf-8")
    lines = raw.splitlines()
    if not lines or lines[0].strip() != "---":
        raise ValueError(f"{path.name} has no YAML-style front matter")
    try:
        closing = next(
            index for index, line in enumerate(lines[1:], start=1) if line.strip() == "---"
        )
    except StopIteration as exc:
        raise ValueError(f"{path.name} has unterminated front matter") from exc

    metadata: dict[str, str | bool] = {}
    for line in lines[1:closing]:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        key, separator, value = line.partition(":")
        if not separator:
            raise ValueError(f"invalid metadata line in {path.name}: {line!r}")
        clean_value = value.strip().strip('"').strip("'")
        metadata[key.strip()] = clean_value
    missing = REQUIRED_METADATA.difference(metadata)
    if missing:
        raise ValueError(f"{path.name} is missing metadata: {sorted(missing)}")
    try:
        date.fromisoformat(str(metadata["effective_date"]))
    except ValueError as exc:
        raise ValueError(f"{path.name} has an invalid effective_date") from exc
    status = str(metadata.pop("status", "active")).lower()
    if status not in {"active", "retired"}:
        raise ValueError(f"{path.name} status must be active or retired")
    metadata["active"] = status == "active"
    body = "\n".join(lines[closing + 1 :]).strip()
    return PolicyDocument(
        path=path,
        metadata=metadata,
        body=body,
        checksum=hashlib.sha256(raw.encode("utf-8")).hexdigest(),
    )


def load_documents(documents_dir: Path = DEFAULT_DOCUMENTS_DIR) -> list[PolicyDocument]:
    documents = []
    for path in sorted(documents_dir.glob("*.md")):
        if path.name.lower() == "readme.md":
            continue
        documents.append(parse_front_matter(path))
    if not documents:
        raise ValueError(f"no policy documents found in {documents_dir}")
    ids = [str(document.metadata["document_id"]) for document in documents]
    if len(ids) != len(set(ids)):
        raise ValueError("policy document_id values must be unique")
    return documents


def _sections(body: str) -> list[tuple[str, str]]:
    heading_path: list[str] = []
    sections: list[tuple[str, str]] = []
    content: list[str] = []

    def flush() -> None:
        text = "\n".join(content).strip()
        if text:
            sections.append((" > ".join(heading_path), text))
        content.clear()

    for line in body.splitlines():
        match = re.match(r"^(#{1,6})\s+(.+?)\s*$", line)
        if match:
            flush()
            level = len(match.group(1))
            del heading_path[level - 1 :]
            heading_path.append(match.group(2))
        else:
            content.append(line)
    flush()
    return sections


def _word_chunks(text: str, target_tokens: int, overlap_tokens: int) -> list[str]:
    # A transparent approximation is adequate for local corpus budgeting.
    target_words = max(40, int(target_tokens / 1.3))
    overlap_words = max(0, int(overlap_tokens / 1.3))
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]
    chunks: list[str] = []
    current: list[str] = []
    current_words = 0
    for paragraph in paragraphs:
        words = paragraph.split()
        if current and current_words + len(words) > target_words:
            rendered = "\n\n".join(current)
            chunks.append(rendered)
            overlap = rendered.split()[-overlap_words:] if overlap_words else []
            current = [" ".join(overlap)] if overlap else []
            current_words = len(overlap)
        if len(words) > target_words and not current:
            start = 0
            stride = max(1, target_words - overlap_words)
            while start < len(words):
                chunks.append(" ".join(words[start : start + target_words]))
                start += stride
            continue
        current.append(paragraph)
        current_words += len(words)
    if current:
        chunks.append("\n\n".join(current))
    return chunks


def chunk_document(
    document: PolicyDocument,
    *,
    target_tokens: int = 450,
    overlap_tokens: int = 60,
) -> list[PolicyChunk]:
    if target_tokens < 100 or overlap_tokens >= target_tokens:
        raise ValueError("chunk sizes require target >= 100 and overlap < target")
    chunks: list[PolicyChunk] = []
    chunk_number = 0
    for heading, section_text in _sections(document.body):
        for body_chunk in _word_chunks(section_text, target_tokens, overlap_tokens):
            chunk_number += 1
            rendered = f"{heading}\n\n{body_chunk}" if heading else body_chunk
            document_id = str(document.metadata["document_id"])
            chunk_id = f"{document_id}:{document.checksum[:12]}:{chunk_number:04d}"
            metadata: dict[str, str | int | bool] = {
                **document.metadata,
                "checksum": document.checksum,
                "heading": heading,
                "chunk_number": chunk_number,
                "source_path": document.path.name,
            }
            chunks.append(PolicyChunk(chunk_id, rendered, metadata))
    return chunks


def corpus_version(documents: list[PolicyDocument], model_name: str) -> str:
    digest = hashlib.sha256(model_name.encode("utf-8"))
    for document in documents:
        digest.update(str(document.metadata["document_id"]).encode("utf-8"))
        digest.update(document.checksum.encode("ascii"))
    return digest.hexdigest()[:16]


def _write_pointer(index_dir: Path, payload: dict[str, Any]) -> None:
    temporary = index_dir / f".{POINTER_FILE}.tmp"
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, index_dir / POINTER_FILE)


def build_index(
    *,
    documents_dir: Path = DEFAULT_DOCUMENTS_DIR,
    index_dir: Path = DEFAULT_INDEX_DIR,
    embedder: Embedder | None = None,
) -> dict[str, Any]:
    """Build an immutable collection and switch the pointer after success."""

    embedder = embedder or SentenceTransformerEmbedder()
    documents = load_documents(documents_dir)
    version = corpus_version(documents, embedder.model_name)
    collection_name = f"policy_{version}"
    chunks = [chunk for document in documents for chunk in chunk_document(document)]
    index_dir.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(index_dir / "chroma"))

    existing_names = {collection.name for collection in client.list_collections()}
    if collection_name in existing_names:
        collection = client.get_collection(collection_name)
        if collection.count() != len(chunks):
            raise RuntimeError(
                f"existing collection {collection_name} is incomplete; remove it and rebuild"
            )
    else:
        collection = client.create_collection(
            collection_name, metadata={"hnsw:space": "cosine"}
        )
        try:
            batch_size = 128
            for start in range(0, len(chunks), batch_size):
                batch = chunks[start : start + batch_size]
                texts = [chunk.text for chunk in batch]
                collection.add(
                    ids=[chunk.chunk_id for chunk in batch],
                    documents=texts,
                    metadatas=[chunk.metadata for chunk in batch],
                    embeddings=embedder.embed(texts),
                )
        except Exception:
            client.delete_collection(collection_name)
            raise

    pointer = {
        "corpus_version": version,
        "collection": collection_name,
        "embedding_model": embedder.model_name,
        "document_count": len(documents),
        "chunk_count": len(chunks),
    }
    _write_pointer(index_dir, pointer)
    return pointer


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the FinGuardAI policy index")
    parser.add_argument("--documents", type=Path, default=DEFAULT_DOCUMENTS_DIR)
    parser.add_argument("--index", type=Path, default=DEFAULT_INDEX_DIR)
    args = parser.parse_args()
    print(json.dumps(build_index(documents_dir=args.documents, index_dir=args.index), indent=2))


if __name__ == "__main__":
    main()
