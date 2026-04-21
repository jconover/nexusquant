from fastapi.testclient import TestClient
from nexusquant_ingester.main import app


def test_healthz() -> None:
    client = TestClient(app)
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_readyz() -> None:
    client = TestClient(app)
    r = client.get("/readyz")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}
