from sparkweave.services.diagnostics import explain_provider_error


def test_iflytek_llm_apikey_not_found_explains_http_key() -> None:
    message = explain_provider_error(
        "llm",
        "Error code: 401 - {'message': 'HMAC signature cannot be verified: apikey not found'}",
    )

    assert "APIKey" in message
    assert "APISecret" in message
    assert "APIPassword" in message


def test_iflytek_llm_secret_mismatch_explains_api_password_or_pair() -> None:
    message = explain_provider_error(
        "llm",
        "Error code: 401 - {'message': 'HMAC secret key does not match'}",
    )

    assert "APIKey:APISecret" in message
    assert "APIPassword" in message


def test_iflytek_embedding_missing_credentials_explains_three_fields() -> None:
    message = explain_provider_error(
        "embedding",
        "iFlytek Spark Embedding requires app_id, api_key and api_secret.",
    )

    assert "APPID" in message
    assert "APIKey" in message
    assert "APISecret" in message


def test_iflytek_ws_missing_credentials_explains_three_fields() -> None:
    message = explain_provider_error(
        "llm",
        "iFlytek Spark WebSocket requires app_id, api_key and api_secret.",
    )

    assert "APIKey" in message
    assert "APISecret" in message
    assert "APIPassword" in message


def test_iflytek_search_apikey_not_found_explains_api_password() -> None:
    message = explain_provider_error(
        "search",
        "Error code: 401 - {'message': 'HMAC signature cannot be verified: apikey not found'}",
    )

    assert "ONE SEARCH" in message
    assert "APIPassword" in message
