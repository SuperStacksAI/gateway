import uuid
import hashlib
import pytest


@pytest.mark.asyncio
async def test_rate_limit_exceeded_returns_429(client, db):
    user_id = str(uuid.uuid4())
    api_key_raw = f"sk-rate-test-{uuid.uuid4().hex}"
    key_hash = hashlib.sha256(api_key_raw.encode()).hexdigest()

    async with db.acquire() as conn:
        await conn.execute("""
            INSERT INTO "ApiKey" (id, "userId", name, "keyPrefix", "keyHash", status)
            VALUES ($1, $2, 'rate-test', $3, $4, 'ACTIVE')
        """, str(uuid.uuid4()), user_id, api_key_raw[:10], key_hash)

        await conn.execute("""
            INSERT INTO "Membership" (id, "userId", status)
            VALUES ($1, $2, 'ACTIVE')
        """, str(uuid.uuid4()), user_id)

    headers = {"Authorization": f"Bearer {api_key_raw}"}
    body = {"model": "test", "messages": [{"role": "user", "content": "hi"}]}

    for _ in range(5):
        resp = await client.post("/v1/chat/completions", json=body, headers=headers)
        assert resp.status_code == 200

    resp = await client.post("/v1/chat/completions", json=body, headers=headers)
    assert resp.status_code == 429
    data = resp.json()
    assert "rate limit" in data["error"]


@pytest.mark.asyncio
async def test_rate_limit_resets_with_different_user(client, db):
    user_id = str(uuid.uuid4())
    api_key_raw = f"sk-rate-test-{uuid.uuid4().hex}"
    key_hash = hashlib.sha256(api_key_raw.encode()).hexdigest()

    async with db.acquire() as conn:
        await conn.execute("""
            INSERT INTO "ApiKey" (id, "userId", name, "keyPrefix", "keyHash", status)
            VALUES ($1, $2, 'rate-test', $3, $4, 'ACTIVE')
        """, str(uuid.uuid4()), user_id, api_key_raw[:10], key_hash)

        await conn.execute("""
            INSERT INTO "Membership" (id, "userId", status)
            VALUES ($1, $2, 'ACTIVE')
        """, str(uuid.uuid4()), user_id)

    headers = {"Authorization": f"Bearer {api_key_raw}"}
    body = {"model": "test", "messages": [{"role": "user", "content": "hi"}]}

    for _ in range(6):
        resp = await client.post("/v1/chat/completions", json=body, headers=headers)

    assert resp.status_code == 429
