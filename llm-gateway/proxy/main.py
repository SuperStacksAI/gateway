import os
import uuid
import hashlib
import json
import asyncio
from datetime import datetime
from typing import AsyncGenerator

import httpx
import redis.asyncio as redis
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse, JSONResponse
import asyncpg

app = FastAPI(title="LLM Gateway")

DATABASE_URL = os.environ["DATABASE_URL"]
REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379")
VLLM_BASE_URL = os.environ.get("VLLM_BASE_URL", "http://vllm:8000")
MODEL_NAME = os.environ.get("MODEL_NAME", "minimax-2.7")

# Token pricing: $X per 1M tokens
INPUT_PRICE_PER_M = float(os.environ.get("INPUT_PRICE_PER_M", "0.15"))
OUTPUT_PRICE_PER_M = float(os.environ.get("OUTPUT_PRICE_PER_M", "0.60"))

# Rate limits
RPM_LIMIT = int(os.environ.get("RPM_LIMIT", "60"))
TPM_LIMIT = int(os.environ.get("TPM_LIMIT", "300000"))

pool: asyncpg.Pool = None
r: redis.Redis = None


async def get_db_pool():
    global pool
    if pool is None:
        pool = await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=5)
    return pool


@app.on_event("startup")
async def startup():
    global r
    r = redis.from_url(REDIS_URL, decode_responses=True)


@app.on_event("shutdown")
async def shutdown():
    global pool, r
    if pool:
        await pool.close()
    if r:
        await r.close()


def hash_api_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


async def verify_key(raw_key: str) -> dict | None:
    key_hash = hash_api_key(raw_key)
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT ak.id, ak."userId", ak.status,
                   m.status IS NOT NULL as has_active_membership
            FROM "ApiKey" ak
            LEFT JOIN "Membership" m ON m."userId" = ak."userId" AND m.status = 'ACTIVE'
            WHERE ak."keyHash" = $1
            """,
            key_hash,
        )
        if not row:
            return None
        if row["status"] != "ACTIVE":
            return None
        return {"user_id": row["userId"], "id": row["id"], "has_active_membership": row["has_active_membership"]}


async def check_rate_limit(user_id: str) -> bool:
    key = f"ratelimit:rpm:{user_id}"
    pipe = r.pipeline()
    pipe.incr(key)
    pipe.expire(key, 60)
    results = await pipe.execute()
    rpm = int(results[0])
    if rpm > RPM_LIMIT:
        return False
    return True


async def log_usage(
    user_id: str, api_key_id: str | None, model: str,
    prompt_tokens: int, completion_tokens: int, cost_usd: float,
):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO "UsageLog" (id, "userId", "apiKeyId", model, "promptTokens", "completionTokens", "totalTokens", "costUsd", endpoint)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, 'chat/completions')
            """,
            str(uuid.uuid4()), user_id, api_key_id, model,
            prompt_tokens, completion_tokens, prompt_tokens + completion_tokens, cost_usd,
        )
        await conn.execute(
            'UPDATE "ApiKey" SET "lastUsedAt" = $1 WHERE id = $2',
            datetime.utcnow(), api_key_id,
        )


def parse_key_from_header(auth: str | None) -> str | None:
    if not auth:
        return None
    if auth.startswith("Bearer "):
        return auth[7:]
    return auth


async def proxy_stream(
    request: Request, vllm_url: str, headers: dict, body: dict, user_id: str, api_key_id: str | None
) -> AsyncGenerator[bytes, None]:
    prompt_tokens = 0
    completion_tokens = 0
    async with httpx.AsyncClient(timeout=120) as client:
        async with client.stream("POST", vllm_url, json=body, headers=headers) as resp:
            if resp.status_code != 200:
                error_body = await resp.aread()
                yield error_body
                return

            try:
                async for chunk in resp.aiter_bytes():
                    yield chunk
                    decoded = chunk.decode(errors="ignore")
                    if decoded.startswith("data: ") and decoded != "data: [DONE]\n":
                        try:
                            data = json.loads(decoded[6:])
                            usage = data.get("usage", {})
                            if usage:
                                prompt_tokens = usage.get("prompt_tokens", prompt_tokens)
                                completion_tokens = usage.get("completion_tokens", completion_tokens)
                        except json.JSONDecodeError:
                            pass
            except GeneratorExit:
                pass
            finally:
                if prompt_tokens or completion_tokens:
                    cost = (prompt_tokens / 1_000_000 * INPUT_PRICE_PER_M +
                            completion_tokens / 1_000_000 * OUTPUT_PRICE_PER_M)
                    asyncio.create_task(
                        log_usage(user_id, api_key_id, MODEL_NAME, prompt_tokens, completion_tokens, cost)
                    )


def get_model(body: dict) -> str:
    return body.get("model", MODEL_NAME)


@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    raw_key = parse_key_from_header(request.headers.get("Authorization"))
    if not raw_key:
        return JSONResponse(status_code=401, content={"error": "missing api key"})

    key_data = await verify_key(raw_key)
    if not key_data:
        return JSONResponse(status_code=401, content={"error": "invalid or revoked api key"})

    if not key_data["has_active_membership"]:
        return JSONResponse(status_code=403, content={"error": "no active subscription"})

    allowed = await check_rate_limit(key_data["user_id"])
    if not allowed:
        return JSONResponse(status_code=429, content={"error": "rate limit exceeded"})

    body = await request.json()
    body["model"] = get_model(body)

    vllm_headers = {
        "Content-Type": "application/json",
    }
    vllm_url = f"{VLLM_BASE_URL}/v1/chat/completions"

    if body.get("stream", False):
        return StreamingResponse(
            proxy_stream(request, vllm_url, vllm_headers, body, key_data["user_id"], key_data["id"]),
            media_type="text/event-stream",
        )

    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(vllm_url, json=body, headers=vllm_headers)
        if resp.status_code != 200:
            return JSONResponse(status_code=resp.status_code, content=resp.json())

        data = resp.json()
        usage = data.get("usage", {})
        prompt_tokens = usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("completion_tokens", 0)
        cost = (prompt_tokens / 1_000_000 * INPUT_PRICE_PER_M +
                completion_tokens / 1_000_000 * OUTPUT_PRICE_PER_M)
        asyncio.create_task(
            log_usage(key_data["user_id"], key_data["id"], MODEL_NAME, prompt_tokens, completion_tokens, cost)
        )
        return JSONResponse(content=data)


@app.get("/health")
async def health():
    return {"status": "ok"}
