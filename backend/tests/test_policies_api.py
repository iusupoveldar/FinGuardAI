from fastapi.testclient import TestClient

from main import app


def test_current_policies_include_full_source_documents() -> None:
    response = TestClient(app).get("/policies/")

    assert response.status_code == 200
    policies = response.json()
    monitoring = next(
        item for item in policies if item["document_id"] == "NSB-STD-TM-004"
    )
    assert monitoring["version"] == "1.4"
    assert "# Transaction Monitoring Alert Standard" in monitoring["content"]
    assert "## Patterns requiring review" in monitoring["content"]
