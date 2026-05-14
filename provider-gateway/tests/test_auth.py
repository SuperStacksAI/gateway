import pytest


@pytest.mark.asyncio
async def test_no_key_returns_401(client):
    resp = await client.post("/v1/chat/completions", json={"model": "test", "messages": []})
    assert resp.status_code == 401
    data = resp.json()
    assert "missing api key" in data["error"]


@pytest.mark.asyncio
async def test_invalid_key_returns_401(client):
    resp = await client.post(
        "/v1/chat/completions",
        json={"model": "test", "messages": []},
        headers={"Authorization": "Bearer sk-fake-key"},
    )
    assert resp.status_code == 401
    data = resp.json()
    assert "invalid" in data["error"]


@pytest.mark.asyncio
async def test_valid_key_without_subscription_returns_403(client, insert_expired_membership):
    resp = await client.post(
        "/v1/chat/completions",
        json={"model": "test", "messages": [{"role": "user", "content": "hi"}]},
        headers={"Authorization": "Bearer sk-test-key-expired-abcdefghijklmnopqrstuvwxyz"},
    )
    assert resp.status_code == 403
    data = resp.json()
    assert "no active subscription" in data["error"]


@pytest.mark.asyncio
async def test_valid_key_with_active_subscription_returns_200(client, insert_test_key):
    resp = await client.post(
        "/v1/chat/completions",
        json={"model": "test", "messages": [{"role": "user", "content": "hi"}]},
        headers={"Authorization": "Bearer sk-test-key-1234567890abcdefghijklmnopqrstuvwxyz"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "choices" in data
    assert len(data["choices"]) > 0


@pytest.mark.asyncio
async def test_health_endpoint(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
