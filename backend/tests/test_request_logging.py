import logging

from fastapi.testclient import TestClient

from app.main import app


def test_request_middleware_logs_method_path_status_and_duration(caplog):
    client = TestClient(app)
    with caplog.at_level(logging.INFO):
        client.get("/healthz")

    record = next(r for r in caplog.records if r.name == "app.access" and r.message == "request")
    assert record.method == "GET"
    assert record.path == "/healthz"
    assert record.status_code == 200
    assert record.duration_ms >= 0
