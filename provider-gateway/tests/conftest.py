import os
import pytest
import hashlib
import asyncpg
import httpx
import redis.asyncio as redis

TEST_DB_URL = os.environ.get("TEST_DB_URL", "postgresql://test:test@localhost:5433/test")
TEST_REDIS_URL = os.environ.get("TEST_REDIS_URL", "redis://localhost:6380")
PROXY_URL = os.environ.get("PROXY_URL", "http://localhost:8081")

TEST_USER_ID = "test-user-0000-0000-000000000001"
TEST_USER_EXPIRED_ID = "test-user-0000-0000-000000000002"
TEST_API_KEY_RAW = "sk-test-key-1234567890abcdefghijklmnopqrstuvwxyz"
TEST_API_KEY_RAW_EXPIRED = "sk-test-key-expired-abcdefghijklmnopqrstuvwxyz"
TEST_API_KEY_HASH = hashlib.sha256(TEST_API_KEY_RAW.encode()).hexdigest()
TEST_API_KEY_HASH_EXPIRED = hashlib.sha256(TEST_API_KEY_RAW_EXPIRED.encode()).hexdigest()


@pytest.fixture(scope="function")
async def db():
    pool = await asyncpg.create_pool(TEST_DB_URL)
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS "ApiKey" (
                id TEXT PRIMARY KEY,
                "userId" TEXT NOT NULL,
                name TEXT NOT NULL,
                "keyPrefix" TEXT NOT NULL,
                "keyHash" TEXT NOT NULL UNIQUE,
                status TEXT NOT NULL DEFAULT 'ACTIVE',
                "lastUsedAt" TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS "Membership" (
                id TEXT PRIMARY KEY,
                "userId" TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'ACTIVE'
            );
            CREATE TABLE IF NOT EXISTS "UsageLog" (
                id TEXT PRIMARY KEY,
                "createdAt" TIMESTAMP NOT NULL DEFAULT NOW(),
                "userId" TEXT NOT NULL,
                "apiKeyId" TEXT,
                model TEXT NOT NULL,
                "promptTokens" INTEGER NOT NULL,
                "completionTokens" INTEGER NOT NULL,
                "totalTokens" INTEGER NOT NULL,
                "costUsd" DOUBLE PRECISION NOT NULL,
                endpoint TEXT NOT NULL DEFAULT 'chat/completions'
            );
            CREATE INDEX IF NOT EXISTS "UsageLog_userId_createdAt_idx" ON "UsageLog"("userId", "createdAt");
            CREATE INDEX IF NOT EXISTS "UsageLog_apiKeyId_idx" ON "UsageLog"("apiKeyId");
        """)
    yield pool
    await pool.close()


@pytest.fixture(scope="function")
async def insert_test_key(db):
    async with db.acquire() as conn:
        await conn.execute("""
            INSERT INTO "ApiKey" (id, "userId", name, "keyPrefix", "keyHash", status)
            VALUES ('test-key-active', $1, 'test-key', $2, $3, 'ACTIVE')
            ON CONFLICT ("keyHash") DO UPDATE SET status = 'ACTIVE'
        """, TEST_USER_ID, TEST_API_KEY_RAW[:10], TEST_API_KEY_HASH)

        await conn.execute("""
            INSERT INTO "Membership" (id, "userId", status)
            VALUES ('test-membership-active', $1, 'ACTIVE')
            ON CONFLICT (id) DO UPDATE SET status = 'ACTIVE'
        """, TEST_USER_ID)

    yield

    async with db.acquire() as conn:
        await conn.execute('DELETE FROM "UsageLog" WHERE "userId" = $1', TEST_USER_ID)
        await conn.execute('DELETE FROM "ApiKey" WHERE "userId" = $1', TEST_USER_ID)
        await conn.execute('DELETE FROM "Membership" WHERE "userId" = $1', TEST_USER_ID)


@pytest.fixture(scope="function")
async def insert_expired_membership(db):
    async with db.acquire() as conn:
        await conn.execute("""
            INSERT INTO "ApiKey" (id, "userId", name, "keyPrefix", "keyHash", status)
            VALUES ('test-key-expired', $1, 'test-key', $2, $3, 'ACTIVE')
            ON CONFLICT ("keyHash") DO NOTHING
        """, TEST_USER_EXPIRED_ID, TEST_API_KEY_RAW_EXPIRED[:10], TEST_API_KEY_HASH_EXPIRED)

        await conn.execute("""
            INSERT INTO "Membership" (id, "userId", status)
            VALUES ('test-membership-expired', $1, 'CANCELED')
            ON CONFLICT (id) DO UPDATE SET status = 'CANCELED'
        """, TEST_USER_EXPIRED_ID)

    yield

    async with db.acquire() as conn:
        await conn.execute('DELETE FROM "UsageLog" WHERE "userId" = $1', TEST_USER_EXPIRED_ID)
        await conn.execute('DELETE FROM "ApiKey" WHERE "userId" = $1', TEST_USER_EXPIRED_ID)
        await conn.execute('DELETE FROM "Membership" WHERE "userId" = $1', TEST_USER_EXPIRED_ID)


@pytest.fixture(scope="function", autouse=True)
async def flush_redis():
    r = redis.from_url(TEST_REDIS_URL, decode_responses=True)
    await r.flushall()
    await r.aclose()


@pytest.fixture(scope="function")
async def client():
    async with httpx.AsyncClient(base_url=PROXY_URL) as c:
        yield c
