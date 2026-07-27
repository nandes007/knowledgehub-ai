from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_allows_the_configured_frontend_origin():
    response = client.options(
        "/healthz",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_rejects_an_unconfigured_origin():
    response = client.options(
        "/healthz",
        headers={
            "Origin": "http://evil.example.com",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert "access-control-allow-origin" not in response.headers


def test_preflight_does_not_advertise_unused_http_methods():
    response = client.options(
        "/healthz",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "PUT",
        },
    )

    assert "PUT" not in response.headers.get("access-control-allow-methods", "")
