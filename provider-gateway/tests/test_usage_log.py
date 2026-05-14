import pytest


@pytest.mark.asyncio
async def test_usage_logged_on_successful_request(client, db, insert_test_key):
    headers = {"Authorization": "Bearer sk-test-key-1234567890abcdefghijklmnopqrstuvwxyz"}
    body = {"model": "test", "messages": [{"role": "user", "content": "hi"}]}

    resp = await client.post("/v1/chat/completions", json=body, headers=headers)
    assert resp.status_code == 200

    async with db.acquire() as conn:
        rows = await conn.fetch(
            'SELECT * FROM "UsageLog" WHERE "userId" = $1',
            "test-user-0000-0000-000000000001",
        )

    assert len(rows) >= 1
    row = rows[-1]
    assert row["model"] == "test"
    assert row["promptTokens"] == 10
    assert row["completionTokens"] == 5
    assert row["totalTokens"] == 15
    assert row["costUsd"] == pytest.approx(
        (10 / 1_000_000 * 0.15) + (5 / 1_000_000 * 0.60)
    )


@pytest.mark.asyncio
async def test_usage_logged_on_streaming_request(client, db, insert_test_key):
    headers = {"Authorization": "Bearer sk-test-key-1234567890abcdefghijklmnopqrstuvwxyz"}
    body = {"model": "test", "messages": [{"role": "user", "content": "hi"}], "stream": True}

    async with client.stream("POST", "/v1/chat/completions", json=body, headers=headers) as resp:
        assert resp.status_code == 200
        chunks = [c async for c in resp.aiter_bytes()]

    assert len(chunks) > 0

    async with db.acquire() as conn:
        rows = await conn.fetch(
            'SELECT * FROM "UsageLog" WHERE "userId" = $1',
            "test-user-0000-0000-000000000001",
        )

    assert len(rows) >= 1
    row = rows[-1]
    assert row["promptTokens"] == 10
    assert row["completionTokens"] == 5
    assert row["costUsd"] >= 0


@pytest.mark.asyncio
async def test_no_usage_logged_on_auth_failure(client, db):
    resp = await client.post(
        "/v1/chat/completions",
        json={"model": "test", "messages": [{"role": "user", "content": "hi"}]},
        headers={"Authorization": "Bearer sk-fake-key"},
    )
    assert resp.status_code == 401

    async with db.acquire() as conn:
        rows = await conn.fetch(
            'SELECT * FROM "UsageLog" WHERE "userId" = $1',
            "test-user-0000-0000-000000000001",
        )

    assert len(rows) == 0
