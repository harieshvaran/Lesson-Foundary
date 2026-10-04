"""Tests for backend API health check endpoint."""

def test_health_endpoint_response(client):
    """Verify /api/v1/health returns DB status and key configuration status safely."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "ok"
    assert data["database"] == "connected"
    assert "api_key_configured" in data
    assert isinstance(data["api_key_configured"], bool)
    assert "llm_provider" in data
    assert "version" in data

    # Verify no raw secret / API key text is present anywhere in response JSON
    raw_response_text = response.text
    assert "your_api_key_here" not in raw_response_text
    assert "mock_key_for_dev" not in raw_response_text
