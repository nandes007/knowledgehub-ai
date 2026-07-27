import logging

from fastapi.testclient import TestClient

from app.main import app

# No `with` block: lifespan (which needs a live Postgres) does not run,
# matching the convention in test_health.py.
client = TestClient(app)


def test_request_middleware_logs_method_path_status_and_duration(caplog):
    with caplog.at_level(logging.INFO, logger="app.access"):
        client.get("/healthz")

    record = next(r for r in caplog.records if r.name == "app.access")
    assert record.method == "GET"
    assert record.path == "/healthz"
    assert record.status_code == 200
    assert record.duration_ms >= 0
