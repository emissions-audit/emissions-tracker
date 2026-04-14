import hashlib
import uuid

import pytest

from src.shared.models import ApiKey, Webhook


RAW_KEY = "webhook-test-key-99999"
KEY_HASH = hashlib.sha256(RAW_KEY.encode()).hexdigest()
API_KEY_ID = uuid.UUID("00000000-0000-0000-0000-aaaaaaaaaaaa")
HEADERS = {"X-API-Key": RAW_KEY}


@pytest.fixture
def webhook_client(seeded_session):
    seeded_session.add(
        ApiKey(id=API_KEY_ID, key_hash=KEY_HASH, email="wh@test.com", tier="pro", rate_limit=1000)
    )
    seeded_session._session.commit()
    from src.api.main import create_app
    from fastapi.testclient import TestClient

    app = create_app(db_session_override=seeded_session)
    return TestClient(app)


def test_create_webhook(webhook_client):
    resp = webhook_client.post(
        "/v1/webhooks",
        json={"url": "https://example.com/hook", "events": ["new_emission"]},
        headers=HEADERS,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["url"] == "https://example.com/hook"
    assert data["events"] == ["new_emission"]
    assert data["active"] is True


def test_create_webhook_invalid_event(webhook_client):
    resp = webhook_client.post(
        "/v1/webhooks",
        json={"url": "https://example.com/hook", "events": ["bogus_event"]},
        headers=HEADERS,
    )
    assert resp.status_code == 422


def test_create_webhook_requires_api_key(webhook_client):
    resp = webhook_client.post(
        "/v1/webhooks",
        json={"url": "https://example.com/hook", "events": ["new_emission"]},
    )
    assert resp.status_code == 401


def test_list_webhooks(webhook_client, seeded_session):
    seeded_session.add(
        Webhook(
            id=uuid.uuid4(),
            api_key_id=API_KEY_ID,
            url="https://example.com/h1",
            events=["new_emission"],
            secret="a" * 64,
        )
    )
    seeded_session._session.commit()
    resp = webhook_client.get("/v1/webhooks", headers=HEADERS)
    assert resp.status_code == 200
    assert resp.json()["total"] >= 1


def test_get_webhook(webhook_client, seeded_session):
    wh_id = uuid.UUID("00000000-0000-0000-0000-bbbbbbbbbbbb")
    seeded_session.add(
        Webhook(
            id=wh_id,
            api_key_id=API_KEY_ID,
            url="https://example.com/h2",
            events=["coverage_update"],
            secret="b" * 64,
        )
    )
    seeded_session._session.commit()
    resp = webhook_client.get(f"/v1/webhooks/{wh_id}", headers=HEADERS)
    assert resp.status_code == 200
    assert resp.json()["url"] == "https://example.com/h2"


def test_get_webhook_not_found(webhook_client):
    resp = webhook_client.get(
        f"/v1/webhooks/{uuid.uuid4()}", headers=HEADERS
    )
    assert resp.status_code == 404


def test_delete_webhook(webhook_client, seeded_session):
    wh_id = uuid.UUID("00000000-0000-0000-0000-cccccccccccc")
    seeded_session.add(
        Webhook(
            id=wh_id,
            api_key_id=API_KEY_ID,
            url="https://example.com/h3",
            events=["new_filing"],
            secret="c" * 64,
        )
    )
    seeded_session._session.commit()
    resp = webhook_client.delete(f"/v1/webhooks/{wh_id}", headers=HEADERS)
    assert resp.status_code == 204

    resp2 = webhook_client.get(f"/v1/webhooks/{wh_id}", headers=HEADERS)
    assert resp2.status_code == 404


def test_deactivate_webhook(webhook_client, seeded_session):
    wh_id = uuid.UUID("00000000-0000-0000-0000-dddddddddddd")
    seeded_session.add(
        Webhook(
            id=wh_id,
            api_key_id=API_KEY_ID,
            url="https://example.com/h4",
            events=["new_emission"],
            secret="d" * 64,
        )
    )
    seeded_session._session.commit()
    resp = webhook_client.patch(f"/v1/webhooks/{wh_id}/deactivate", headers=HEADERS)
    assert resp.status_code == 200
    assert resp.json()["active"] is False


def test_activate_webhook(webhook_client, seeded_session):
    wh_id = uuid.UUID("00000000-0000-0000-0000-eeeeeeeeeeee")
    seeded_session.add(
        Webhook(
            id=wh_id,
            api_key_id=API_KEY_ID,
            url="https://example.com/h5",
            events=["new_emission"],
            secret="e" * 64,
            active=False,
        )
    )
    seeded_session._session.commit()
    resp = webhook_client.patch(f"/v1/webhooks/{wh_id}/activate", headers=HEADERS)
    assert resp.status_code == 200
    assert resp.json()["active"] is True


def test_webhook_scoped_to_api_key(webhook_client, seeded_session):
    other_key_id = uuid.UUID("00000000-0000-0000-0000-ffffffffffff")
    wh_id = uuid.UUID("00000000-0000-0000-0000-111111111111")
    other_raw = "other-key-for-scoping"
    seeded_session.add(
        ApiKey(
            id=other_key_id,
            key_hash=hashlib.sha256(other_raw.encode()).hexdigest(),
            email="other@test.com",
            tier="free",
            rate_limit=100,
        )
    )
    seeded_session.add(
        Webhook(
            id=wh_id,
            api_key_id=other_key_id,
            url="https://example.com/other",
            events=["new_emission"],
            secret="f" * 64,
        )
    )
    seeded_session._session.commit()
    resp = webhook_client.get(f"/v1/webhooks/{wh_id}", headers=HEADERS)
    assert resp.status_code == 404
