# Provider Gateway

OpenAI-compatible proxy that validates API keys from your OpenSaaS app and forwards requests to a third-party AI provider. No GPU needed.

```
User (sk-... key from your app) → Proxy → Provider API (Together / OpenAI / etc.)
                                       ↓
                                    Redis (rate limiting)
                                       ↓
                                    Postgres (key validation + usage tracking)
```

## Files

| File | Purpose |
|------|---------|
| `proxy/main.py` | FastAPI app — validates keys, proxies to provider, tracks usage |
| `proxy/requirements.txt` | Python dependencies |
| `Dockerfile.proxy` | Container build |
| `docker-compose.yml` | Local dev: proxy + Redis |
| `fly.toml` | Fly.io deployment config |
| `.env.example` | Environment variables template |

## Prerequisites

- **Postgres** database shared with your OpenSaaS app (must have `UsageLog` table)
- **Provider API key** — sign up at Together, OpenAI, Fireworks, Groq, etc.

## Local Dev

```bash
cp .env.example .env
# edit .env with your DATABASE_URL and PROVIDER_API_KEY

docker compose up -d
```

## Deploy to Fly.io

```bash
# Install flyctl if you haven't
brew install flyctl

# Launch app
fly launch --no-deploy

# Set secrets
fly secrets set DATABASE_URL="postgresql://..."
fly secrets set PROVIDER_BASE_URL="https://api.together.xyz/v1"
fly secrets set PROVIDER_API_KEY="tsk-..."
fly secrets set INPUT_PRICE_PER_M="0.15"
fly secrets set OUTPUT_PRICE_PER_M="0.60"
fly secrets set RPM_LIMIT="60"

# Optional: managed Redis on Fly
fly redis create
fly secrets set REDIS_URL="redis://..."

# Deploy
fly deploy
```

### Set your domain

```bash
fly certs create api.your-app.com
```

## How Users Connect

```python
from openai import OpenAI

client = OpenAI(
    api_key="sk-...",  # created from your OpenSaaS frontend
    base_url="https://api.your-app.com/v1"
)
```

## Spin Up / Shut Down (to save cost)

```bash
# Stop all machines (stops billing)
fly scale count 0

# Start again
fly scale count 1
```

## Switching Providers

Just change the env vars — no code changes:

```bash
fly secrets set PROVIDER_BASE_URL="https://api.openai.com/v1" PROVIDER_API_KEY="sk-..."
fly deploy
```

## Cost

Runs on Fly.io's cheapest shared-CPU plan (~$5-15/mo). The main cost is whatever you're paying the provider — the proxy itself is negligible.

## Running Tests

Tests use a mock provider so no real API key is needed. They verify auth, rate limiting, and usage logging end-to-end.

### 1. Start the test stack

```bash
cd provider-gateway/tests
docker compose -f docker-compose.test.yml up -d --build
```

Wait for all services to be healthy (check with `docker compose ps`).

### 2. Install test dependencies

```bash
cd provider-gateway
pip install -r tests/requirements-test.txt
```

### 3. Run tests

```bash
cd provider-gateway
pytest tests/ -v
```

### 4. Shut down test stack when done

```bash
cd provider-gateway/tests
docker compose -f docker-compose.test.yml down --volumes
```

### Expected Results

All tests should pass with green `PASSED`. Here's what each test covers:

| Test | What it checks |
|------|----------------|
| `test_no_key_returns_401` | Request without `Authorization` header → 401 |
| `test_invalid_key_returns_401` | Request with unknown key → 401 |
| `test_valid_key_without_subscription_returns_403` | Valid key but no active membership → 403 |
| `test_valid_key_with_active_subscription_returns_200` | Valid key + active membership → 200 with response |
| `test_health_endpoint` | `GET /health` returns `{"status": "ok"}` |
| `test_rate_limit_exceeded_returns_429` | 6th request within a minute → 429 |
| `test_rate_limit_resets_with_different_user` | Different user isn't affected by another's rate limit |
| `test_usage_logged_on_successful_request` | Non-streaming request creates a `UsageLog` row |
| `test_usage_logged_on_streaming_request` | Streaming request also creates a `UsageLog` row |
| `test_no_usage_logged_on_auth_failure` | Failed auth doesn't write to `UsageLog` |

You should see:

```
tests/test_auth.py::test_no_key_returns_401 PASSED
tests/test_auth.py::test_invalid_key_returns_401 PASSED
tests/test_auth.py::test_valid_key_without_subscription_returns_403 PASSED
tests/test_auth.py::test_valid_key_with_active_subscription_returns_200 PASSED
tests/test_auth.py::test_health_endpoint PASSED
tests/test_rate_limit.py::test_rate_limit_exceeded_returns_429 PASSED
tests/test_rate_limit.py::test_rate_limit_resets_with_different_user PASSED
tests/test_usage_log.py::test_usage_logged_on_successful_request PASSED
tests/test_usage_log.py::test_usage_logged_on_streaming_request PASSED
tests/test_usage_log.py::test_no_usage_logged_on_auth_failure PASSED

10 passed in ~5.32s
```
