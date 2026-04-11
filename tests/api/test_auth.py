import hashlib


def test_request_without_key_uses_anonymous_limits(client):
    resp = client.get("/v1/companies")
    assert resp.status_code == 200
    assert "X-RateLimit-Limit" in resp.headers


def test_request_with_valid_key(client, seeded_session):
    from src.shared.models import ApiKey
    import uuid

    raw_key = "test-api-key-12345"
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    seeded_session.add(
        ApiKey(
            id=uuid.uuid4(),
            key_hash=key_hash,
            email="test@example.com",
            tier="pro",
            rate_limit=1000,
        )
    )
    seeded_session._session.commit()
    resp = client.get("/v1/companies", headers={"X-API-Key": raw_key})
    assert resp.status_code == 200
    assert resp.headers.get("X-RateLimit-Limit") == "1000"


def test_request_with_invalid_key(client):
    resp = client.get("/v1/companies", headers={"X-API-Key": "bad-key"})
    assert resp.status_code == 401
