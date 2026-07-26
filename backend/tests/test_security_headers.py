from fastapi.testclient import TestClient

from app.main import app

# No `with` block: lifespan (which needs a live Postgres) does not run,
# matching the convention in test_health.py.
client = TestClient(app)


def test_responses_include_standard_security_headers():
    response = client.get("/healthz")

    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "strict-origin-when-cross-origin"
