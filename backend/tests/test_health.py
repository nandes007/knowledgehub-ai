from fastapi.testclient import TestClient

from app.main import app

# No `with` block: lifespan (which needs a live Postgres) does not run,
# so this stays a pure unit test of the /healthz route.
client = TestClient(app)


def test_healthz_returns_ok():
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
