from fastapi.testclient import TestClient

from src.api.main import create_app


def test_quickstart_returns_200(db_session):
    app = create_app(db_session_override=db_session)
    client = TestClient(app)
    resp = client.get("/quickstart")
    assert resp.status_code == 200


def test_quickstart_content_type_is_html(db_session):
    app = create_app(db_session_override=db_session)
    client = TestClient(app)
    resp = client.get("/quickstart")
    assert resp.headers["content-type"].startswith("text/html")


def test_quickstart_body_contains_title(db_session):
    app = create_app(db_session_override=db_session)
    client = TestClient(app)
    resp = client.get("/quickstart")
    assert "Emissions Tracker API \u2014 Quickstart" in resp.text


def test_quickstart_body_contains_curl_example(db_session):
    app = create_app(db_session_override=db_session)
    client = TestClient(app)
    resp = client.get("/quickstart")
    assert "curl" in resp.text
