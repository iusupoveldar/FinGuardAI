from datetime import date

from fastapi import APIRouter
from fastapi import HTTPException

from ai.ingestion import load_documents
from app.schemas.policy import PolicyDocumentResponse


router = APIRouter(prefix="/policies", tags=["Policies"])


@router.get("/", response_model=list[PolicyDocumentResponse])
def list_current_policies() -> list[PolicyDocumentResponse]:
    """Return active source documents that are currently in effect."""

    try:
        documents = load_documents()
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=503, detail="Policy documents are unavailable") from exc

    today = date.today()
    current = [
        document
        for document in documents
        if document.metadata["active"]
        and date.fromisoformat(str(document.metadata["effective_date"])) <= today
    ]
    return [
        PolicyDocumentResponse(
            document_id=str(document.metadata["document_id"]),
            title=str(document.metadata["title"]),
            company=str(document.metadata.get("company", "")),
            category=str(document.metadata["category"]),
            effective_date=str(document.metadata["effective_date"]),
            version=str(document.metadata["version"]),
            jurisdiction=str(document.metadata["jurisdiction"]),
            content=document.body,
        )
        for document in sorted(current, key=lambda item: str(item.metadata["title"]))
    ]
