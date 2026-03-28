import hashlib
import uuid

from src.shared.models import ApiKey


def _add_pro_key(session, raw_key="pro-key-123"):
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    session.add(ApiKey(
        id=uuid.uuid4(), key_hash=key_hash, email="pro@example.com",
        tier="pro", rate_limit=1000,
    ))
    session.commit()
    return raw_key


def test_full_export_requires_pro(client):
    resp = client.get("/v1/export/full")
    assert resp.status_code == 403


def test_full_export_csv(client, seeded_session):
    key = _add_pro_key(seeded_session)
    resp = client.get("/v1/export/full?format=csv", headers={"X-API-Key": key})
    assert resp.status_code == 200
    assert "text/csv" in resp.headers.get("content-type", "")
    lines = resp.text.strip().split("\n")
    assert len(lines) >= 2  # header + data


def test_full_export_json(client, seeded_session):
    key = _add_pro_key(seeded_session)
    resp = client.get("/v1/export/full?format=json", headers={"X-API-Key": key})
    assert resp.status_code == 200
    data = resp.json()
    assert "companies" in data
    assert "emissions" in data
