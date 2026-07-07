import pytest
from fastapi.testclient import TestClient
from ember_api import app, API_KEY_NAME, API_KEY

client = TestClient(app)

def test_api_key_required():
    # Attempting to access an endpoint without API key should fail
    response = client.get("/settings")
    assert response.status_code == 401
    assert response.json() == {"detail": "Not authenticated"}

def test_api_key_valid():
    # Providing the correct API key should succeed
    response = client.get("/settings", headers={API_KEY_NAME: API_KEY})
    assert response.status_code == 200
    assert "voice" in response.json()

def test_invalid_api_key():
    # Providing an incorrect API key should fail
    response = client.get("/settings", headers={API_KEY_NAME: "wrong-key"})
    assert response.status_code == 403
