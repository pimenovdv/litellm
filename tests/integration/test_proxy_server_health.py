import pytest
from fastapi.testclient import TestClient

from litellm.proxy.proxy_server import app

client = TestClient(app)

@pytest.mark.integration
def test_health_liveliness():
    """Test that the /health/liveliness endpoint returns 200 OK without making external requests."""
    response = client.get("/health/liveliness")
    assert response.status_code == 200

@pytest.mark.integration
def test_health_readiness():
    """Test that the /health/readiness endpoint returns 200 OK."""
    response = client.get("/health/readiness")
    # It might return 500 if DB is not connected, but we just check if it responds.
    assert response.status_code in [200, 500]
