from main import app


def test_openapi_builds_and_routes_are_typed() -> None:
    schema = app.openapi()
    assert "/customers/" in schema["paths"]
    assert "/customers/{customer_id}/transactions" in schema["paths"]
    assert "/investigate/{customer_id}" in schema["paths"]

    customer_response = schema["paths"]["/customers/"]["get"]["responses"]["200"]
    assert customer_response["content"]["application/json"]["schema"]["type"] == "array"


def test_customer_identifiers_are_strings() -> None:
    schema = app.openapi()
    transaction_path = schema["paths"]["/customers/{customer_id}/transactions"]
    parameter = next(
        item for item in transaction_path["get"]["parameters"]
        if item["name"] == "customer_id"
    )
    assert parameter["schema"]["type"] == "string"
