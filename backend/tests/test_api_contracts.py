from fastapi.testclient import TestClient

from main import app


def test_openapi_builds_and_routes_are_typed() -> None:
    schema = app.openapi()
    assert "/customers/" in schema["paths"]
    assert "/customers/{customer_id}/transactions" in schema["paths"]
    assert "/customers/{customer_id}/risk" in schema["paths"]
    assert "/investigate/{customer_id}" in schema["paths"]
    assert "/investigations/{investigation_id}" in schema["paths"]
    assert "/investigations/" in schema["paths"]
    assert "/customers/{customer_id}/investigations/latest" in schema["paths"]
    assert "/policies/" in schema["paths"]

    customer_response = schema["paths"]["/customers/"]["get"]["responses"]["200"]
    assert customer_response["content"]["application/json"]["schema"]["type"] == "array"
    parameters = {
        item["name"] for item in schema["paths"]["/customers/"]["get"]["parameters"]
    }
    assert {"sort_by", "sort_order"}.issubset(parameters)
    history_response = schema["paths"]["/investigations/"]["get"]["responses"]["200"]
    assert history_response["content"]["application/json"]["schema"]["type"] == "array"
    policies_response = schema["paths"]["/policies/"]["get"]["responses"]["200"]
    assert policies_response["content"]["application/json"]["schema"]["type"] == "array"


def test_customer_identifiers_are_strings() -> None:
    schema = app.openapi()
    transaction_path = schema["paths"]["/customers/{customer_id}/transactions"]
    parameter = next(
        item for item in transaction_path["get"]["parameters"]
        if item["name"] == "customer_id"
    )
    assert parameter["schema"]["type"] == "string"


def test_api_robots_file_disallows_crawling() -> None:
    response = TestClient(app).get("/robots.txt")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert response.text == "User-agent: *\nDisallow: /\n"
