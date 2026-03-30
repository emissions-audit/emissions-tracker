from fastapi.testclient import TestClient
from src.api.main import create_app


def test_health_returns_ok(db_session):
    app = create_app(db_session_override=db_session)
    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert "version" in data


def test_ready_returns_ok_when_db_connected(db_session):
    app = create_app(db_session_override=db_session)
    client = TestClient(app)
    resp = client.get("/ready")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ready"
    assert data["database"] == "connected"
