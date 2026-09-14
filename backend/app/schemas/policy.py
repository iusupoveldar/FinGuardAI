from pydantic import BaseModel


class PolicyDocumentResponse(BaseModel):
    document_id: str
    title: str
    company: str
    category: str
    effective_date: str
    version: str
    jurisdiction: str
    content: str
